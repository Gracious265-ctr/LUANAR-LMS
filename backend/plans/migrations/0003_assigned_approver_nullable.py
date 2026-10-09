"""Make ``plans_planapprovalstage.assigned_approver_id`` nullable.

``0001_initial`` was applied to this database on 2026-09-28 while this column
was still ``NOT NULL``. The file's content then changed before it was
committed in ``82a773b`` (2026-09-30) to add ``null=True``, and Django records
a migration as applied and never re-runs it — so the model, the migration
state and the service code all say the column is nullable while the physical
column is not.

A stage is born with no approver: ``assign_plan_workflow`` passes
``assigned_approver=None`` because a section is resolved by whoever acts
first. Submission therefore raised ``IntegrityError`` on the very first
``bulk_create`` and the endpoint 500'd — and had it not, the plan would have
been stranded as ``submitted`` with no approval chain.

``manage.py makemigrations --check`` cannot see this: it compares the model
against the migration state, never against the live schema. Run
``manage.py check_schema_drift`` to catch the rest.

State is untouched — it already reads ``null=True`` — so this is a pure
live-schema repair with no ``state_operations``. On a freshly created database
the statement is a no-op. The reverse is a no-op too: putting ``NOT NULL``
back would fail as soon as any open stage exists, and would recreate exactly
the drift this migration removes.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("plans", "0002_schedule_plan_housekeeping"),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                "ALTER TABLE plans_planapprovalstage "
                "ALTER COLUMN assigned_approver_id DROP NOT NULL;"
            ],
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
