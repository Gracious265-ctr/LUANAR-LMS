from django.db import models
from django.utils import timezone

from organisation.models import ApproverRole
from users.models import User
from workflows.models import Section


class ApplicationStage(models.Model):
    """One immutable position in an application's assigned approval chain.

    Stages are created in one batch by ``assign_workflow`` when the application
    is first submitted; only the stage that ``LeaveApplication.current_stage``
    points at is live, and exactly one stage is ``pending`` at a time.

    On resubmission (Unit 17) the chain is *kept*, not rebuilt: the scheme
    keeps the same reference and the same stage/approver, so stages never leave
    the cycle they were created under. The current stage flips back to
    ``pending`` in place and ``decision_version`` increments; earlier and later
    stages are untouched and ``LeaveApplication.submission_cycle`` increments
    while stage ``submission_cycle`` stays at the chain-creation cycle. Chain
    lookups use ``LeaveApplication.workflow_chain_cycle`` (the minimum stage
    cycle, i.e. usually 1), never ``submission_cycle``.

    ``decision_version`` starts at ``1`` and is optimistically incremented every
    time the stage is acted upon (approve/reject/correction/resubmission).
    Decision requests carry the version they read; a mismatch aborts with a
    stale/conflict (409).
    """

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
        help_text=(
            "The approver role responsible for this stage, snapshotted as its "
            "code. Kept as a plain string — and kept forever — so a later rename "
            "or retirement of the role can never rewrite history."
        ),
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
        help_text=(
            "The live role this stage was materialised from. Null only for rows "
            "written before roles became data; ``role`` stays authoritative in "
            "that case. Kept for traceability — not for reading behaviour."
        ),
    )
    history_scope = models.CharField(
        max_length=32,
        blank=True,
        default="",
        help_text=(
            "Snapshot of the role's leave-history scope at materialization. This "
            "— not the live role — is what an in-flight application is judged "
            "by, so widening or narrowing a role later never rewrites the review "
            "history of an application already in flight. Blank on rows written "
            "before roles became data."
        ),
    )
    handles_cancellation = models.BooleanField(
        default=False,
        help_text=(
            "Snapshot of the role's cancellation-handling flag at materialization, "
            "so an in-flight application never changes behaviour when HR edits "
            "the role."
        ),
    )
    assigned_approver = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="application_stages",
        help_text=(
            "The member of the stage's section who actually decided it, or who "
            "claimed it by acting. Null while the stage is still open, because a "
            "section is resolved by whoever acts first — the people entitled to "
            "act are the eligible_approvers snapshot, not this field."
        ),
    )
    section_ref = models.ForeignKey(
        Section,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="application_stages",
        help_text=(
            "The live section this stage was materialised from. Null only for "
            "rows written before sections existed; the snapshotted role fields "
            "stay authoritative in that case. Kept for traceability — not for "
            "reading behaviour."
        ),
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.WAITING,
    )
    is_final = models.BooleanField(
        default=False,
        help_text="True for the last stage; approving it finalises the application.",
    )
    skip_reason = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text=(
            "Why this stage was skipped, set at materialisation and never "
            "changed. Blank on any stage that was not skipped. Recorded because a "
            "chain that visibly starts at step 2 with steps 1 marked skipped is "
            "the only way a reader can tell a deliberate skip from a stage that "
            "was quietly dropped."
        ),
    )
    decision_version = models.PositiveIntegerField(
        default=1,
        help_text="Optimistic-lock counter, incremented on every decision.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "workflows_applicationstage"
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
        """The people who were entitled to act, from the snapshot.

        Reads through :class:`ApplicationStageApprover` rather than
        ``assigned_approver``, because the point of the snapshot is that
        eligibility does not change when configuration does.
        """
        if "eligible_approvers" in getattr(
            self, "_prefetched_objects_cache", {}
        ):
            return tuple(
                sorted(row.user_id for row in self.eligible_approvers.all())
            )
        return tuple(
            self.eligible_approvers.order_by("user_id").values_list(
                "user_id", flat=True
            )
        )


class ApplicationStageApprover(models.Model):
    """Who was entitled to act on a stage when the chain was materialised.

    Append-only. Changing who may act on a live application is an explicit
    administrative operation (reassignment), recorded in the audit log — never a
    side effect of editing configuration.
    """

    stage = models.ForeignKey(
        ApplicationStage, on_delete=models.CASCADE, related_name="eligible_approvers"
    )
    user = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="stage_eligibility"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "workflows_applicationstageapprover"
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
    """Append-only: queryset-wide update/delete are rejected."""

    def update(self, *args: object, **kwargs: object):
        raise ApprovalDecisionLockedError(
            "Approval decisions are append-only and cannot be updated."
        )

    def delete(self):
        raise ApprovalDecisionLockedError(
            "Approval decisions are append-only and cannot be deleted."
        )


class ApprovalDecisionManager(models.Manager.from_queryset(ApprovalDecisionQuerySet)):
    """Manager enforcing the append-only invariant."""


class ApprovalDecision(models.Model):
    """One recorded worker; append-only by design (spec 6.4).

    A decision belongs to exactly one stage of one application. It is written
    once, atomically with the stage/app transition it causes, and can never be
    updated or deleted — not via the API, the admin, or ORM helpers.
    """

    class Action(models.TextChoices):
        APPROVE = "approve", "Approve"
        REJECT = "reject", "Reject"
        RETURN_FOR_CORRECTION = "return_for_correction", "Return for correction"

    application = models.ForeignKey(
        "leave.LeaveApplication",
        on_delete=models.PROTECT,
        related_name="approval_decisions",
        help_text="The application the decision was made on.",
    )
    stage = models.ForeignKey(
        ApplicationStage,
        on_delete=models.PROTECT,
        related_name="decisions",
        help_text="The stage this decision was recorded against.",
    )
    approver = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="approval_decisions",
        help_text="The user who made the decision.",
    )
    approver_name = models.CharField(
        max_length=150,
        help_text="Snapshot of the approver's full name at decision time.",
    )
    role_label = models.CharField(
        max_length=80,
        help_text="Snapshot of the stage's role label.",
    )
    action = models.CharField(
        max_length=24,
        choices=Action.choices,
    )
    comment = models.TextField(
        blank=True,
        default="",
        help_text="Mandatory for reject and return-for-correction.",
    )
    submission_cycle = models.PositiveIntegerField(
        default=1,
        help_text="The resubmission cycle this decision belongs to.",
    )
    decided_at = models.DateTimeField(
        default=timezone.now,
        help_text="Explicit timestamp recorded by the decision service.",
    )

    objects = ApprovalDecisionManager()

    class Meta:
        db_table = "workflows_approvaldecision"
        ordering = ["-decided_at"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(action__in=("reject", "return_for_correction"))
                | ~models.Q(comment=""),
                name="comment_required_for_reject_or_return",
            )
        ]
        indexes = [
            models.Index(
                fields=["approver", "decided_at"],
                name="idx_decision_approver_time",
            )
        ]

    def __str__(self) -> str:
        return (
            f"{self.get_action_display()} ({self.approver_name})"
            f" on {self.application.reference_number or self.application_id}"
        )

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ApprovalDecisionLockedError(
            "Approval decisions are append-only and cannot be deleted."
        )

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ApprovalDecisionLockedError(
                "Approval decisions are append-only and cannot be updated."
            )
        super().save(*args, **kwargs)


class Delegation(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    approver = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="delegations_as_approver",
    )
    delegate = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="delegations_as_delegate",
        null=True,
        blank=True,
    )
    starts_on = models.DateField()
    ends_on = models.DateField(null=True, blank=True)
    request_reason = models.TextField(blank=True)
    requested_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="delegations_requested",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.REQUESTED,
    )
    decision_reason = models.TextField(blank=True)
    decided_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="delegations_decided",
        null=True,
        blank=True,
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "workflows_delegation"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_on__isnull=True)
                | models.Q(ends_on__gte=models.F("starts_on")),
                name="delegation_ends_on_gte_starts_on",
            ),
            models.UniqueConstraint(
                fields=["approver"],
                condition=models.Q(status="requested"),
                name="one_open_request_per_approver",
            ),
        ]

    @property
    def state(self) -> str:
        """The calendar-aware lifecycle state shown in the UI.

        ``approved`` maps to ``scheduled`` / ``active`` / ``ended`` depending on
        today against the delegation period.
        """
        if self.status == self.Status.APPROVED:
            today = timezone.localdate()
            if self.ends_on is not None and self.ends_on < today:
                return "ended"
            if self.starts_on > today:
                return "scheduled"
            return "active"
        return self.status

    def __str__(self) -> str:
        delegate = self.delegate.get_full_name() if self.delegate else "unassigned"
        return f"{self.approver.get_full_name()} → {delegate} ({self.state})"


class Reassignment(models.Model):
    """An HR emergency reassignment of a pending application to an approver.

    ``from_approver`` records who the application was previously with and may be
    ``None`` when a submitted application had not yet been routed (the first
    reassignment is effectively an initial assignment). Reassigning atomically
    writes this history row and updates
    ``LeaveApplication.current_approver`` — the live responsible-approver spine
    Unit 21 consumes.
    """

    application = models.ForeignKey(
        "leave.LeaveApplication",
        on_delete=models.PROTECT,
        related_name="reassignments",
        help_text="The pending leave application being reassigned.",
    )
    from_approver = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="reassignments_from",
        null=True,
        blank=True,
        help_text="The approver the application was previously assigned to.",
    )
    to_approver = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="reassignments_to",
        help_text="The replacement approver who inherits the pending application.",
    )
    reason = models.TextField(
        help_text="HR's mandatory reason for the reassignment.",
    )
    decided_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="reassignments_decided",
        help_text="The HR user who performed the reassignment.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "workflows_reassignment"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        application = self.application.reference_number or "Draft"
        return f"Reassignment({application} → {self.to_approver.get_full_name()})"
