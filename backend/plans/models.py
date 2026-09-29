"""Leave day plans (Unit 25).

A ``LeaveDayPlan`` is one employee's forward-looking plan of annual leave
blocks inside a single financial year. Blocks are validated through the same
leave-validation pipeline as applications; once HR's workflow approves the plan,
each block that consumes annual entitlement *reserves* that many working days.
The employee confirms (locks the days) or releases them before the block
starts; an unconfirmed block auto-lapses at its start date.

* **Plan approval chain** — ``PlanApprovalStage`` mirrors ``ApplicationStage``
  but is plan-scoped (Unit 25 D3): the same workflow provider resolves the
  chain, with the supervisor stage fixed to the employee's assigned supervisor.
  ``PlanApprovalDecision`` is append-only like ``ApprovalDecision``.
* **Balance reservation** — ``PlanBalanceTransaction`` is an append-only
  reservation ledger, deliberately separate from
  ``LeaveBalanceTransaction``: a plan reserves *capacity* ahead of a real
  application, and the balance provider subtracts reservation net (reserves
  minus releases). ``confirm`` rows are informational — the days were already
  held by the ``reserve`` row.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from users.models import User


class PlanSettings(models.Model):
    """Single-row global configuration for the plans feature."""

    confirmation_lead_days = models.PositiveSmallIntegerField(
        default=14,
        validators=[MinValueValidator(1)],
        help_text="How many days before a block starts the employee is asked to confirm it.",
    )

    class Meta:
        verbose_name = "Plan settings"

    def __str__(self) -> str:
        return f"Plan settings (confirm {self.confirmation_lead_days} days ahead)"


def get_plan_settings() -> PlanSettings:
    """The singleton ``PlanSettings`` row, created lazily."""
    return PlanSettings.objects.first() or PlanSettings.objects.create(
        confirmation_lead_days=14
    )


class LeaveDayPlan(models.Model):
    """One employee's plan of leave blocks for one financial year period."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="leave_day_plans",
    )
    period_start = models.DateField()
    period_end = models.DateField()
    financial_year_label = models.CharField(max_length=16)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    # The approver / approval stage currently parked at (mirrors
    # ``LeaveApplication.current_approver``/``current_stage``).
    current_approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="plans_assigned",
    )
    current_stage = models.ForeignKey(
        "plans.PlanApprovalStage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="The live approval stage awaiting this plan.",
    )
    submission_cycle = models.PositiveSmallIntegerField(
        default=1,
        help_text="Reserved for v1 (plans are not resubmittable); always 1.",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    row_version = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(period_end__gte=models.F("period_start")),
                name="plan_period_end_gte_start",
            ),
            # One open plan per employee per financial year (D1). A rejected
            # plan is terminal, so it does not block a fresh plan for the same
            # period.
            models.UniqueConstraint(
                fields=["employee", "financial_year_label"],
                condition=~models.Q(status="rejected"),
                name="one_open_plan_per_employee_fy",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.employee.get_full_name()} plan ({self.financial_year_label})"

    @property
    def blocks(self) -> models.QuerySet:
        return self.plan_blocks.all()


class LeavePlanBlock(models.Model):
    """One leave block inside a ``LeaveDayPlan``."""

    class Status(models.TextChoices):
        # A block of a draft or submitted plan; capacity is not yet held.
        PROPOSED = "proposed", "Proposed"
        # Reserved as soon as the plan is approved (capacity held).
        RESERVED = "reserved", "Reserved"
        # The employee confirmed: the days are locked for a future application.
        CONFIRMED = "confirmed", "Confirmed"
        # Auto-settled at the block's start date without confirmation.
        LAPSED = "lapsed", "Lapsed"
        # Explicitly released/declined before the block started.
        RELEASED = "released", "Released"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan = models.ForeignKey(
        LeaveDayPlan, on_delete=models.CASCADE, related_name="plan_blocks"
    )
    leave_type_id = models.PositiveIntegerField(null=True, blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    working_days = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Whole working days, server-calculated."
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PROPOSED
    )
    # Optional link from a later LeaveApplication (D15): when an application is
    # submitted for a confirmed block, it points here instead of warning.
    application = models.ForeignKey(
        "leave.LeaveApplication",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="plan_blocks",
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    released_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_date", "end_date"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="planblock_end_date_gte_start_date",
            ),
        ]

    def __str__(self) -> str:
        return f"Block {self.start_date}–{self.end_date} ({self.status})"


class PlanApprovalStage(models.Model):
    """One materialised position in a plan's approval chain."""

    class Status(models.TextChoices):
        WAITING = "waiting", "Waiting"
        PENDING = "pending", "Pending action"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        SKIPPED = "skipped", "Skipped — applicant is the approver"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan = models.ForeignKey(
        LeaveDayPlan, on_delete=models.CASCADE, related_name="approval_stages"
    )
    submission_cycle = models.PositiveSmallIntegerField(default=1)
    stage_order = models.PositiveIntegerField()
    role = models.CharField(max_length=20)
    role_label = models.CharField(max_length=80)
    assigned_approver = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="plan_approval_stages",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.WAITING
    )
    is_final = models.BooleanField(default=False)
    decision_version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["plan", "submission_cycle", "stage_order"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(stage_order__gte=1),
                name="planstage_order_positive",
            ),
            models.UniqueConstraint(
                fields=["plan", "submission_cycle", "stage_order"],
                name="unique_plan_stage_order",
            ),
            models.UniqueConstraint(
                fields=["plan", "submission_cycle"],
                condition=models.Q(status="pending"),
                name="unique_pending_plan_stage",
            ),
        ]
        indexes = [
            models.Index(
                fields=["assigned_approver", "status"],
                name="idx_plan_stage_approver_status",
            )
        ]

    def __str__(self) -> str:
        return f"Plan stage {self.stage_order} ({self.role_label})"


class PlanApprovalDecisionLockedError(Exception):
    """Raised on any attempt to update or delete a ``PlanApprovalDecision``."""


class PlanApprovalDecisionQuerySet(models.QuerySet):
    """Append-only: queryset-wide update/delete are rejected."""

    def update(self, *args: object, **kwargs: object):
        raise PlanApprovalDecisionLockedError(
            "Plan approval decisions are append-only and cannot be updated."
        )

    def delete(self):
        raise PlanApprovalDecisionLockedError(
            "Plan approval decisions are append-only and cannot be deleted."
        )


class PlanApprovalDecisionManager(models.Manager.from_queryset(
    PlanApprovalDecisionQuerySet
)):
    """Manager enforcing the append-only invariant."""


class PlanApprovalDecision(models.Model):
    """One recorded plan decision; append-only by design."""

    class Action(models.TextChoices):
        APPROVE = "approve", "Approve"
        REJECT = "reject", "Reject"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan = models.ForeignKey(
        LeaveDayPlan,
        on_delete=models.PROTECT,
        related_name="approval_decisions",
    )
    stage = models.ForeignKey(
        PlanApprovalStage,
        on_delete=models.PROTECT,
        related_name="decisions",
    )
    approver = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="plan_approval_decisions"
    )
    approver_name = models.CharField(max_length=150)
    role_label = models.CharField(max_length=80)
    action = models.CharField(max_length=24, choices=Action.choices)
    comment = models.TextField(
        blank=True, default="", help_text="Mandatory when rejecting."
    )
    submission_cycle = models.PositiveSmallIntegerField(default=1)
    decided_at = models.DateTimeField(default=timezone.now)

    objects = PlanApprovalDecisionManager()

    class Meta:
        ordering = ["-decided_at"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(action="reject") | ~models.Q(comment=""),
                name="plan_comment_required_for_reject",
            )
        ]

    def __str__(self) -> str:
        return f"{self.get_action_display()} ({self.approver_name}) on plan {self.plan_id}"

    def delete(self, *args: object, **kwargs: object) -> None:
        raise PlanApprovalDecisionLockedError(
            "Plan approval decisions are append-only and cannot be deleted."
        )

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise PlanApprovalDecisionLockedError(
                "Plan approval decisions are append-only and cannot be updated."
            )
        super().save(*args, **kwargs)


class PlanBalanceTransactionLockedError(Exception):
    """Raised on any attempt to update or delete a ``PlanBalanceTransaction``."""


class PlanBalanceTransactionQuerySet(models.QuerySet):
    """Append-only: queryset-wide update/delete are rejected."""

    def update(self, *args: object, **kwargs: object):
        raise PlanBalanceTransactionLockedError(
            "Plan balance transactions are append-only and cannot be updated."
        )

    def delete(self):
        raise PlanBalanceTransactionLockedError(
            "Plan balance transactions are append-only and cannot be deleted."
        )


class PlanBalanceTransactionManager(models.Manager.from_queryset(
    PlanBalanceTransactionQuerySet
)):
    """Manager enforcing the append-only invariant."""


class PlanBalanceTransaction(models.Model):
    """Append-only reservation ledger for plan blocks.

    ``reserve`` holds capacity the day the plan is approved; ``release``
    returns it (explicit decline, HR release, or auto-lapse); ``confirm`` is
    informational (the days were already held by the reserve row). Available
    balance = entitlement + application ledger net − reservation net.
    """

    class Type(models.TextChoices):
        RESERVE = "reserve", "Reserve"
        CONFIRM = "confirm", "Confirm"
        RELEASE = "release", "Release"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    block = models.ForeignKey(
        LeavePlanBlock,
        on_delete=models.PROTECT,
        related_name="balance_transactions",
    )
    employee = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="plan_balance_transactions"
    )
    financial_year = models.CharField(max_length=16)
    leave_type_id = models.PositiveIntegerField(null=True, blank=True)
    type = models.CharField(max_length=16, choices=Type.choices)
    days = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0"))
    created_at = models.DateTimeField(auto_now_add=True)

    objects = PlanBalanceTransactionManager()

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.type} {self.days} days (block {self.block_id})"

    def delete(self, *args: object, **kwargs: object) -> None:
        raise PlanBalanceTransactionLockedError(
            "Plan balance transactions are append-only and cannot be deleted."
        )

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise PlanBalanceTransactionLockedError(
                "Plan balance transactions are append-only and cannot be updated."
            )
        super().save(*args, **kwargs)