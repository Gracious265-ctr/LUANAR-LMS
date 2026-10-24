"""Give every team a chain of its own.

A chain used to be a foreign key several teams could point at, which made
"edit this team's approval steps" and "re-route every other team that shares
the chain" the same action. Teams now own their chain one-to-one.

If a workflow is somehow shared, the extra teams are given a copy of it —
same steps, same roles, empty rosters — rather than being refused. A
migration that raised would leave the deployment stuck with the old schema
applied, and HR would have no way to fix the data because the standalone
workflow screens are gone: the copy keeps every team routing, and the empty
roster is visible in the team's own readiness check rather than silent.
"""

from django.db import migrations, models
import django.db.models.deletion


def split_shared_workflows(apps, schema_editor):
    Team = apps.get_model("chains", "Team")
    Workflow = apps.get_model("chains", "Workflow")
    Section = apps.get_model("chains", "Section")

    # ``workflow_id -> owning team id`` for every chain, so a duplicate can be
    # told apart from the first team that already owns it. The lowest team id
    # keeps the original chain; the rest are split off.
    owners: dict[int, int] = {}
    for team_id, workflow_id in Team.objects.values_list("id", "workflow_id").order_by(
        "id"
    ):
        owners.setdefault(workflow_id, team_id)

    for workflow_id, owner_team_id in list(owners.items()):
        duplicates = list(
            Team.objects.filter(workflow_id=workflow_id)
            .exclude(pk=owner_team_id)
            .order_by("pk")
        )
        for duplicate in duplicates:
            copy = Workflow.objects.create(
                name=f"{Workflow.objects.get(pk=workflow_id).name} ({duplicate.name})",
                employee_category="",
                department="",
                is_active=True,
            )
            for section in Section.objects.filter(workflow_id=workflow_id).order_by(
                "order"
            ):
                Section.objects.create(
                    workflow=copy,
                    name=section.name,
                    order=section.order,
                    approver_role_id=section.approver_role_id,
                    description=section.description,
                    is_active=section.is_active,
                )
            Team.objects.filter(pk=duplicate.pk).update(workflow=copy)


def noop_reverse(apps, schema_editor):
    """Not reversible: the copies would have to be merged back, losing the
    separation the forward migration exists to create."""


class Migration(migrations.Migration):

    dependencies = [
        ("chains", "0018_team_lifecycle_and_membership_history"),
    ]

    operations = [
        migrations.RunPython(split_shared_workflows, noop_reverse),
        migrations.AlterField(
            model_name="team",
            name="workflow",
            field=models.OneToOneField(
                help_text=(
                    "The approval workflow this team is routed through. One-to-one, "
                    "not a foreign key: a chain belongs to the team it was built "
                    "for, and a shared chain would mean editing one team's steps "
                    "silently re-routing every other team pointing at it. It owns "
                    "the sections, so its steps define who may act for this team."
                ),
                on_delete=django.db.models.deletion.PROTECT,
                related_name="team",
                to="chains.workflow",
            ),
        ),
    ]
