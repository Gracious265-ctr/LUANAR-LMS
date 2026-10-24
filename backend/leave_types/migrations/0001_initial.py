"""Take ownership of the pre-existing ``leave_leavetype`` table (§1.1).

The table was created by the ``leave`` app, which still has ``LeaveType`` in
its own state until ``leave.0021`` runs. This migration is therefore entirely
state-only: no DDL is emitted, no row moves, and every foreign key pointing at
the table keeps working because the table name never changes.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
                    name="LeaveType",
                    fields=[
                        (
                            "id",
                            models.BigAutoField(
                                auto_created=True,
                                primary_key=True,
                                serialize=False,
                                verbose_name="ID",
                            ),
                        ),
                        ("name", models.CharField(max_length=120, unique=True)),
                        (
                            "code",
                            models.SlugField(blank=True, max_length=50, unique=True),
                        ),
                        (
                            "is_active",
                            models.BooleanField(
                                default=True,
                                help_text=(
                                    "Whether HR still offers this type. Deactivating hides it from new "
                                    "applications and plans without deleting it, so applications "
                                    "already filed against it keep their type and its rules keep their "
                                    "history. Never hard-delete a referenced type (§1.5)."
                                ),
                            ),
                        ),
                        (
                            "plannable",
                            models.BooleanField(
                                default=True,
                                help_text=(
                                    "Whether employees may pre-plan this type (Leave Plans). Types that "
                                    "are rarely planned ahead — sick leave, for instance — set this off "
                                    "so they never appear on the Create a Plan form."
                                ),
                            ),
                        ),
                        (
                            "plan_notice_days",
                            models.PositiveIntegerField(
                                blank=True,
                                null=True,
                                help_text=(
                                    "How many days before a plan's start date the reminder email fires. "
                                    "Null means no reminder window is configured; the plan stays visible "
                                    "and can still be applied for manually."
                                ),
                            ),
                        ),
                    ],
                    options={
                        "db_table": "leave_leavetype",
                        "ordering": ["name"],
                    },
                ),
            ],
        ),
    ]
