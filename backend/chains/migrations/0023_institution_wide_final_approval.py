"""Resolve institution-wide final approval through role assignments.

Unit 10 restricts a section approver to the owning team's own department, which
an earlier version of this schema did not enforce. Some roles are genuinely
institution-wide: the DVC signs off for every faculty, so as a *team*
appointment they were eligible for exactly one department and could not act on
the rest. Flagging the role institution-wide and resolving it through
``RoleAssignment`` is what lets one officer hold the final step everywhere.

The role list is named explicitly instead of being inferred from "this role is
appointed on sections belonging to more than one department". That inference
would be wrong: the HOD was also appointed across two departments, but the fix
there is a *second HOD* in the other department, not one HOD approving for a
faculty they have nothing to do with. A migration cannot tell those two cases
apart, and guessing would quietly widen who can approve what, so the decision is
recorded here instead.
"""

from django.db import migrations

# Roles that hold a final institution-wide approval by the office they occupy
# rather than by the department they sit in.
INSTITUTION_WIDE_ROLE_CODES = ["dvc"]


def flag_institution_wide_roles(apps, schema_editor):
    """Give the named roles an institution-wide holding, and drop the
    department-scoped appointments that the flag replaces.

    Each distinct person appointed to such a role becomes a holder of it, so
    nobody loses the ability to approve on migration: the existing DVC keeps
    signing off, just through the global holding instead of a section row. The
    section rows are then cleared because a role that resolves globally must
    not also be pinned to one department's section, which would let the
    department-scoped row win in one team and the holding in another.
    """
    ApproverRole = apps.get_model("chains", "ApproverRole")
    RoleAssignment = apps.get_model("chains", "RoleAssignment")
    Section = apps.get_model("chains", "Section")

    for code in INSTITUTION_WIDE_ROLE_CODES:
        role = ApproverRole.objects.filter(code=code).first()
        if role is None:
            # Nothing to promote. A role may legitimately not exist yet in a
            # fresh install, where the seed creates it already flagged.
            continue

        sections = Section.objects.filter(approver_role=role)
        holders = {
            section.approver_id
            for section in sections
            if section.approver_id is not None
        }

        role.is_institution_wide = True
        role.save(update_fields=["is_institution_wide"])

        for user_id in holders:
            RoleAssignment.objects.get_or_create(user_id=user_id, role=role)

        cleared = sections.exclude(approver=None).update(approver=None)
        if cleared:
            print(
                f"  Promoted '{code}' to institution-wide and promoted "
                f"{len(holders)} holder(s) from {cleared} section appointment(s)."
            )


def unflag_institution_wide_roles(apps, schema_editor):
    """Flip the flag back.

    The ``RoleAssignment`` rows are deliberately left in place. Deleting them
    would silently revoke a real approval right during a rollback, and a
    ``RoleAssignment`` whose role is no longer institution-wide is rejected by
    the model's validation rather than acted on — so the stale row is inert and
    visible, which is safer than removing an officer's authority unattended.
    """
    ApproverRole = apps.get_model("chains", "ApproverRole")
    ApproverRole.objects.filter(code__in=INSTITUTION_WIDE_ROLE_CODES).update(
        is_institution_wide=False
    )


class Migration(migrations.Migration):
    dependencies = [
        ("chains", "0022_team_workflow_optional"),
    ]

    operations = [
        migrations.RunPython(
            flag_institution_wide_roles,
            unflag_institution_wide_roles,
        ),
    ]