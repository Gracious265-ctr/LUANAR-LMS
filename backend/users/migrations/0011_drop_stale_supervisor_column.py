"""Drop the orphaned ``users_employeeprofile.supervisor_id`` column.

``0005_employeeprofile_supervisor`` was applied to this database on
2026-09-28 12:35 — the same minute ``plans.0001_initial`` was — and its file
was subsequently deleted. The row in ``django_migrations`` outlived both the
migration and the ``EmployeeProfile.supervisor`` field it introduced, so the
physical column was left behind with nothing able to read it: no model field,
no query, no fixture.

``manage.py check_schema_drift`` reports it as present-in-the-database-but-
not-in-the-model. Dropping it makes the schema agree with the models again.

``IF EXISTS`` matters: a database built fresh from the current migrations
never had this column, because the migration that introduced it is gone.
Against this development database the bare ``ALTER TABLE ... DROP COLUMN``
succeeded; against a fresh test database it would raise. Idempotent SQL keeps
the repair correct for both.

Reverse is a no-op rather than a recreation: Django's state has never contained
this field, so restoring the column would be restoring drift, and the 6
non-null values it holds are unreachable either way.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0010_department_org_unit"),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                "ALTER TABLE users_employeeprofile "
                "DROP COLUMN IF EXISTS supervisor_id;"
            ],
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
