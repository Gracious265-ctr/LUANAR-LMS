"""Append-only notification outbox (Unit 22, D2/D5).

Each row is one email — the delivery record for a single subject/party pair:
a leave decision (``application``), a delegation lifecycle event
(``delegation``), a reassignment (``reassignment``), a leave day plan
(``plan``/``plan_block``), a cancellation (``cancellation``), or an account
login itself (``user``).

* **Append-only** — queryset-wide ``update``/``delete`` are rejected, mirroring
  the balance-ledger discipline. Row state moves ``pending → sent|failed`` only
  through the model's own transition methods, never through the queryset.
* **Idempotent** — a partial unique constraint per subject family means a
  re-emitted event (after a reconnect or replay) matches the existing row and
  never sends a second email. The one deliberate exception is the account
  family, where each issuance of a link is its own row.
* **Same vocabulary** — state values ``pending`` / ``sent`` / ``failed`` reuse
  the delivery vocabulary already pinned in Unit 18's
  ``CancellationRequest.NotificationState``; nothing new is invented.
"""

from __future__ import annotations

import uuid

from django.conf import settings
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
    """One email notification record for one decision, cycle and stage role.

    Exactly one subject is set per row: ``application`` for a leave decision,
    ``delegation`` for a delegation lifecycle event, or ``reassignment`` for an
    HR intervention. A row therefore always has one authoritative thing to point
    at, and the subject families are constrained separately so idempotency never
    collides across them.

    A reassignment needs its own subject rather than riding on ``application``:
    an application can be reassigned several times in one submission cycle, and
    the application constraint is unique per ``(application, kind, cycle, role)``,
    so a second reassignment would silently match the first row and send nothing.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        "leave.LeaveApplication",
        on_delete=models.PROTECT,
        related_name="notification_outbox_rows",
        null=True,
        blank=True,
    )
    delegation = models.ForeignKey(
        "org.Delegation",
        on_delete=models.PROTECT,
        related_name="notification_outbox_rows",
        null=True,
        blank=True,
    )
    reassignment = models.ForeignKey(
        "workflows.Reassignment",
        on_delete=models.PROTECT,
        related_name="notification_outbox_rows",
        null=True,
        blank=True,
    )
    plan = models.ForeignKey(
        "plans.LeaveDayPlan",
        on_delete=models.PROTECT,
        related_name="notification_outbox_rows",
        null=True,
        blank=True,
    )
    plan_block = models.ForeignKey(
        "plans.LeavePlanBlock",
        on_delete=models.PROTECT,
        related_name="notification_outbox_rows",
        null=True,
        blank=True,
    )
    cancellation = models.ForeignKey(
        "leave.CancellationRequest",
        on_delete=models.PROTECT,
        related_name="notification_outbox_rows",
        null=True,
        blank=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="notification_outbox_rows",
        null=True,
        blank=True,
        help_text="The account this email concerns. Only the account family uses it: "
        "a password-set link is about the login itself and has no business subject.",
    )
    kind = models.CharField(max_length=32, db_index=True)
    submission_cycle = models.PositiveSmallIntegerField(default=1)
    role_label = models.CharField(
        max_length=32,
        default="",
        help_text="Who the row concerns: the stage role for a decision email, "
        "'approver' / 'delegate' for a delegation email, "
        "'from_approver' / 'to_approver' for a reassignment email, "
        "'employee' or the workflow role for a cancellation email, "
        "'owner' for a leave day plan lifecycle email, or "
        "'account' for a password-set email.",
    )
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
            models.CheckConstraint(
                condition=(
                    models.Q(
                        application__isnull=False,
                        delegation__isnull=True,
                        reassignment__isnull=True,
                        plan__isnull=True,
                        plan_block__isnull=True,
                        cancellation__isnull=True,
                        user__isnull=True,
                    )
                    | models.Q(
                        application__isnull=True,
                        delegation__isnull=False,
                        reassignment__isnull=True,
                        plan__isnull=True,
                        plan_block__isnull=True,
                        cancellation__isnull=True,
                        user__isnull=True,
                    )
                    | models.Q(
                        application__isnull=True,
                        delegation__isnull=True,
                        reassignment__isnull=False,
                        plan__isnull=True,
                        plan_block__isnull=True,
                        cancellation__isnull=True,
                        user__isnull=True,
                    )
                    | models.Q(
                        application__isnull=True,
                        delegation__isnull=True,
                        reassignment__isnull=True,
                        plan__isnull=False,
                        plan_block__isnull=True,
                        cancellation__isnull=True,
                        user__isnull=True,
                    )
                    | models.Q(
                        application__isnull=True,
                        delegation__isnull=True,
                        reassignment__isnull=True,
                        plan__isnull=True,
                        plan_block__isnull=False,
                        cancellation__isnull=True,
                        user__isnull=True,
                    )
                    | models.Q(
                        application__isnull=True,
                        delegation__isnull=True,
                        reassignment__isnull=True,
                        plan__isnull=True,
                        plan_block__isnull=True,
                        cancellation__isnull=False,
                        user__isnull=True,
                    )
                    | models.Q(
                        application__isnull=True,
                        delegation__isnull=True,
                        reassignment__isnull=True,
                        plan__isnull=True,
                        plan_block__isnull=True,
                        cancellation__isnull=True,
                        user__isnull=False,
                    )
                ),
                name="one_notification_subject",
            ),
            # Partial so the nullable columns stay meaningful: a delegation or
            # reassignment row can never collide with an application row, and
            # PostgreSQL skips NULLs, so each family is unique only among its
            # own subject.
            models.UniqueConstraint(
                fields=["application", "kind", "submission_cycle", "role_label"],
                condition=models.Q(application__isnull=False),
                name="one_outbox_row_per_application_kind_cycle_role",
            ),
            models.UniqueConstraint(
                fields=["delegation", "kind", "role_label"],
                condition=models.Q(delegation__isnull=False),
                name="one_outbox_row_per_delegation_kind_role",
            ),
            models.UniqueConstraint(
                fields=["reassignment", "kind", "role_label"],
                condition=models.Q(reassignment__isnull=False),
                name="one_outbox_row_per_reassignment_kind_role",
            ),
            models.UniqueConstraint(
                fields=["plan", "kind", "submission_cycle", "role_label"],
                condition=models.Q(plan__isnull=False),
                name="one_outbox_row_per_plan_kind_cycle_role",
            ),
            models.UniqueConstraint(
                fields=["plan_block", "kind", "role_label"],
                condition=models.Q(plan_block__isnull=False),
                name="one_outbox_row_per_plan_block_kind_role",
            ),
            models.UniqueConstraint(
                fields=["cancellation", "kind", "role_label"],
                condition=models.Q(cancellation__isnull=False),
                name="one_outbox_row_per_cancellation_kind_role",
            ),
            # No unique constraint for the account family, and that is the point:
            # the other families are idempotent because re-emitting an event must
            # not send a second email, but reissuing a password-set link *must*
            # send another one. The single-use token is what guarantees a link
            # cannot be used twice, so the outbox keeps one row per issuance.
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
