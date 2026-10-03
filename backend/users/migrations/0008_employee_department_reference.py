"""Point employees at the department rows created in ``0007``.

An employee's department has to be the same kind of thing as a team's,
because the rule "an approver must be in the team's department" is answered by
comparing them. As two free-text columns that comparison was a spelling contest
between whoever typed them; as two foreign keys it is an identity.

The text column is converted with the add/copy/drop/rename sequence rather than
an in-place type change, because altering the column's type in place would ask
Postgres to cast ``'ICT'`` to an integer. Matching is case-insensitive on the
trimmed text, keeping the first spelling seen, so ``"ICT"`` and ``" ict "``
become one department rather than two that look identical. An employee whose
text is blank gets no department: blank meant "not claiming one", and inventing
a department would be a guess.

``workflows.0020`` converts the same column on ``Team`` and is free to come
afterwards, because by then this app already holds the rows it needs.
"""

from django.db import migrations, models
import django.db.models.deletion


def collect_departments(apps, schema_editor):
    """One Department row per distinct non-blank ``EmployeeProfile.department``."""
    Department = apps.get_model("users", "Department")
    EmployeeProfile = apps.get_model("users", "EmployeeProfile")

    by_name: dict[str, str] = {}
    for raw in EmployeeProfile.objects.order_by("pk").values_list(
        "department", flat=True
    ):
        name = (raw or "").strip()
        if not name:
            continue
        by_name.setdefault(name.casefold(), name)

    Department.objects.bulk_create(
        [Department(name=name) for name in by_name.values()]
    )


def point_employees_at_departments(apps, schema_editor):
    """Copy each employee's text department onto the new reference column."""
    Department = apps.get_model("users", "Department")
    EmployeeProfile = apps.get_model("users", "EmployeeProfile")

    by_name = {
        department.name.strip().casefold(): department.pk
        for department in Department.objects.all()
    }
    pks_by_department: dict[int, list[int]] = {}
    for pk, raw in EmployeeProfile.objects.order_by("pk").values_list(
        "pk", "department"
    ):
        department_id = by_name.get((raw or "").strip().casefold())
        if department_id is None:
            continue
        pks_by_department.setdefault(department_id, []).append(pk)

    for department_id, pks in pks_by_department.items():
        EmployeeProfile.objects.filter(pk__in=pks).update(
            department_ref=department_id
        )


def noop(apps, schema_editor):
    """Not reversible: a dropped free-text column cannot be reconstructed.

    The forward direction is the whole point of the migration — one department
    row per distinct string — so restoring the column would only restore a
    denormalized copy of data the new column already holds.
    """


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0007_department"),
    ]

    operations = [
        migrations.RunPython(collect_departments, noop),
        migrations.AddField(
            model_name="employeeprofile",
            name="department_ref",
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    "The department this employee belongs to. It is what makes "
                    "the employee eligible to be a team's approver: an approver "
                    "must be in the same department as the team they approve "
                    "for."
                ),
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="employees",
                to="users.department",
            ),
        ),
        migrations.RunPython(point_employees_at_departments, noop),
        migrations.RemoveField(model_name="employeeprofile", name="department"),
        migrations.RenameField(
            model_name="employeeprofile",
            old_name="department_ref",
            new_name="department",
        ),
    ]