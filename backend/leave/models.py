import uuid

from django.conf import settings
from django.db import models
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
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        LeaveApplication,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    file_path = models.CharField(max_length=512)
    file_url = models.URLField()
    file_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField()
    content_type = models.CharField(max_length=100)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self) -> str:
        return f"Document({self.file_name})"


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
