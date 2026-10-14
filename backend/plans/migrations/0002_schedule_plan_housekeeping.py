"""Seed the django-q2 cron entry for plan housekeeping (Unit 25, D10/D11).

``plans.tasks.run_plan_housekeeping`` lapses overdue blocks and sends
confirmation reminders, and both halves are idempotent, so a daily schedule is
enough. The schedule is a *database* row: without it the jobs only ever run when
an operator calls them by hand, which is how reminder emails went missing.

Created with ``update_or_create`` on ``name`` so the migration is reversible and
re-runnable, and so a deploy that already edited the schedule does not clobber it.
Cron runs at 06:00 Africa/Blantyre — after the working day, before anyone reads
the reminder.
"""

from django.db import migrations

SCHEDULE_NAME = "plans housekeeping"
HOUSEKEEPING_FUNC = "plans.tasks.run_plan_housekeeping"
HOUSEKEEPING_CRON = "0 6 * * *"
#: ``django_q.models.Schedule.CRON``. Spelled out because a historical model in a
#: data migration carries only the fields, not the enum class attributes.
SCHEDULE_TYPE_CRON = "C"


def create_housekeeping_schedule(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    Schedule.objects.update_or_create(
        name=SCHEDULE_NAME,
        defaults={
            "func": HOUSEKEEPING_FUNC,
            "schedule_type": SCHEDULE_TYPE_CRON,
            "cron": HOUSEKEEPING_CRON,
            "repeats": -1,
        },
    )


def delete_housekeeping_schedule(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    Schedule.objects.filter(name=SCHEDULE_NAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("django_q", "0001_initial"),
        ("plans", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            create_housekeeping_schedule,
            delete_housekeeping_schedule,
        ),
    ]
