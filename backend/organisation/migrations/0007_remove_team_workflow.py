"""Drop the single ``Team.workflow`` routing pointer.

A team may own several chains and each one can be in force at the same time,
so "the workflow this team routes through" stopped being a property of the
team. Routing is resolved per applicant from their
:class:`workflows.models.WorkflowMember` membership instead, which is what
lets two people on the same team sit in two different chains at once.

The workflows themselves are untouched: they are still owned by the team
through ``Workflow.team``, so nothing that was pointed at here disappears.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("organisation", "0006_alter_team_status"),
        ("workflows", "0034_workflow_effective_to_and_more"),
    ]

    operations = [
        migrations.RemoveField(model_name="team", name="workflow"),
    ]
