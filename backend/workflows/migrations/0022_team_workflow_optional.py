"""Let a draft team exist before its approval chain.

``0016_require_team_workflow`` made ``Team.workflow`` non-null, and it was right
at the time: a team was created and configured in one request, so a team with no
chain could only ever be a half-written one.

HR now configures a team in two steps — the department and name first, the
approval chain second — and the first step is persisted rather than held in the
browser. So a draft team legitimately has no chain for the length of one
conversation.

The relaxation is safe because the two states cannot overlap: a team only routes
when :attr:`Team.status` is ``active``, activation validates the chain first and
refuses a team without one, and ``DatabaseWorkflowProvider`` already refuses to
build a chain from ``None``. A chainless team is therefore a team HR is still
working on, never one that silently approves nothing. ``0016`` is left applied —
its guard did its job on the data that existed then, and this migration is the
recorded decision to reverse part of it.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("workflows", "0021_section_single_approver"),
    ]

    operations = [
        migrations.AlterField(
            model_name="team",
            name="workflow",
            field=models.OneToOneField(
                blank=True,
                help_text=(
                    "The approval workflow this team is routed through. One-to-one, "
                    "not a foreign key: a chain belongs to the team it was built "
                    "for, and a shared chain would mean editing one team's steps "
                    "silently re-routing every other team pointing at it. It owns "
                    "the sections, so its steps define who may act for this team. "
                    "Blank only while the team is still a draft being configured."
                ),
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="team",
                to="workflows.workflow",
            ),
        ),
    ]