import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class GradeEntitlement(models.Model):
    """Effective-dated annual leave entitlement for a grade range."""

    grade_start = models.CharField(max_length=20)
    grade_end = models.CharField(max_length=20)
    days = models.PositiveIntegerField()
    effective_from = models.DateField()

    class Meta:
        ordering = ["-effective_from", "grade_start", "grade_end"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(days__gte=1),
                name="gradeentitlement_days_gte_1",
            ),
            models.CheckConstraint(
                condition=models.Q(grade_start__lte=models.F("grade_end")),
                name="gradeentitlement_grade_start_le_grade_end",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.grade_start}–{self.grade_end}: {self.days} days "
            f"(from {self.effective_from})"
        )

    def save(self, *args, **kwargs):
        self.grade_start = self.grade_start.strip().upper()
        self.grade_end = self.grade_end.strip().upper()
        super().save(*args, **kwargs)


class LeaveType(models.Model):
    """Named leave type registry entry (annual, maternity, paternity, ...)."""

    name = models.CharField(max_length=120, unique=True)
    code = models.SlugField(max_length=50, unique=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        self.name = self.name.strip()
        if not self.code:
            self.code = slugify(self.name)
        else:
            self.code = self.code.strip().lower()
        super().save(*args, **kwargs)


class LeaveRule(models.Model):
    """Effective-dated configuration for a leave type."""

    leave_type = models.ForeignKey(
        LeaveType, on_delete=models.CASCADE, related_name="rules"
    )
    max_duration_days = models.PositiveIntegerField()
    eligibility = models.TextField(blank=True)
    min_notice_days = models.PositiveIntegerField(default=0)
    requires_supporting_document = models.BooleanField(default=False)
    consumes_annual_entitlement = models.BooleanField(default=False)
    effective_from = models.DateField()

    class Meta:
        ordering = ["-effective_from", "leave_type"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(max_duration_days__gte=1),
                name="leaverule_max_duration_days_gte_1",
            ),
            models.CheckConstraint(
                condition=models.Q(min_notice_days__gte=0),
                name="leaverule_min_notice_days_gte_0",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.leave_type.name}: {self.max_duration_days} days "
            f"(from {self.effective_from})"
        )


class FinancialYear(models.Model):
    """A configured financial-year period for the university."""

    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=False)

    class Meta:
        ordering = ["-start_date"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="financialyear_end_date_gte_start_date",
            ),
        ]

    def __str__(self) -> str:
        status = " (active)" if self.is_active else ""
        return f"{self.start_date} – {self.end_date}{status}"


class PublicHoliday(models.Model):
    """A configured public-holiday date (named, occurs at most once)."""

    name = models.CharField(max_length=200)
    date = models.DateField(unique=True)

    class Meta:
        ordering = ["date"]
        constraints = [
            models.UniqueConstraint(
                fields=["date"],
                name="publicholiday_date_unique",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.date})"
class LeaveApplication(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CORRECTION_REQUIRED = "correction_required", "Correction Required"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="leave_applications",
    )

    # Soft reference to LeaveType (by integer PK) for now. The real FK is an
    # integration-track concern (Unit 20/21); the HR LeaveType registry now
    # exists (Unit 4) so the FK upgrade has a target.
    leave_type_id = models.PositiveIntegerField(null=True, blank=True)

    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    calculated_days = models.PositiveIntegerField(null=True, blank=True)
    reason = models.TextField(blank=True, default="")

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    reference_number = models.CharField(
        max_length=32, unique=True, null=True, blank=True
    )

    # The approver who currently must act on this pending application. Set only
    # by HR emergency reassignment (Unit 9) for now; Unit 21 (workflow routing)
    # resolves and writes it as the responsible-approver spine.
    current_approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="applications_assigned",
    )

    # Unit 16 workflow spine. ``current_stage`` is the live ApprovalStage the
    # application sits on (null until the workflow is assigned at submission);
    # ``submission_cycle`` counts submissions and is copied onto decisions so a
    # future resubmission unit can group them (incremented there, not here).
    current_stage = models.ForeignKey(
        "workflows.ApplicationStage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    submission_cycle = models.PositiveIntegerField(default=1)

    # Unit 17 optimistic-concurrency token. Incremented on every saved edit and
    # every document operation while the application is rejected or correction
    # required, so two windows can never silently overwrite each other.
    row_version = models.PositiveIntegerField(default=1)

    # Unit 18 cancellation. Set when the application is withdrawn or
    # a cancellation is finally approved.
    cancelled_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    # Authoritative, server-calculated values written once at submission (Unit 14).
    working_days = models.PositiveSmallIntegerField(null=True, blank=True)
    calendar_days = models.PositiveSmallIntegerField(null=True, blank=True)
    financial_year_label = models.CharField(max_length=16, null=True, blank=True)
    rules_snapshot = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        ref = self.reference_number or "Draft"
        return f"LeaveApplication({ref} - {self.employee})"


class SupportingDocument(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        RETIRED = "retired", "Retired"

    class RetireReason(models.TextChoices):
        REPLACED = "replaced", "Replaced"
        REMOVED = "removed", "Removed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        LeaveApplication,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    file_path = models.CharField(max_length=512)
    file_url = models.URLField(max_length=2048)
    file_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField()
    content_type = models.CharField(max_length=100)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    # Unit 17 lifecycle: documents on a submitted application are never
    # physically deleted. A replace/remove retires the old row (``status``
    # drops to ``retired``) so it stays in the application history; the file in
    # storage is never removed either (retirement is metadata-only).
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    retired_at = models.DateTimeField(null=True, blank=True)
    retired_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="documents_retired",
    )
    retire_reason = models.CharField(
        max_length=20, choices=RetireReason.choices, null=True, blank=True
    )
    replaced_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replaced_from",
    )

    class Meta:
        ordering = ["-uploaded_at"]
        indexes = [
            models.Index(fields=["application", "status"]),
        ]

    def __str__(self) -> str:
        return f"Document({self.file_name})"


class ApplicationRevision(models.Model):
    """An immutable content snapshot taken at each submission (Unit 17).

    Revision ``1`` is written at the initial submission (Unit 14); the
    `resubmit` service writes revision ``N`` for cycle ``N``. ``revision_number``
    therefore equals ``LeaveApplication.submission_cycle`` at the time of
    creation. ``changes`` is the diff against the previous revision (``None``
    for revision 1) and is what the approver sees in the change summary.

    Rows are append-only: no update or delete through the ORM, admin, or API.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        LeaveApplication,
        on_delete=models.CASCADE,
        related_name="revisions",
    )
    revision_number = models.PositiveIntegerField()
    leave_type = models.ForeignKey(
        LeaveType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    leave_type_name = models.CharField(max_length=120)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    working_days = models.PositiveSmallIntegerField(null=True, blank=True)
    reason = models.TextField(blank=True, default="")
    documents = models.JSONField(default=list)
    changes = models.JSONField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="application_revisions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["revision_number"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(revision_number__gte=1),
                name="applicationrevision_revision_number_gte_1",
            ),
            models.UniqueConstraint(
                fields=["application", "revision_number"],
                name="applicationrevision_application_revision_number_unique",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"Revision {self.revision_number} of "
            f"{self.application.reference_number or self.application_id}"
        )


class ReferenceSequence(models.Model):
    """Per-financial-year reference counter (Unit 14, decision D8).

    Each financial year has its own independent, never-reused sequence; the
    ``reference_number`` unique constraint on ``LeaveApplication`` is the final
    safety net against a collision.
    """

    financial_year_label = models.CharField(max_length=16, unique=True)
    last_value = models.PositiveIntegerField(default=0)

    def __str__(self) -> str:
        return f"RefSeq({self.financial_year_label}: {self.last_value})"


class CancellationRequest(models.Model):
    """A leave cancellation or withdrawal request (Unit 18).

    A withdrawal is a ``kind = withdrawal`` request created directly in
    ``approved`` status with no approver stages. An approved-leave
    cancellation is ``kind = approved_leave`` and progresses through
    ``CancellationApprovalStage`` rows.
    """

    class Kind(models.TextChoices):
        WITHDRAWAL = "withdrawal", "Withdrawal"
        APPROVED_LEAVE = "approved_leave", "Approved Leave Cancellation"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    class EmployeeNotificationState(models.TextChoices):
        NOT_REQUIRED = "not_required", "Not required"
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    application = models.ForeignKey(
        "leave.LeaveApplication",
        on_delete=models.CASCADE,
        related_name="cancellation_requests",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cancellation_requests",
    )
    kind = models.CharField(max_length=20, choices=Kind.choices)
    reason = models.TextField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    stage_version = models.PositiveIntegerField(default=1)
    requested_at = models.DateTimeField(default=timezone.now)
    decided_at = models.DateTimeField(null=True, blank=True)
    application_status_at_request = models.CharField(max_length=20)
    balance_restored_days = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )
    restored_financial_year = models.CharField(max_length=16, null=True, blank=True)
    employee_notification_state = models.CharField(
        max_length=20,
        choices=EmployeeNotificationState.choices,
        default=EmployeeNotificationState.NOT_REQUIRED,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-requested_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["application"],
                condition=models.Q(status="pending"),
                name="cancellationrequest_one_pending_per_application",
            )
        ]

    def __str__(self) -> str:
        return f"Cancellation({self.application_id} - {self.kind} - {self.status})"


class CancellationApprovalStage(models.Model):
    """One sequential approval stage of a cancellation request (Unit 18)."""

    class Status(models.TextChoices):
        WAITING = "waiting", "Waiting"
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        NOT_REACHED = "not_reached", "Not Reached"
        CANCELLED = "cancelled", "Cancelled"

    request = models.ForeignKey(
        CancellationRequest,
        on_delete=models.CASCADE,
        related_name="stages",
    )
    order = models.PositiveIntegerField()
    role = models.CharField(max_length=20)
    role_label = models.CharField(max_length=100)
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="cancellation_stages",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.WAITING,
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    comment = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(
                fields=["request", "order"],
                name="cancellationapprovalstage_request_order_unique",
            )
        ]

    def __str__(self) -> str:
        return f"CancellationStage({self.request_id} stage {self.order} - {self.role})"


class LeaveBalanceTransaction(models.Model):
    """Append-only balance ledger (Unit 18)."""

    class Type(models.TextChoices):
        DEDUCTION = "deduction", "Deduction"
        RESTORATION = "restoration", "Restoration"

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="balance_transactions",
    )
    financial_year = models.CharField(max_length=16)
    leave_type = models.ForeignKey(
        "leave.LeaveType",
        on_delete=models.PROTECT,
        related_name="balance_transactions",
    )
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
    type = models.CharField(max_length=20, choices=Type.choices)
    days = models.DecimalField(max_digits=10, decimal_places=2)
    carry_forward_eligible = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["cancellation_request", "type"],
                condition=models.Q(type="restoration"),
                name="balancetransaction_unique_restoration_per_request",
            )
        ]

    def __str__(self) -> str:
        return f"BalanceTransaction({self.type} - {self.days}d - {self.employee})"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("LeaveBalanceTransaction rows are append-only.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("LeaveBalanceTransaction rows are append-only.")
