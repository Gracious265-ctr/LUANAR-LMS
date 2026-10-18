"""A team is in force from creation, so the legacy ``draft`` status is retired.

``0006`` narrowed ``Team.status`` to ``active``/``inactive`` but left existing
rows alone: any team still carrying the old ``draft`` value would render as its
own raw code and would not be counted as in force. Creating a team *is* putting
it in force, so every surviving ``draft`` row simply becomes ``active``.
"""

from django.db import migrations


def draft_to_active(apps, schema_editor):
    Team = apps.get_model("organisation", "Team")
    Team.objects.filter(status="draft").update(status="active")


class Migration(migrations.Migration):

    dependencies = [
        ("organisation", "0007_remove_team_workflow"),
    ]

    operations = [
        migrations.RunPython(draft_to_active, migrations.RunPython.noop),
    ]
