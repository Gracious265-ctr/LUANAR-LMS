"""Add ``EmployeeProfile.team``.

An employee's team is what selects the approval workflow for their leave, so this
is the field that makes "who approves what" a property of the team rather than of
the person's job title.

Deliberately nullable with no data migration. Every existing employee is left
without a team, and the consequence is visible rather than silent: the workflow
provider refuses to build a chain for an employee with no team, so the employee
sees "Ask HR to assign them to a team" instead of quietly being routed by a
default. Backfilling a plausible team per employee would be a guess, and a wrong
guess is worse than an explicit gap — it would route real applications to the
wrong approver.

Depends on ``teams.0001`` because ``Team`` is created there.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0004_employeeprofile_gender"),
        ("teams", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="employeeprofile",
            name="team",
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    "The team this employee belongs to. The team selects the "
                    "approval workflow applied to their leave; blank means the "
                    "employee cannot submit until HR assigns them to a team."
                ),
                null=True,
                on_delete=models.PROTECT,
                related_name="members",
                to="teams.team",
            ),
        ),
    ]
