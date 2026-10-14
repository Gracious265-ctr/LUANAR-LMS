"""Backfill the cancellation stage eligibility snapshot.

A cancellation stage used to name a single assigned approver, and authority was
equality with that one person. Cancellation stages are now sections: the source
``ApplicationStage``'s ``eligible_approvers`` snapshot is copied here at request
time and any member of it may decide.

Existing open stages therefore have an ``approver`` but no eligibility rows, and
under the new rule nobody would be entitled to act on them — an in-flight request
would be stuck. The reverse migration handles the reverse case: a stage decided
before this change has a claimer but possibly several snapshot members, so
``approver`` is restored to the lowest snapshot id to keep the column non-null.

The data step is written for both directions because the set is a superset of the
old single person in every case, so no approver loses access to a stage they were
already given.
"""

from django.db import migrations


def backfill(apps, schema_editor):
    Stage = apps.get_model("leave", "CancellationApprovalStage")
    StageApprover = apps.get_model("leave", "CancellationStageApprover")
    db_alias = schema_editor.connection.alias
    StageApprover.objects.using(db_alias).bulk_create(
        [
            StageApprover(stage_id=stage_id, user_id=user_id)
            for stage_id, user_id in Stage.objects.using(db_alias)
            .exclude(approver_id=None)
            .values_list("id", "approver_id")
        ],
        ignore_conflicts=True,
    )


def restore_single_approver(apps, schema_editor):
    """Reinstate one approver per stage before the constraint is reapplied.

    Deferred until after ``0015`` is unapplied is not possible, so the
    ``AlterField`` that makes the column non-null runs first in reverse order;
    this only has to leave the column holding a plausible single value.
    """
    Stage = apps.get_model("leave", "CancellationApprovalStage")
    db_alias = schema_editor.connection.alias
    for stage in (
        Stage.objects.using(db_alias)
        .filter(approver_id=None)
        .order_by("pk")
    ):
        lowest = (
            stage.eligible_approvers.using(db_alias)
            .order_by("user_id")
            .values_list("user_id", flat=True)
            .first()
        )
        if lowest is not None:
            stage.approver_id = lowest
            stage.save(update_fields=["approver"], using=db_alias)


class Migration(migrations.Migration):

    dependencies = [
        ("leave", "0015_alter_cancellationapprovalstage_approver_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill, restore_single_approver),
    ]
