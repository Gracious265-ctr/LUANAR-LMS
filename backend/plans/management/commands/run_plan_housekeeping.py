"""Invoke plan housekeeping once (lapse overdue blocks + confirmation emails)."""

from django.core.management.base import BaseCommand

from plans.tasks import run_plan_housekeeping


class Command(BaseCommand):
    help = "Lapse overdue plan blocks and send confirmation reminders."

    def handle(self, *args, **options):
        result = run_plan_housekeeping()
        self.stdout.write(
            self.style.SUCCESS(
                f"Lapsed {result['lapsed']} overdue block(s); "
                f"queued {result['reminders']} confirmation reminder(s)."
            )
        )