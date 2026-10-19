"""Convert historical return-for-correction rows to the rejection flow.

The return-for-correction flow was removed in favour of reject + resubmit.
Applications that were ``correction_required`` become ``rejected``, and the
stage that returned them plus the decision recorded against it become
``rejected`` / ``reject``. Audit entries are deliberately left untouched: the
audit log is an immutable historical record, so rows written while the old flow
existed keep their original ``correction_requested`` action.
"""

from django.db import migrations

CORRECTION_REQUESTED = "correction_requested"
RETURN_FOR_CORRECTION = "return_for_correction"
CORRECTION_REQUIRED = "correction_required"
REJECTED = "rejected"
REJECT = "reject"


def forwards(apps, schema_editor):
    LeaveApplication = apps.get_model("leave", "LeaveApplication")
    ApplicationStage = apps.get_model("approvals", "ApplicationStage")
    ApprovalDecision = apps.get_model("approvals", "ApprovalDecision")

    LeaveApplication.objects.filter(status=CORRECTION_REQUIRED).update(
        status=REJECTED
    )
    ApplicationStage.objects.filter(status=CORRECTION_REQUESTED).update(
        status=REJECTED
    )
    ApprovalDecision.objects.filter(action=RETURN_FOR_CORRECTION).update(
        action=REJECT
    )


def backwards(apps, schema_editor):
    """Irreversible in substance: reject and correction re-use the same values.

    Reversing the statuses would be ambiguous (a genuine rejection would be
    indistinguishable from a converted correction), so this is a deliberate
    no-op.
    """


class Migration(migrations.Migration):

    dependencies = [
        ("leave", "0022_alter_leaveapplication_status"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
