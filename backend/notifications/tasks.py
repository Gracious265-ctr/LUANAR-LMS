"""django-q2 delivery task (Unit 22, section 3).

``deliver_notification`` locks the row, bumps ``attempts``, sends the mail with
``fail_silently=False`` and flips status to ``sent``/``failed`` with the error.
Re-running an already-sent row is a no-op so a worker retry never duplicates
mail. Send failures are recorded on the row, not swallowed, so HR sees them.
"""

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import Notification


def deliver_notification(notification_id: int):
    """Deliver ``Notification`` with ``pk``; returns the final status string."""
    row = Notification.objects.select_for_update().get(pk=notification_id)
    if row.status == Notification.Status.SENT:
        return row.status

    row.attempts += 1
    row.save(update_fields=["attempts"])

    if not (settings.EMAIL_HOST_USER and settings.EMAIL_HOST_PASSWORD):
        row.status = Notification.Status.FAILED
        row.error = (
            "SMTP not configured (EMAIL_HOST_USER / EMAIL_HOST_PASSWORD empty)."
        )
        row.save(update_fields=["status", "error"])
        return row.status

    try:
        send_mail(
            row.subject,
            row.body,
            settings.DEFAULT_FROM_EMAIL,
            [row.email_to],
            fail_silently=False,
        )
    except Exception as exc:  # noqa: BLE001 - a failed send must never crash the worker
        row.status = Notification.Status.FAILED
        row.error = str(exc)
        row.save(update_fields=["status", "error"])
        return row.status

    row.status = Notification.Status.SENT
    row.sent_at = timezone.now()
    row.save(update_fields=["status", "sent_at"])
    return row.status