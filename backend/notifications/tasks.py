<<<<<<< HEAD
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
=======
"""Delivery of queued notification emails (django-q2 dispatch).

Dispatch via: ``async_task("notifications.tasks.deliver_notification", row_id,
recipients)`` — enqueued on commit by :func:`enqueue_delivery`, so mail only
starts once the decision, delegation, reassignment, confirmation or cancellation
that produced it is durable.

This module is the **only** place the backend calls ``send_mail``. Every
composer (``services``, ``delegations``, ``reassignments``, ``plans``,
``cancellations``) writes an outbox row and hands it here, which is what keeps
the retry policy, the recipient override and the failure record in one place.

Two properties matter:

* **Idempotent** — the row is re-read, and a row that is no longer ``pending`` is
  a no-op, so a worker restart, a re-broadcast or a second run of the daily job
  can never send the same notification twice.
* **Isolated** — a delivery failure records ``failed`` plus the error on the row
  and is logged. It never propagates: the decision the mail describes has already
  committed, and a dead relay must not undo it.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction

from notifications.models import NotificationOutbox
from notifications.services import LEAVE_DOMAIN

logger = logging.getLogger(__name__)


def _register_cancellation_consumer() -> None:
    """Attach the cancellation composer to the cancellation bus.

    Idempotent: ``register_consumer`` refuses a duplicate registration, which is
    exactly what a second ``ready()`` in the same process should hit, so it is
    treated as "already wired" rather than an error.
    """
    from notifications.cancellations import register_cancellation_email_consumer

    try:
        register_cancellation_email_consumer()
    except ValueError:
        logger.debug("Cancellation email consumer is already registered.")


_register_cancellation_consumer()


class NotificationConfigurationError(Exception):
    """Raised when the mail transport is configured in a way that cannot send."""


def _uses_smtp() -> bool:
    """True when a real relay is behind ``EMAIL_BACKEND``."""
    return "smtp" in str(getattr(settings, "EMAIL_BACKEND", "")).lower()


def _from_email() -> str:
    """The ``From:`` address, refusing a configuration a relay will reject.

    Gmail (and most relays) refuse a ``From:`` the account is not authorised to
    send as. The composers' ``no-reply@luanar.ac.mw`` fallback is fine on the
    console backend, where nothing is sent at all, but against SMTP it produces a
    550 per message and an outbox full of failures nobody asked for — so this
    fails loudly, and the row records why.
    """
    configured = str(getattr(settings, "DEFAULT_FROM_EMAIL", "") or "")
    if configured:
        return configured
    if _uses_smtp():
        raise NotificationConfigurationError(
            "DEFAULT_FROM_EMAIL is not set, so a real SMTP backend would reject "
            "the From: header. Set it to an address the account is authorised to "
            "send as (see .env.example)."
        )
    return f"no-reply@{LEAVE_DOMAIN}"


def _resolve_recipients(recipients: list[str]) -> list[str]:
    """Apply the development-only recipient override, if one is active.

    The seeded users carry ``@test.luanar`` addresses, so a live SMTP smoke test
    would fail on every recipient; the override routes the mail into one real
    inbox instead. It is honoured only under ``DEBUG`` — outside it the setting is
    refused and the real recipients are used, so a wrong recipient can never be
    masked in production.
    """
    override = list(getattr(settings, "EMAIL_DEV_RECIPIENT_OVERRIDE", []) or [])
    if not override:
        return list(recipients)
    if not settings.DEBUG:
        logger.error(
            "EMAIL_DEV_RECIPIENT_OVERRIDE is set but DEBUG is off; ignoring it "
            "and delivering to the real recipients instead."
        )
        return list(recipients)
    logger.warning(
        "EMAIL_DEV_RECIPIENT_OVERRIDE is active (DEBUG): delivering %d "
        "notification(s) to %s instead of the real recipients.",
        len(recipients),
        ", ".join(override),
    )
    return override


def deliver_notification(outbox_id, recipients=None) -> str:
    """Deliver one outbox row; record ``sent``/``failed`` on it.

    ``recipients`` carries the full list when it is wider than the row's primary
    ``recipient_email`` — the finalise decision goes to the owner *and* the
    approver who finalised, while the row records the owner as its subject. A
    missing argument falls back to the row's own recipient.

    Returns the resulting ``state``, so a caller (or a test) can assert on it.
    """
    row = NotificationOutbox.objects.filter(pk=outbox_id).first()
    if row is None:
        logger.error(
            "Notification outbox row %s no longer exists; nothing delivered.", outbox_id
        )
        return "missing"
    if row.state != "pending":
        return row.state  # already delivered, or permanently failed

    recipient_list = _resolve_recipients(list(recipients or [row.recipient_email]))

    try:
        send_mail(
            subject=row.subject,
            message=row.body,
            from_email=_from_email(),
            recipient_list=recipient_list,
            fail_silently=False,
        )
    except Exception as exc:  # noqa: BLE001 — delivery isolation
        logger.exception(
            "Notification delivery failed for %s/%s to %s",
            row.kind,
            row.pk,
            row.recipient_email,
        )
        row.mark_failed(str(exc))
        _reconcile_subject(row)
        return row.state

    row.mark_sent()
    _reconcile_subject(row)
    return row.state


def _reconcile_subject(row) -> None:
    """Mirror the delivery outcome onto the subject's own notification state.

    Only the cancellation family keeps a second, user-facing state column
    (``CancellationRequest.employee_notification_state``), which the API surfaces;
    reconciling it here keeps the outbox and the request from ever disagreeing.
    Failure isolation applies here too — a reconciliation error is logged, never
    raised, and never undoes a sent message.
    """
    if row.cancellation_id is None:
        return
    from notifications.cancellations import confirm_cancellation_delivery

    try:
        confirm_cancellation_delivery(row.pk)
    except Exception:  # noqa: BLE001 — bookkeeping must not fail a delivery
        logger.exception(
            "Could not reconcile the notification state for cancellation %s.",
            row.cancellation_id,
        )


def enqueue_delivery(row, recipients=None) -> None:
    """Queue delivery of one outbox row once the transaction has committed.

    The broker is not a business dependency: if it is unreachable the exception is
    logged and swallowed, the row stays ``pending``, and the decision it describes
    still stands. ``NOTIFICATIONS_SYNC_SEND`` runs the delivery inline instead,
    which is what a single-process development server needs.
    """
    from django_q.tasks import async_task

    row_id = row.pk if hasattr(row, "pk") else row
    recipient_list = [str(address) for address in (recipients or [])]

    def _dispatch() -> None:
        try:
            async_task(
                "notifications.tasks.deliver_notification",
                row_id,
                recipient_list,
                sync=bool(getattr(settings, "NOTIFICATIONS_SYNC_SEND", False)),
            )
        except Exception:  # noqa: BLE001 — a broker outage is not a decision failure
            logger.exception(
                "Could not enqueue notification delivery for outbox row %s; it "
                "stays pending until a worker picks it up.",
                row_id,
            )

    transaction.on_commit(_dispatch)
>>>>>>> feature/plans-teams
