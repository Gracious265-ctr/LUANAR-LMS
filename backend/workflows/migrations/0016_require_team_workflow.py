"""Make ``Team.workflow`` required.

A team with no workflow cannot route an application, so the optional column only
ever produced a team HR believed was configured while silently approving
nothing. This is the database-level version of that decision: the FK is no
longer nullable.

Every existing team already points at a workflow, so the alter is a plain
``NOT NULL`` with no data step. The guard below exists anyway: if a deployment
ever does have such a team, the migration refuses with a message naming the
offending rows rather than picking a workflow on the team's behalf, because
guessing here would wire a team into a chain nobody chose for it.
"""

from django.db import migrations, models
from django.db.models import ForeignKey


def guard_no_unrouted_teams(apps, schema_editor):
    Team = apps.get_model("workflows", "Team")
    orphans = list(
        Team.objects.filter(workflow__isnull=True).values_list("name", "code")
    )
    if orphans:
        raise RuntimeError(
            "Cannot make Team.workflow required: "
            + ", ".join(f"{name} ({code})" for name, code in orphans)
            + " have no workflow, so they cannot route an application. Point each "
            "at the workflow it should use, or delete it, then re-run."
        )


class Migration(migrations.Migration):

    dependencies = [
        ("workflows", "0015_drop_workflow_stages"),
    ]

    operations = [
        migrations.RunPython(guard_no_unrouted_teams, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="team",
            name="workflow",
            field=ForeignKey(
                on_delete=models.PROTECT,
                related_name="teams",
                to="workflows.workflow",
                help_text=(
                    "The approval workflow this team is routed through. It owns "
                    "the sections, so its steps define who may act for this team."
                ),
            ),
        ),
    ]
