"""Remove the approver roles 0011 seeds.

Roles are HR data, not product data. 0011 created six canonical codes so an
already-populated database could resolve the stages the old code hardcoded
in Python. A bare database has no stages and no employees, so those rows are
pure seed: nothing routes to them until HR builds a chain, and HR should
build the chain the institution actually uses rather than the one a migration
guessed.

This migration takes the seed codes back out **only when nothing references
them** — a fresh ``migrate`` ends at zero roles. If any section or holding
still points at one, the rows are live configuration rather than seed and are
left alone, so this cannot delete a real approval right on a database that has
been used. Creating roles on a bare install is an HR action through the app,
which is where labels, history scope and the institution-wide flag belong.

The reverse is a no-op: rewinding to before this migration re-runs 0011's
forwards and the roles come back with it.
"""

from django.db import migrations


SEED_CODES = (
    "supervisor",
    "hod",
    "dean",
    "registrar",
    "campus_registrar",
    "dvc",
)


def forwards(apps, schema_editor):
    SectionMember = apps.get_model("workflows", "SectionMember")
    Section = apps.get_model("workflows", "Section")
    RoleAssignment = apps.get_model("workflows", "RoleAssignment")
    TeamRoleAssignment = apps.get_model("workflows", "TeamRoleAssignment")
    CampusRoleAssignment = apps.get_model("workflows", "CampusRoleAssignment")
    ApproverRole = apps.get_model("workflows", "ApproverRole")

    roles = ApproverRole.objects.filter(code__in=SEED_CODES)
    role_ids = list(roles.values_list("id", flat=True))
    if not role_ids:
        return

    # If anything still points at a seed code, HR has used the system and these
    # rows are no longer seed — leave every role alone rather than delete a
    # real approval right mid-flight. On a fresh install nothing references
    # them, so the six rows 0011 created are removed and the database ends at
    # zero roles.
    dependents = (
        SectionMember.objects.filter(
            section__approver_role_id__in=role_ids
        ).count()
        + Section.objects.filter(approver_role_id__in=role_ids).count()
        + RoleAssignment.objects.filter(role_id__in=role_ids).count()
        + TeamRoleAssignment.objects.filter(role_id__in=role_ids).count()
        + CampusRoleAssignment.objects.filter(role_id__in=role_ids).count()
    )
    if dependents:
        return

    roles.delete()


def backwards(apps, schema_editor):
    """Nothing to restore here — 0011 re-seeds if the database is rewound."""


class Migration(migrations.Migration):
    dependencies = [
        ("workflows", "0027_team_category_workflow_team_alter_team_campus_and_more"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
