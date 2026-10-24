"""Backfill approver roles and turn role codes into role references.

This is the only migration in the sequence that decides anything row by row, so
it is the only one worth reading in full. It runs after 0010 (the tables and
staging columns exist) and before 0012 (the text columns are dropped and the new
columns are made NOT NULL), which is what lets it be both idempotent and
reversible.

What it does, in order:

1. **Create the six canonical roles.** These are the codes the application used
   to hardcode, so every existing workflow stage resolves to a real row. The
   history scope, cancellation flag, and institution-wide flag for each are the
   behaviour the old hardcoded checks implemented — this migration is where that
   behaviour moves from scattered ``if role == "hod"`` branches into data.

2. **Point each workflow stage at its role**, matching the old text code to the
   new role. A code that is not one of the six is *not* an error: a stray code
   from development or test data would otherwise make the whole migration
   unrunnable on a real database. Instead a role is created for it, inactive, so
   the row keeps resolving and the resulting workflow visibly fails activation
   until HR decides what it should have been.

3. **Snapshot the two per-application role properties** onto every existing
   ``ApplicationStage``: the history scope and the cancellation-handling flag.
   This is what makes "changing a role's history scope does not alter an
   in-flight application" true for applications that already exist, not just for
   ones submitted after the feature.

4. **Give the active registrar the registrar role institution-wide.** Registrars
   are the one role the old code resolved globally rather than through a team, so
   a registrar with no team must still be able to approve. This is the one
   ``RoleAssignment`` created outside the dev seed, because the sequence has to
   work on an already-populated database.

The reverse undoes all four: the registrar holding, then the snapshots, then the
references, then the roles themselves. Roles are deleted rather than deactivated
in reverse because by then the references are already gone and nothing points at
them.
"""

from django.db import migrations

# The codes the application hardcoded before roles became data, with the
# behaviour each one implemented. Kept here as literal data — this migration is a
# historical record, and must not import from the models it is creating.
# (code, label, description, history_scope, handles_cancellation, wide)
SEED_ROLES = [
    (
        "supervisor",
        "Supervisor",
        "Line manager of the applicant.",
        "all",
        True,
        False,
    ),
    (
        "hod",
        "Head of Department",
        "Head of the applicant's department.",
        "same_department",
        True,
        False,
    ),
    (
        "dean",
        "Dean",
        "Dean of the applicant's faculty.",
        "same_faculty",
        False,
        False,
    ),
    (
        "registrar",
        "Registrar",
        "Institution-wide registrar; approves every application.",
        "current_financial_year",
        False,
        True,
    ),
    (
        "campus_registrar",
        "Campus Registrar",
        "Registrar for a single campus. New in this migration — no workflow used "
        "this code before, so there is no prior state to back out of.",
        "current_financial_year",
        False,
        True,
    ),
    (
        "dvc",
        "Deputy Vice-Chancellor",
        "Deputy Vice-Chancellor; final institution-wide approval.",
        "current_financial_year",
        False,
        False,
    ),
]


def _title_from_code(code: str) -> str:
    """``campus_registrar`` -> ``Campus Registrar``."""
    return " ".join(part.capitalize() for part in code.replace("-", "_").split("_"))


def _ensure_role(ApproverRole, code: str):
    """The role for ``code``, creating an inert one if the code is unrecognised.

    An unrecognised code is preserved rather than rejected so that one stray row
    of development or test data cannot make this migration unrunnable on a real
    database. The role is created *inactive*, which is the safe default: its
    workflow will fail activation with a message naming the role, so HR has to
    look at it, and nothing routes to it in the meantime.
    """
    role = ApproverRole.objects.filter(code=code).first()
    if role is not None:
        return role
    return ApproverRole.objects.create(
        code=code,
        label=_title_from_code(code),
        description=(
            "Created by migration 0011 to preserve an unrecognised role code. "
            "Inactive on purpose: activate it only after confirming it is a real "
            "approver role."
        ),
        is_active=False,
        history_scope="current_financial_year",
        handles_cancellation=False,
        is_institution_wide=False,
    )


def forwards(apps, schema_editor):
    ApproverRole = apps.get_model("chains", "ApproverRole")
    RoleAssignment = apps.get_model("chains", "RoleAssignment")
    WorkflowStage = apps.get_model("chains", "WorkflowStage")
    ApplicationStage = apps.get_model("chains", "ApplicationStage")
    User = apps.get_model("users", "User")

    for code, label, description, scope, handles_cancellation, wide in SEED_ROLES:
        ApproverRole.objects.update_or_create(
            code=code,
            defaults={
                "label": label,
                "description": description,
                "is_active": True,
                "history_scope": scope,
                "handles_cancellation": handles_cancellation,
                "is_institution_wide": wide,
            },
        )

    # --- 2. workflow stages ------------------------------------------------
    # Resolved row by row rather than with a single UPDATE ... FROM, so that an
    # unknown code is handled explicitly instead of silently becoming NULL and
    # failing the NOT NULL in 0012.
    for stage in WorkflowStage.objects.all().only("id", "approver_role"):
        role = _ensure_role(ApproverRole, stage.approver_role)
        stage.approver_role_ref_staging = role.pk
        stage.save(update_fields=["approver_role_ref_staging"])

    # --- 3. application-stage snapshots ------------------------------------
    # Set on every stage, not just in-flight ones: a stage is the record of what
    # the applicant's approval chain was, and a completed application's history
    # must read the same as an in-flight one's.
    for stage in ApplicationStage.objects.all().only(
        "id", "role", "role_ref", "history_scope", "handles_cancellation"
    ):
        role = _ensure_role(ApproverRole, stage.role)
        stage.role_ref = role
        stage.history_scope = role.history_scope
        stage.handles_cancellation = role.handles_cancellation
        stage.save(
            update_fields=["role_ref", "history_scope", "handles_cancellation"]
        )

    # --- 4. institution-wide registrar --------------------------------------
    # Every active registrar becomes a holder of the institution-wide registrar
    # role. Registrars are matched on the *old* User.role value, which is still
    # intact here: narrowing User.role to employee/approver/hr happens in
    # users/0006, which depends on this migration.
    registrar = ApproverRole.objects.get(code="registrar")
    for user in User.objects.filter(role="registrar", is_active=True):
        RoleAssignment.objects.get_or_create(user=user, role=registrar)


def backwards(apps, schema_editor):
    ApproverRole = apps.get_model("chains", "ApproverRole")
    RoleAssignment = apps.get_model("chains", "RoleAssignment")
    Team = apps.get_model("chains", "Team")
    WorkflowStage = apps.get_model("chains", "WorkflowStage")
    ApplicationStage = apps.get_model("chains", "ApplicationStage")

    # The registrar holding created in step 4 is the only assignment this
    # migration owns. A registrar who is also a member of a team got that
    # membership some other way, so their holding is left in place: removing it
    # would undo a configuration change this migration never made.
    registrar = ApproverRole.objects.filter(code="registrar").first()
    if registrar is not None:
        for assignment in RoleAssignment.objects.filter(role=registrar):
            if not Team.objects.filter(
                memberships__user_id=assignment.user_id
            ).exists():
                assignment.delete()

    # Snapshots and references go back to blank/NULL. 0012's reverse has already
    # restored the text columns by the time a reverse reaches this point, and
    # the original codes are still sitting in them.
    ApplicationStage.objects.update(
        role_ref=None, history_scope="", handles_cancellation=False
    )
    WorkflowStage.objects.update(approver_role_ref_staging=None)

    # No rows reference the roles any more, so they can go. This also removes the
    # inert roles invented for stray codes.
    ApproverRole.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("chains", "0010_approverrole_campus_team_structure"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
