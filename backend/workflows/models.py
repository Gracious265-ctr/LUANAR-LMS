from django.db import models
from django.utils import timezone

from users.models import EmployeeProfile, User

APPROVER_ROLE_CODES = ("supervisor", "hod", "dean", "registrar", "dvc", "hr")

STAGE_ROLE_CODES = ("supervisor", "hod", "dean", "registrar", "dvc")

STAGE_ROLE_CHOICES = [
    (code, label)
    for code, label in User.Role.choices
    if code in STAGE_ROLE_CODES
]

APPROVER_ROLE_CHOICES = [
    (code, label)
    for code, label in User.Role.choices
    if code in APPROVER_ROLE_CODES
]


class ImmutableDecisionError(Exception):
    """Raised when code tries to modify or delete an approval decision.

    ``ApprovalDecision`` rows are append-only (Unit 16): no update or delete
    through the ORM, admin, or API.
    """


class ApplicationStage(models.Model):
    """One approval stage of one submitted application (Unit 16).

    This row **is** the workflow snapshot (invariant 12.5): the role, its
    display label and the assigned approver are copied here at assignment time
    so later workflow configuration changes never alter an existing
    application. ``version`` is bumped on every change and is the optimistic
    concurrency token for decisions.
    """

    class Status(models.TextChoices):
        WAITING = "waiting", "Waiting"
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CORRECTION_REQUESTED = "correction_requested", "Correction requested"
        CANCELLED = "cancelled", "Cancelled"

    application = models.ForeignKey(
        "leave.LeaveApplication",
        on_delete=models.CASCADE,
        related_name="stages",
    )
    stage_order = models.PositiveIntegerField()
    role = models.CharField(max_length=20, choices=STAGE_ROLE_CHOICES)
    role_label = models.CharField(max_length=100)
    assigned_approver = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="application_stages",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.WAITING,
    )
    is_final = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["stage_order"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(stage_order__gte=1),
                name="applicationstage_stage_order_gte_1",
            ),
            models.UniqueConstraint(
                fields=["application", "stage_order"],
                name="applicationstage_application_stage_order_unique",
            ),
            models.UniqueConstraint(
                fields=["application"],
                condition=models.Q(status="pending"),
                name="applicationstage_one_pending_per_application",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.application_id} stage {self.stage_order} ({self.role})"


class ImmutableDecisionQuerySet(models.QuerySet):
    """QuerySet where bulk writes on the append-only table are impossible."""

    def update(self, *args, **kwargs):
        raise ImmutableDecisionError("Approval decisions are immutable.")

    def delete(self):
        raise ImmutableDecisionError("Approval decisions are immutable.")


class ApprovalDecisionManager(models.Manager):
    """Manager that makes bulk writes on an append-only table impossible."""

    def get_queryset(self):
        return ImmutableDecisionQuerySet(self.model, using=self._db)

    def update(self, *args, **kwargs):
        raise ImmutableDecisionError("Approval decisions are immutable.")

    def delete(self):
        raise ImmutableDecisionError("Approval decisions are immutable.")


class ApprovalDecision(models.Model):
    """An immutable, append-only approval decision (Unit 16).

    Created by the decision service; never updated or deleted through the ORM,
    admin, or API. Action, approver name and role label are snapshots taken at
    decision time; ``submission_cycle`` is copied from the application so a
    resubmission unit can group history by cycle.
    """

    class Action(models.TextChoices):
        APPROVE = "approve", "Approve"
        REJECT = "reject", "Reject"
        RETURN_FOR_CORRECTION = "return_for_correction", "Return for correction"

    application = models.ForeignKey(
        "leave.LeaveApplication",
        on_delete=models.CASCADE,
        related_name="approval_decisions",
    )
    stage = models.ForeignKey(
        ApplicationStage,
        on_delete=models.CASCADE,
        related_name="decisions",
    )
    approver = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="approval_decisions",
    )
    approver_name = models.CharField(max_length=200)
    role_label = models.CharField(max_length=100)
    action = models.CharField(max_length=40, choices=Action.choices)
    comment = models.TextField(blank=True, default="")
    submission_cycle = models.PositiveIntegerField(default=1)
    decided_at = models.DateTimeField(auto_now_add=True)

    objects = ApprovalDecisionManager()

    class Meta:
        ordering = ["decided_at"]
        indexes = [
            models.Index(fields=["approver", "decided_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(action="approve")
                | models.Q(comment__gt=""),
                name="approvaldecision_comment_required_unless_approve",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ImmutableDecisionError("Approval decisions are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ImmutableDecisionError("Approval decisions are immutable.")

    def __str__(self) -> str:
        return f"{self.action} by {self.approver_name} on {self.application_id}"


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
        on_delete=models.CASCADE,
        related_name="delegations_as_approver",
        help_text="The approver whose pending decisions are delegated.",
    )
    delegate = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
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
        on_delete=models.CASCADE,
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
        on_delete=models.CASCADE,
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
        on_delete=models.CASCADE,
        related_name="reassignments",
        help_text="The pending leave application being reassigned.",
    )
    from_approver = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="reassignments_from",
        null=True,
        blank=True,
        help_text="The approver the application was previously assigned to.",
    )
    to_approver = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="reassignments_to",
        help_text="The replacement approver who inherits the pending application.",
    )
    reason = models.TextField(
        help_text="HR's mandatory reason for the reassignment.",
    )
    decided_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="reassignments_decided",
        help_text="The HR user who performed the reassignment.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        application = self.application.reference_number or "Draft"
        return f"Reassignment({application} → {self.to_approver.get_full_name()})"