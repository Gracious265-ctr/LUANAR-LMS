"""One workflow membership per employee, wide approver or not.

Until now the ``(team, user)`` constraint was conditional on
``is_wide_approver``: everyone sat on one of a team's chains, but a wide
approver could sit on several. The rule is now the same for everybody — a
normal-member row is where that person's own leave routes, so it is one
workflow, full stop — and the database enforces it on ``user`` alone.

Any existing extra rows are collapsed first; keeping the row whose workflow is
its team's routing default (then the oldest) preserves the chain that actually
routes the person's leave.

Reversing is a no-op: the deleted rows cannot be reconstructed.
"""

from django.db import migrations, models
from django.db.models import Count


def collapse_duplicate_memberships(apps, schema_editor):
    WorkflowMember = apps.get_model("chains", "WorkflowMember")
    duplicates = (
        WorkflowMember.objects.values("user_id")
        .annotate(total=Count("id"))
        .filter(total__gt=1)
    )
    for duplicate in duplicates:
        rows = list(
            WorkflowMember.objects.filter(user_id=duplicate["user_id"])
            .select_related("workflow", "team")
            .order_by("pk")
        )
        if len(rows) < 2:
            continue

        def rank(membership):
            team = membership.team
            routes_here = (
                team is not None and team.workflow_id == membership.workflow_id
            )
            return (0 if routes_here else 1, membership.created_at, membership.pk)

        keep = sorted(rows, key=rank)[0]
        WorkflowMember.objects.filter(
            pk__in=[row.pk for row in rows if row.pk != keep.pk]
        ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("chains", "0032_workflow_effective_to_and_more"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="workflowmember",
            name="workflow_member_team_user_unique",
        ),
        migrations.RemoveConstraint(
            model_name="workflowmember",
            name="workflow_member_workflow_user_unique",
        ),
        migrations.RunPython(
            collapse_duplicate_memberships, migrations.RunPython.noop
        ),
        migrations.AddConstraint(
            model_name="workflowmember",
            constraint=models.UniqueConstraint(
                fields=("user",), name="workflow_member_user_unique"
            ),
        ),
        migrations.AlterField(
            model_name="workflowmember",
            name="is_wide_approver",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Denormalised from the wide-approver holdings "
                    "(institution-wide, team-wide on this team, or campus-wide "
                    "at this team's campus) at the time the membership was "
                    "written, so the roster can say who serves several chains "
                    "as an approver. It is informational only: membership "
                    "itself is one workflow per employee, wide or not. "
                    "Eligibility is always re-checked against the live "
                    "holdings."
                ),
            ),
        ),
    ]
