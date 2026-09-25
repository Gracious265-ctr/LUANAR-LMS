"""Append-only notification outbox (Unit 22, D2/D5).

Each row is one decision email — the delivery record for a single
``(application, kind, submission_cycle, role_label)`` notification.

* **Append-only** — queryset-wide ``update``/``delete`` are rejected, mirroring
  the balance-ledger discipline. Row state moves ``pending → sent|failed`` only
  through the model's own transition methods, never through the queryset.
* **Idempotent** — the unique constraint means a re-emitted event (after a
  reconnect or replay) matches the existing row and never sends a second email.
* **Same vocabulary** — state values ``pending`` / ``sent`` / ``failed`` reuse
  the delivery vocabulary already pinned in Unit 18's
  ``CancellationRequest.NotificationState``; nothing new is invented.
"""

from __future__ import annotations

import uuid

from django.db import models
from django.utils import timezone


class NotificationOutboxLockedError(Exception):
    """Raised on any append-only outbox violation (queryset update/delete)."""


class NotificationOutboxQuerySet(models.QuerySet):
    """Append-only outbox queryset; queryset-wide mutation is rejected."""

    def update(self, *args, **kwargs):  # noqa: A003
        raise NotificationOutboxLockedError(
            "Notification outbox is append-only and cannot be updated en masse."
        )

    def delete(self):  # noqa: A003
        raise NotificationOutboxLockedError(
            "Notification outbox is append-only and cannot be deleted en masse."
        )


class NotificationOutboxManager(models.Manager.from_queryset(NotificationOutboxQuerySet)):
    """Append-only outbox manager (Unit 22 D5)."""


class NotificationOutbox(models.Model):
    """One email notification record for one decision, cycle and stage role."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        "leave.LeaveApplication",
        on_delete=models.PROTECT,
        related_name="notification_outbox_rows",
    )
    kind = models.CharField(max_length=32, db_index=True)
    submission_cycle = models.PositiveSmallIntegerField(default=1)
    role_label = models.CharField(max_length=32, default="")
    recipient_email = models.EmailField()
    subject = models.CharField(max_length=200, default="")
    body = models.TextField(default="")
    state = models.CharField(
        max_length=16,
        choices=(
            ("pending", "Pending"),
            ("sent", "Sent"),
            ("failed", "Failed"),
        ),
        default="pending",
    )
    error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    objects = NotificationOutboxManager()

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["application", "kind", "submission_cycle", "role_label"],
                name="one_outbox_row_per_application_kind_cycle_role",
            )
        ]

    def __str__(self) -> str:
        return f"{self.kind}/{self.role_label} → {self.state} ({self.recipient_email})"

    def mark_sent(self):
        """pending → sent (idempotent; later calls are no-ops)."""
        if self.state != "pending":
            return self
        self.state = "sent"
        self.sent_at = timezone.now()
        self.save(update_fields=["state", "sent_at"])
        return self

    def mark_failed(self, error: str):
        """pending → failed, recording why (idempotent; later calls are no-ops)."""
        if self.state != "pending":
            return self
        self.state = "failed"
        self.error = (error or "")[:2000]
        self.save(update_fields=["state", "error"])
        return self
