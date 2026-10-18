"""Hand ownership of ``LeaveType`` to ``leave_config`` (§1.1).

State-only, and deliberately so: ``leave_leavetype`` is the pre-existing table,
so nothing is copied, dropped, or altered in the database — the ``leave`` app
simply stops declaring a model the ``leave_config`` app now owns, and the two
grade-entitlement foreign keys are re-pointed at the identical table under its
new owner. Every referencing row keeps working because the table name and the
integer primary key never change.

The ``plans.LeavePlan.leave_type`` foreign key is re-pointed by
``plans.0003``, which this migration depends on so that no state in between
refers to a model this one deletes.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("leave", "0021_delete_leaverule"),
        ("plans", "0003_alter_leaveplan_leave_type"),
        ("leave_config", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name="gradeleaveentitlement",
                    name="leave_type",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="grade_leave_entitlements",
                        to="leave_config.leavetype",
                    ),
                ),
                migrations.AlterField(
                    model_name="gradeentitlement",
                    name="leave_type",
                    field=models.ForeignKey(
                        blank=True,
                        help_text=(
                            "The leave type this band grants. Naming it is what "
                            "puts the type in the employee's selection for "
                            "grades in this range."
                        ),
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="grade_entitlements",
                        to="leave_config.leavetype",
                    ),
                ),
                migrations.DeleteModel(
                    name="LeaveType",
                ),
            ],
        ),
    ]
