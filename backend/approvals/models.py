from django.conf import settings
from django.db import models

from org.models import ApproverRole, Section


class ApplicationStage(models.Model):
    class Status(models.TextChoices):
        WAITING = "waiting", "Waiting"
        PENDING = "pending", "Pending action"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CORRECTION_REQUESTED = "correction_requested", "Correction requested"
        SUPERSEDED = "superseded", "Superseded by resubmission"
        SKIPPED = "skipped", "Skipped"
        CANCELLED = "cancelled", "Cancelled"

    application = models.ForeignKey(
        "leave.LeaveApplication",
        on_delete=models.CASCADE,
        related_name="stages",
        help_text="The application this stage belongs to.",
    )
    submission_cycle = models.PositiveSmallIntegerField(
        default=1,
        help_text="The resubmission cycle this stage belongs to.",
    )
    stage_order = models.PositiveIntegerField(
        help_text="Position in the chain, 1-based and unique per application/cycle.",
    )
    role = models.CharField(
        max_length=50,
        help_text="The approver role responsible for this stage, snapshotted as its code.",
    )
    role_label = models.CharField(
        max_length=80,
        help_text="Human-readable label for ``role``, snapshotted at materialization.",
    )
    role_ref = models.ForeignKey(
        ApproverRole,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="application_stages",
    )
    history_scope = models.CharField(
        max_length=32,
        blank=True,
        default="",
    )
    handles_cancellation = models.BooleanField(default=False)
    assigned_approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="application_stages",
    )
    section_ref = models.ForeignKey(
        Section,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="application_stages",
    )
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.WAITING,
    )
    is_final = models.BooleanField(default=False)
    skip_reason = models.CharField(
        max_length=320,
        blank=True,
        default="",
    )
    decision_version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["application", "submission_cycle", "stage_order"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(stage_order__gte=1),
                name="stage_order_positive",
            ),
            models.UniqueConstraint(
                fields=["application", "submission_cycle", "stage_order"],
                name="unique_stage_order_per_application",
            ),
            models.UniqueConstraint(
                fields=["application", "submission_cycle"],
                condition=models.Q(status="pending"),
                name="unique_pending_stage_per_application",
            ),
        ]
        indexes = [
            models.Index(
                fields=["assigned_approver", "status"],
                name="idx_stage_approver_status",
            )
        ]

    def __str__(self) -> str:
        return (
            f"Stage {self.stage_order} (cycle {self.submission_cycle},"
            f" {self.role_label})"
            f" #{self.application.reference_number or self.application_id}"
        )

    def eligible_approver_ids(self) -> tuple[int, ...]:
        if "eligible_approvers" in getattr(self, "_prefetched_objects_cache", {}):
            return tuple(sorted(row.user_id for row in self.eligible_approvers.all()))
        return tuple(
            self.eligible_approvers.order_by("user_id").values_list(
                "user_id", flat=True
            )
        )


class ApplicationStageApprover(models.Model):
    stage = models.ForeignKey(
        ApplicationStage, on_delete=models.CASCADE, related_name="eligible_approvers"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="stage_eligibility"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["stage", "user"]
        constraints = [
            models.UniqueConstraint(
                fields=["stage", "user"],
                name="stageapprover_stage_user_unique",
            )
        ]
        indexes = [
            models.Index(fields=["user"], name="idx_stage_elig_user")
        ]

    def __str__(self) -> str:
        return f"{self.user.get_full_name()} eligible for stage {self.stage_id}"


class ApprovalDecisionLockedError(Exception):
    """Raised on any attempt to update or delete an ``ApprovalDecision``."""


class ApprovalDecisionQuerySet(models.QuerySet):
    def update(self, *args: object, **kwargs: object):
        raise ApprovalDecisionLockedError(
            "Approval decisions are append-only and cannot be updated."
        )

    def delete(self):
        raise ApprovalDecisionLockedError(
            "Approval decisions are append-only and cannot be deleted."
        )


class ApprovalDecisionManager(models.Manager.from_queryset(ApprovalDecisionQuerySet)):
    pass


class ApprovalDecision(models.Model):
    class Action(models.TextChoices):
        APPROVE = "approve", "Approve"
        REJECT = "reject", "Reject"
        RETURN_FOR_CORRECTION = "return_for_correction", "Return for correction"

    application = models.ForeignKey(
        "leave.LeaveApplication",
        on_delete=models.PROTECT,
        related_name="approval_decisions",
    )
    stage = models.ForeignKey(
        ApplicationStage,
        on_delete=models.PROTECT,
        related_name="decisions",
    )
    action = models.CharField(
        max_length=32,
        choices=Action.choices,
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="approval_decisions_made",
    )
    reason = models.TextField(blank=True, default="")
    decided_at = models.DateTimeField(auto_now_add=True)
    decision_version = models.PositiveIntegerField(default=1)

    objects = ApprovalDecisionManager()

    class Meta:
        ordering = ["-decided_at"]

    def __str__(self) -> str:
        return (
            f"Decision {self.action} on {self.application.reference_number or self.application_id}"
            f" by {self.actor.get_full_name()}"
        )

    def clean(self) -> None:
        super().clean()
        if self.stage_id is not None and self.application_id is not None:
            if self.stage.application_id != self.application_id:
                raise models.ValidationError(
                    {"stage": "Stage does not belong to this application."}
                )

    def save(self, *args: object, **kwargs: object) -> None:
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args: object, **kwargs: object):
        raise ApprovalDecisionLockedError(
            "Approval decisions are append-only and cannot be deleted."
        )
