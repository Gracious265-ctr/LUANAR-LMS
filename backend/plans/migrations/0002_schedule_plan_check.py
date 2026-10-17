"""Register the daily Leave Plan check with django-q2.

The job is not wired through ``Q_CLUSTER`` config (which only describes the
worker, not what it runs): a ``django_q.Schedule`` row *is* the registration a
running cluster reads, so creating one on migrate is what makes the reminder job
actually fire. The row is created with ``next_run`` at deploy time and repeats
forever; the schedule itself is idempotent by ``func`` so re-running migrate never
stacks duplicates.
"""

from django.db import migrations

from django.utils import timezone

#: The task function the cluster will import. Must match
#: :func:`plans.tasks.check_and_notify_plans`.
SCHEDULE_FUNC = "plans.tasks.check_and_notify_plans"
SCHEDULE_NAME = "plans: check and notify"

#: ``Schedule.DAILY`` — hard-coded because historical models expose no constants.
DAILY = "D"


def create_schedule(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    Schedule.objects.filter(func=SCHEDULE_FUNC).delete()
    Schedule.objects.create(
        name=SCHEDULE_NAME,
        func=SCHEDULE_FUNC,
        schedule_type=DAILY,
        repeats=-1,
        next_run=timezone.now(),
    )


def remove_schedule(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    Schedule.objects.filter(func=SCHEDULE_FUNC).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("plans", "0001_initial"),
        ("django_q", "__latest__"),
    ]

    operations = [
        migrations.RunPython(create_schedule, remove_schedule),
    ]
