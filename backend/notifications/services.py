"""Notification service (Unit 22, section 2).

``send_notification`` persists one :class:`Notification` row per eligible
recipient (active user with an email address) and enqueues delivery through
django-q2. It never sends mail synchronously and never re-queries business
logic. Tests patch ``async_task`` or run ``deliver_notification`` directly;
``send_sync_callbacks`` lets a test (or dev tool) observe the created rows.
"""

from django_q.tasks import async_task

from users.models import User

from .models import Notification


def send_notification(
    *,
    event_type: str,
    recipients,
    subject: str,
    body: str,
    application_id=None,
    target_object_id=None,
    send_sync_callbacks=(),
):
    """Persist and enqueue one email per eligible recipient.

    ``recipients`` may be a sequence of users; inactive users and users
    without an email are skipped. Returns the created ``Notification`` rows.
    """
    user_ids = {user.pk for user in recipients}
    eligible = list(
        User.objects.filter(pk__in=user_ids, is_active=True).exclude(
            email__exact=""
        )
    )
    if not eligible:
        return []

    rows = [
        Notification.objects.create(
            event_type=event_type,
            recipient=user,
            email_to=user.email,
            subject=subject,
            body=body,
            application_id=application_id,
            target_object_id=target_object_id,
        )
        for user in eligible
    ]

    for row in rows:
        async_task("notifications.tasks.deliver_notification", row.id)

    for callback in send_sync_callbacks:
        callback(rows)

    return rows