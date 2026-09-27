from django.conf import settings
from django.db import models
from django.utils import timezone

from users.models import EmployeeProfile, User

APPROVER_ROLE_CODES = ("supervisor", "hod", "dean", "registrar", "dvc", "hr")

APPROVER_ROLE_CHOICES = [
    (code, label)
    for code, label in User.Role.choices
    if code in APPROVER_ROLE_CODES
]

# Stage roles in the approver chain. HR and employee are never workflow stages.
STAGE_ROLE_CODES = ("supervisor", "hod", "dean", "registrar", "dvc")

STAGE_ROLE_LABELS = {
    code: label for code, label in User.Role.choices if code in STAGE_ROLE_CODES
}

STAGE_ROLE_CHOICES = list(STAGE_ROLE_LABELS.items())


class Workflow(models.Model):
    """A configured approval sequence for a group of employees."""

    name = models.CharField(max_length=200, unique=True)
    employee_category = models.CharField(
        max_length=20,
        choices=EmployeeProfile.Category.choices,
        blank=True,
        help_text="Blank applies the workflow to every employee category.",
    )
    department = models.CharField(
        max_length=200,
        blank=True,
        help_text="Blank applies the workflow to every department.",
    )
    effective_from = models.DateField(
        null=True,
        blank=True,
        help_text="Blank keeps the workflow a draft; set a date to schedule it.",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    @property
    def scope(self) -> tuple[str, str]:
        """The (category, department) a workflow applies to; blank means any."""
        return (self.employee_category or "", self.department or "")

    @property
    def state(self) -> str:
        """Derived lifecycle state: draft, scheduled, active, or inactive."""
        if self.effective_from is None:
            return "draft"
        if not self.is_active:
            return "inactive"
        if self.effective_from > timezone.localdate():
            return "scheduled"
        return "active"

    def __str__(self) -> str:
        scope = self.employee_category or "All categories"
        if self.department:
            scope = f"{scope} / {self.department}"
        return f"{self.name} ({scope})"


class WorkflowStage(models.Model):
    """One mandatory approver step in a workflow's sequence."""

    workflow = models.ForeignKey(
        Workflow, on_delete=models.CASCADE, related_name="stages"
    )
    order = models.PositiveIntegerField()
    approver_role = models.CharField(max_length=20, choices=APPROVER_ROLE_CHOICES)

    class Meta:
        ordering = ["order"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(order__gte=1),
                name="workflowstage_order_gte_1",
            ),
            models.UniqueConstraint(
                fields=["workflow", "order"],
                name="workflowstage_workflow_order_unique",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.order}. {self.approver_role}"


class Delegation(models.Model):
    """A temporary transfer of an approver's pending decisions to a delegate.

    The delegation is person-based: a specific original approver ``User`` hands
    their pending approvals to a specific delegate ``User`` while they are
    unavailable. Applications do not exist yet, so the actual routing body is
    Unit 21; this record plus :func:`active_delegation_for` are the boundary it
    consumes.
    """

    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    approver = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="delegations_as_approver",
        help_text="The approver whose pending decisions are delegated.",
    )
    delegate = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="delegations_as_delegate",
        null=True,
        blank=True,
        help_text="The person temporarily acting for the approver; required once approved.",
    )
    starts_on = models.DateField()
    ends_on = models.DateField(
        null=True,
        blank=True,
        help_text="Blank means the delegation stays active until HR cancels it.",
    )
    request_reason = models.TextField(
        blank=True,
        help_text="The approver's reason for requesting delegation.",
    )
    requested_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="delegations_requested",
        help_text="Who submitted the request (the approver or HR on their behalf).",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.REQUESTED,
    )
    decision_reason = models.TextField(
        blank=True,
        help_text="HR's mandatory reason when approving, rejecting, or cancelling.",
    )
    decided_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="delegations_decided",
        null=True,
        blank=True,
        help_text="The HR user who decided the request.",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_on__isnull=True)
                | models.Q(ends_on__gte=models.F("starts_on")),
                name="delegation_ends_on_gte_starts_on",
            ),
            # The service-level ``open_request_exists`` check gives the friendly
            # 400, but it is a bare SELECT ... EXISTS and two concurrent requests
            # for the same approver could both pass it. This partial unique
            # index is the database backstop that closes the race.
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
        ordering = ["-created_at"]

    def __str__(self) -> str:
        application = self.application.reference_number or "Draft"
        return f"Reassignment({application} → {self.to_approver.get_full_name()})"


class ApplicationStage(models.Model):
    """One immutable position in an application's assigned approval chain.

    Stages are created in one batch by ``assign_workflow`` when the application
    is first submitted; only the stage that ``LeaveApplication.current_stage``
    points at is live, and exactly one stage is ``pending`` at a time.

    On resubmission (Unit 17) the chain is *kept*, not rebuilt: the scheme
    keeps the same reference and the same stage/approver, so stages never leave
    the cycle they were created under. The current stage flips back to
    ``pending`` in place and ``decision_version`` increments; earlier and later
    stages are untouched and ``LieaveApplication.submission_cycle`` increments
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
        # A pending stage closed by an employee withdrawing their application
        # (Unit 18). The application leaves the approver queues and any decision
        # on it returns 409.
        CANCELLED = "cancelled", "Cancelled"
        # A configured stage that was never activated because its resolved
        # approver is the applicant themself. An employee who is also an
        # approver must never be the approver of record for their own leave, so
        # the stage is bypassed and the application moves to the next approver
        # in the sequence. The row is kept so the chain stays contiguous and the
        # snapshot keeps recording the workflow as HR configured it.
        SKIPPED = "skipped", "Skipped — applicant is the approver"

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
        max_length=20,
        choices=STAGE_ROLE_CHOICES,
        help_text="The approver role responsible for this stage.",
    )
    role_label = models.CharField(
        max_length=80,
        help_text="Human-readable label for ``role``.",
    )
    assigned_approver = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="application_stages",
        help_text="The specific user responsible for this stage.",
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
    decision_version = models.PositiveIntegerField(
        default=1,
        help_text="Optimistic-lock counter, incremented on every decision.",
    )
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