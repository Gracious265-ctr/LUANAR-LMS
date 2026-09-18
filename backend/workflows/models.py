from django.db import models
from django.utils import timezone

from users.models import EmployeeProfile, User

APPROVER_ROLE_CODES = ("supervisor", "hod", "dean", "registrar", "dvc", "hr")

APPROVER_ROLE_CHOICES = [
    (code, label)
    for code, label in User.Role.choices
    if code in APPROVER_ROLE_CODES
]


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