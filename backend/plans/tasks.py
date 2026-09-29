"""Periodic plan housekeeping (Unit 25, D10/D11).

Two idempotent jobs are safe to run daily and safe to run in parallel:

* :func:`lapse_overdue_blocks` — unconfirmed reserved blocks lapse at their
  start date and the reserved capacity is released (always safe to re-run).
* :func:`send_plan_block_confirmation_reminders` — employees whose blocks just
  entered their confirmation window get one reminder email each (outbox rows
  make the job idempotent).

Operators can schedule this as a django-q2 cron task:

    schedule("plans.tasks.run_plan_housekeeping", schedule_type=cron,
             cron="0 6 * * *")

or invoke it via ``manage.py run_plan_housekeeping``.
"""

from __future__ import annotations


def run_plan_housekeeping(*args, **kwargs):
    from notifications.plans import send_plan_block_confirmation_reminders
    from plans.services import lapse_overdue_blocks

    lapsed = lapse_overdue_blocks()
    reminders = send_plan_block_confirmation_reminders()
    return {"lapsed": lapsed, "reminders": reminders}