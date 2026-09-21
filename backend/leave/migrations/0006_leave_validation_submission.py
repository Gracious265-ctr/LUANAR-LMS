from datetime import date

from django.db import migrations, models


def clear_reference_sequences(apps, schema_editor):
    """Drop any legacy ReferenceSequence rows before reshaping the table.

    The old rows are purely counters for the ``LUANAR-{year}`` reference format
    that is being retired in favour of per-financial-year ``LV-`` sequences
    (Unit 14, decision D8). Existing reference numbers are already stamped on
    their applications, so the counters have no value to preserve.
    """
    ReferenceSequence = apps.get_model("leave", "ReferenceSequence")
    ReferenceSequence.objects.all().delete()


class Migration(migrations.Migration):
    """Unit 14: submission fields on LeaveApplication + ReferenceSequence reshape."""

    dependencies = [
        ("leave", "0005_leaveapplication_current_approver"),
    ]

    operations = [
        migrations.RunPython(clear_reference_sequences, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="referencesequence",
            name="year",
        ),
        migrations.RemoveField(
            model_name="referencesequence",
            name="last_number",
        ),
        migrations.AddField(
            model_name="referencesequence",
            name="financial_year_label",
            field=models.CharField(max_length=16, unique=True),
        ),
        migrations.AddField(
            model_name="referencesequence",
            name="last_value",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="leaveapplication",
            name="working_days",
            field=models.PositiveSmallIntegerField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="leaveapplication",
            name="calendar_days",
            field=models.PositiveSmallIntegerField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="leaveapplication",
            name="financial_year_label",
            field=models.CharField(max_length=16, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="leaveapplication",
            name="rules_snapshot",
            field=models.JSONField(null=True, blank=True),
        ),
    ]