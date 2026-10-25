"""Introduce sections: a workflow's steps now own their approvers.

Step 1 of 3. 0014 copies the data across, 0015 drops the tables it replaced.
Splitting it this way is what lets the backfill in 0014 be reversible and lets
the application run against either shape depending on how far the sequence has
been applied.

What changes in the model:

* ``Section`` replaces ``WorkflowStage``. Same job — one mandatory step in
  approval order, naming an approver role — plus a ``name`` HR can read, and an
  ``is_active`` flag so a step can be stood down without deleting it.
* ``SectionMember`` replaces ``TeamMember``. A section may hold *any number* of
  people and the same person may hold several sections, so both of the old
  uniqueness constraints are gone: ``teammember_team_role_unique`` (one holder
  per role) existed only to make a single-person resolution unambiguous, which
  is exactly what a section no longer assumes, and ``teammember_team_user_unique``
  (one role per person per team) is replaced by
  ``sectionmember_section_user_unique`` (not twice in the *same* section).
* ``ApplicationStageApprover`` is new, and is the reason this is not just a
  rename. A section is decided by whichever member acts first, so entitlement to
  act is a set. It is snapshotted per stage at materialisation, which is what
  keeps an in-flight application unaffected by later membership edits
  (invariant 12.5) and what makes self-approval impossible rather than merely
  unlikely.
* ``ApplicationStage.assigned_approver`` becomes nullable and gains
  ``section_ref``. It no longer records "the person responsible", which was only
  well defined when a step had exactly one; it records who *actually* decided,
  and is null while a section is still open.

``WorkflowStage`` and ``TeamMember`` are left in place here — still populated,
still consistent — and are dropped in 0015.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("chains", "0012_role_foreign_keys"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Section",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        help_text="What this step is for, as HR labels it (e.g. 'Departmental review').",
                        max_length=200,
                    ),
                ),
                ("order", models.PositiveIntegerField()),
                ("description", models.TextField(blank=True, default="")),
                ("is_active", models.BooleanField(default=True)),
                (
                    "approver_role",
                    models.ForeignKey(
                        help_text=(
                            "The role this section's members act as. Held on the "
                            "section rather than on each member so the snapshot an "
                            "in-flight application is judged by is fixed when the "
                            "chain is materialised."
                        ),
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="sections",
                        to="chains.approverrole",
                    ),
                ),
                (
                    "workflow",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sections",
                        to="chains.workflow",
                    ),
                ),
            ],
            options={"ordering": ["order"]},
        ),
        migrations.CreateModel(
            name="SectionMember",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "section",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="members",
                        to="chains.section",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="section_memberships",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["section", "user"]},
        ),
        migrations.CreateModel(
            name="ApplicationStageApprover",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "stage",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="eligible_approvers",
                        to="chains.applicationstage",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="stage_eligibility",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"db_table": "workflows_applicationstageapprover", "ordering": ["stage", "user"]},
        ),
        migrations.AddIndex(
            model_name="applicationstageapprover",
            index=models.Index(fields=["user"], name="idx_stage_elig_user"),
        ),
        migrations.AddConstraint(
            model_name="applicationstageapprover",
            constraint=models.UniqueConstraint(
                fields=("stage", "user"), name="stageapprover_stage_user_unique"
            ),
        ),
        migrations.AddConstraint(
            model_name="section",
            constraint=models.CheckConstraint(
                condition=models.Q(("order__gte", 1)), name="section_order_gte_1"
            ),
        ),
        migrations.AddConstraint(
            model_name="section",
            constraint=models.UniqueConstraint(
                fields=("workflow", "order"), name="section_workflow_order_unique"
            ),
        ),
        migrations.AddConstraint(
            model_name="sectionmember",
            constraint=models.UniqueConstraint(
                fields=("section", "user"),
                name="sectionmember_section_user_unique",
            ),
        ),
        migrations.AddField(
            model_name="applicationstage",
            name="section_ref",
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    "The live section this stage was materialised from. Null only "
                    "for rows written before sections existed; the snapshotted role "
                    "fields stay authoritative in that case. Kept for traceability "
                    "— not for reading behaviour."
                ),
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="application_stages",
                to="chains.section",
            ),
        ),
        migrations.AlterField(
            model_name="applicationstage",
            name="assigned_approver",
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    "The member of the stage's section who actually decided it, or "
                    "who claimed it by acting. Null while the stage is still open, "
                    "because a section is resolved by whoever acts first — the "
                    "people entitled to act are the eligible_approvers snapshot, "
                    "not this field."
                ),
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="application_stages",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
