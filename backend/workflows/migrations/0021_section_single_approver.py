"""Give every section exactly one approver.

A section used to hold any number of members and be resolved by whoever acted
first. Stages execute in order and a stage is either decided or it is not, so
there is one person responsible for it, and "the first of three to click" is not
a rule anybody can write down for a colleague.

The new ``Section.approver`` is the configured answer; the ``SectionMember``
rows stay as the effective-dated record of who held the step and when. The
backfill therefore copies, it does not move anything: where a section had
several open members, the one whose period started earliest (lowest id to break
a tie) becomes the approver, and the rest are left in place as history rather
than deleted. A section with no open member stays null, which the owning team's
readiness check reports as unstaffed.

Nothing is destroyed here, and the old rows stay authoritative for
``resolve_section_approvers`` while an approver is null, so a configuration that
predates this migration keeps routing exactly as it did.
"""

from django.db import migrations, models
from django.conf import settings
import django.db.models.deletion


def backfill_section_approvers(apps, schema_editor):
    """Point each section at the person whose open membership started first."""
    Section = apps.get_model("workflows", "Section")
    # ``objects`` here is Django's plain manager, not the open-only one: a
    # migration's historical models keep only managers that opted in with
    # ``use_in_migrations``, so the "is it open" question is asked explicitly
    # rather than left to a manager this migration cannot rely on.
    SectionMember = apps.get_model("workflows", "SectionMember")

    for section in Section.objects.filter(approver__isnull=True).order_by("pk"):
        earliest = (
            SectionMember.objects.filter(section_id=section.pk, effective_to=None)
            .order_by("effective_from", "pk")
            .values_list("user_id", flat=True)
            .first()
        )
        if earliest is None:
            continue
        Section.objects.filter(pk=section.pk).update(approver_id=earliest)


def noop(apps, schema_editor):
    """Not reversible: the derived mapping has no stored inverse."""


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("workflows", "0020_team_department_reference"),
    ]

    operations = [
        migrations.AddField(
            model_name="section",
            name="approver",
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    "The single person who approves this step. Must be in the "
                    "owning team's department, and must already hold the role "
                    "above for that department. Blank means the step is not "
                    "staffed yet, which the team's readiness check reports and "
                    "activation refuses."
                ),
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="approver_sections",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="section",
            name="approver_role",
            field=models.ForeignKey(
                help_text=(
                    "The role this section's approver acts as. Held on the section "
                    "rather than on the approver so the snapshot an in-flight "
                    "application is judged by is fixed when the chain is "
                    "materialised."
                ),
                on_delete=django.db.models.deletion.PROTECT,
                related_name="sections",
                to="workflows.approverrole",
            ),
        ),
        migrations.RunPython(backfill_section_approvers, noop),
    ]