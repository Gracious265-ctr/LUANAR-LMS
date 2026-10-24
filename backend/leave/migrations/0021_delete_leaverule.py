"""Retire ``leave.LeaveRule``: its data now lives on the type (§4.2).

Runs after ``leave_types.0002``, which is the last migration allowed to read
the rule rows — that one copied every effective-dated rule onto its
``leave_types.LeaveType`` — so the table can be dropped here without losing a
value. Nothing references it: the model's only foreign key points at the leave
type, and types outlive the rules written against them.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("leave", "0020_gradeleaveentitlement"),
        ("leave_types", "0002_fold_leave_rules_into_types"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="leaverule",
            name="leaverule_max_duration_days_gte_1",
        ),
        migrations.RemoveConstraint(
            model_name="leaverule",
            name="leaverule_min_notice_days_gte_0",
        ),
        migrations.DeleteModel(
            name="LeaveRule",
        ),
    ]
