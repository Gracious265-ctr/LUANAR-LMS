"""Unit 18 data model: cancellation requests, stages, and the balance ledger.

Models live under ``leave``'s app label (like ``workflows.ApplicationStage``
lives under ``workflows``) so a single migration is produced for the app. The
ledger is append-only, mirroring ``ApprovalDecision``'s write-only discipline.
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class CancellationRequest(models.Model):
    """One request to cancel a leave application (Unit 18, spec 3.1).

    A ``withdrawal`` (pending application) is recorded directly as ``approved``
    with no approval stages; an ``approved_leave`` request starts ``pending``
    and needs Supervisor/HOD approval. At most one open (``pending``) request
    exists per application — enforced by a partial unique constraint.
    """

    class Kind(models.TextChoices):
        WITHDRAWAL = "withdrawal", "Withdrawal"
        APPROVED_LEAVE = "approved_leave", "Approved leave"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    class NotificationState(models.TextChoices):
        NOT_REQUIRED = "not_required", "Not required"
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        "leave.LeaveApplication",
        on_delete=models.PROTECT,
        related_name="cancellation_requests",
        help_text="The leave application being cancelled.",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="cancellation_requests",
        help_text="The employee who requested the cancellation (from request.user only).",
    )
    kind = models.CharField(max_length=16, choices=Kind.choices)
    reason = models.TextField(
        help_text="Mandatory reason, 10-1000 characters after trimming.",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    # Optimistic-lock counter: starts at 1, incremented on every stage
    # transition so a stale decision is aborted with 409.
    stage_version = models.PositiveIntegerField(default=1)
    requested_at = models.DateTimeField(default=timezone.now)
    decided_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Set once the request reaches a terminal state.",
    )
    application_status_at_request = models.CharField(
        max_length=20,
        help_text="Snapshot of the application status when the request was created.",
    )
    # Balance restoration recorded only on final approval of an ``approved_leave``
    # cancellation with a deduction; 0 otherwise.
    balance_restored_days = models.DecimalField(
        max_digits=6, decimal_places=1, default=0
    )
    restored_financial_year = models.CharField(
        max_length=16, null=True, blank=True
    )
    employee_notification_state = models.CharField(
        max_length=16,
        choices=NotificationState.choices,
        default=NotificationState.NOT_REQUIRED,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-requested_at"]
        constraints = [
            # The 10-1000 character reason policy is enforced authoritatively in
            # the service; TextField length lookups are unsupported in Postgres
            # CheckConstraints.
            models.CheckConstraint(
                condition=models.Q(stage_version__gte=1),
                name="cancellation_request_stage_version_gte_1",
            ),
            models.UniqueConstraint(
                fields=["application"],
                condition=models.Q(status="pending"),
                name="one_open_cancellation_per_application",
            ),
        ]
        indexes = [
            models.Index(
                fields=["status", "requested_at"],
                name="idx_cancel_status_requested",
            )
        ]

    def __str__(self) -> str:
        ref = self.application.reference_number or "Draft"
        return f"CancellationRequest({self.kind} of {ref})"


class CancellationApprovalStage(models.Model):
    """One stage of an ``approved_leave`` cancellation request.

    Stages are built from the application's original workflow snapshot, keeping
    only Supervisor/HOD roles in their original order. Exactly one stage is
    ``pending`` while the request is open; rejection ends the request and marks
    later stages ``not_reached``. Withdrawals never create stages.
    """

    class Status(models.TextChoices):
        WAITING = "waiting", "Waiting"
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        NOT_REACHED = "not_reached", "Not reached"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(
        CancellationRequest,
        on_delete=models.PROTECT,
        related_name="stages",
    )
    order = models.PositiveIntegerField(
        help_text="Position in the cancellation chain (original workflow order).",
    )
    role = models.CharField(
        max_length=20, help_text="The approver role: supervisor or hod."
    )
    role_label = models.CharField(
        max_length=80, help_text="Human-readable label for ``role``."
    )
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="cancellation_stages",
        help_text="The specific user responsible for this stage.",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.WAITING,
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    comment = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(order__gte=1),
                name="cancellation_stage_order_gte_1",
            ),
            models.UniqueConstraint(
                fields=["request", "order"],
                name="cancellation_request_stage_order_unique",
            ),
            models.UniqueConstraint(
                fields=["request"],
                condition=models.Q(status="pending"),
                name="one_pending_cancellation_stage_per_request",
            ),
        ]

    def __str__(self) -> str:
        return f"Stage {self.order} ({self.role_label})"


class BalanceTransactionLockedError(Exception):
    """Raised on any attempt to update or delete a ``LeaveBalanceTransaction``."""


class LeaveBalanceTransactionQuerySet(models.QuerySet):
    """Append-only: queryset-wide update/delete are rejected."""

    def update(self, *args: object, **kwargs: object):
        raise BalanceTransactionLockedError(
            "Balance transactions are append-only and cannot be updated."
        )

    def delete(self):
        raise BalanceTransactionLockedError(
            "Balance transactions are append-only and cannot be deleted."
        )


class LeaveBalanceTransactionManager(models.Manager.from_queryset(
    LeaveBalanceTransactionQuerySet
)):
    """Manager enforcing the append-only balance-ledger invariant."""


class LeaveBalanceTransaction(models.Model):
    """One immutable entry in the balance ledger (Unit 18, spec 3.1/3.3).

    Both arrow ends of an approved annual-leave application: the ``deduction``
    when the leave is approved, and at most one ``restoration`` per cancellation
    request when an approved application is finally cancelled. Rows are written
    once, never updated or deleted — not via the API, the admin, or the ORM.

    Restorations never feed carry-forward: ``carry_forward_eligible`` is always
    ``false`` on them and on cancelled applications.
    """

    class Type(models.TextChoices):
        DEDUCTION = "deduction", "Deduction"
        RESTORATION = "restoration", "Restoration"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="leave_balance_transactions",
    )
    financial_year = models.CharField(max_length=16)
    leave_type = models.PositiveIntegerField()
    application = models.ForeignKey(
        "leave.LeaveApplication",
        on_delete=models.PROTECT,
        related_name="balance_transactions",
    )
    cancellation_request = models.ForeignKey(
        CancellationRequest,
        on_delete=models.PROTECT,
        related_name="balance_transactions",
        null=True,
        blank=True,
    )
    type = models.CharField(max_length=16, choices=Type.choices)
    days = models.DecimalField(max_digits=6, decimal_places=1)
    carry_forward_eligible = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = LeaveBalanceTransactionManager()

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(days__gt=0),
                name="balance_transaction_days_gt_0",
            ),
            models.UniqueConstraint(
                fields=["cancellation_request", "type"],
                condition=models.Q(type="restoration"),
                name="one_restoration_per_cancellation",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.type} {self.days} days (FY {self.financial_year})"

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise BalanceTransactionLockedError(
                "Balance transactions are append-only and cannot be updated."
            )
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object) -> None:
        raise BalanceTransactionLockedError(
            "Balance transactions are append-only and cannot be deleted."
        )