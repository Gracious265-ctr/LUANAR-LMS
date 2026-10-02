"""Point teams at the department rows created in ``users.0007``.

The employee-side half of the same conversion lives in ``users.0008``; this is
the team side, and it runs after it. That order is deliberate. ``users`` has to
be a dependency of ``workflows`` here rather than the other way round, because a
migration in ``users`` that waits on ``workflows`` would apply the whole
``workflows`` chain before ``users.0005`` adds ``EmployeeProfile.team`` — and
``workflows.0014`` reads that column, so the chain has to come after it, not
before. Putting ``Department`` in ``users`` keeps every dependency pointing the
way it already pointed.

A department that only employees used is not dropped: it is a department a team
is about to be created in, and creating the row now means creating the team
later does not also create a department.
"""

from django.db import migrations, models
import django.db.models.deletion


def collect_departments(apps, schema_editor):
    """One Department row per distinct non-blank ``Team.department`` string."""
    Department = apps.get_model("users", "Department")
    Team = apps.get_model("workflows", "Team")

    existing = {
        department.name.strip().casefold() for department in Department.objects.all()
    }
    wanted: dict[str, str] = {}
    for raw in Team.objects.order_by("pk").values_list("department", flat=True):
        name = (raw or "").strip()
        if not name:
            continue
        key = name.casefold()
        if key in existing:
            continue
        wanted.setdefault(key, name)

    Department.objects.bulk_create(
        [Department(name=name) for name in wanted.values()]
    )


def point_teams_at_departments(apps, schema_editor):
    """Copy each team's text department onto the new reference column."""
    Department = apps.get_model("users", "Department")
    Team = apps.get_model("workflows", "Team")

    by_name = {
        department.name.strip().casefold(): department.pk
        for department in Department.objects.all()
    }
    pks_by_department: dict[int, list[int]] = {}
    for pk, raw in Team.objects.order_by("pk").values_list("pk", "department"):
        department_id = by_name.get((raw or "").strip().casefold())
        if department_id is None:
            continue
        pks_by_department.setdefault(department_id, []).append(pk)

    for department_id, pks in pks_by_department.items():
        Team.objects.filter(pk__in=pks).update(department_ref=department_id)


def noop(apps, schema_editor):
    """Not reversible: a dropped free-text column cannot be reconstructed."""


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0008_employee_department_reference"),
        ("workflows", "0019_team_owns_its_workflow"),
    ]

    operations = [
        migrations.RunPython(collect_departments, noop),
        migrations.AddField(
            model_name="team",
            name="department_ref",
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    "The department this team belongs to. A department holds one "
                    "or more teams. It is what scopes approvers — only an "
                    "employee in this department may be made this team's "
                    "approver — but it is not a routing key: routing follows "
                    "the team."
                ),
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="teams",
                to="users.department",
            ),
        ),
        migrations.RunPython(point_teams_at_departments, noop),
        migrations.RemoveField(model_name="team", name="department"),
        migrations.RenameField(
            model_name="team", old_name="department_ref", new_name="department"
        ),
    ]