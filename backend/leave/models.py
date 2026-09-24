import uuid

from django.conf import settings
from django.db import models
from django.db.models import Min
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
    eligibility_rules = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "Machine-readable eligibility rules for the validation engine, each "
            "``{'type': ..., 'params': {...}}``. ``eligibility`` above stays the "
            "human-readable description."
        ),
    )
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
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CORRECTION_REQUIRED = "correction_required", "Correction required"
        CANCELLED = "cancelled", "Cancelled"

    # The set of statuses where the employee can no longer submit/edit (Unit 17).
    # Unit 18 adds ``CANCELLED``: a withdrawn or cancelled application is terminal.
    SUBMITTED_STATUSES = (Status.SUBMITTED,)
    APPROVED_STATUSES = (Status.APPROVED,)

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

    # Set when the application reaches the terminal ``CANCELLED`` state (Unit 18):
    # either the employee withdrew a pending application or an approved-leave
    # cancellation was finally approved. Null for every other status.
    cancelled_at = models.DateTimeField(null=True, blank=True)

    # Resubmission cycle counter. Starts at 1; increments on every resubmission.
    # All workflow stages and approval decisions for one submission carry this
    # value so a stale stage can never be confused with the live chain.
    submission_cycle = models.PositiveSmallIntegerField(default=1)

    # The stage the application is currently parked at. Written by the workflow
    # assignment/approval services; null for drafts and finalised applications.
    current_stage = models.ForeignKey(
        "workflows.ApplicationStage",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="The live workflow stage awaiting (or last acted on) this application.",
    )

    # Authoritative, server-calculated values written once at submission (Unit 14).
    working_days = models.PositiveSmallIntegerField(null=True, blank=True)
    calendar_days = models.PositiveSmallIntegerField(null=True, blank=True)
    financial_year_label = models.CharField(max_length=16, null=True, blank=True)
    rules_snapshot = models.JSONField(null=True, blank=True)

    # Optimistic-lock version. Every employee edit bumps this by one so a stale
    # edit context from a parallel tab/window is rejected with a conflict.
    row_version = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        ref = self.reference_number or "Draft"
        return f"LeaveApplication({ref} - {self.employee})"

    @property
    def workflow_chain_cycle(self) -> int:
        """The cycle the live workflow chain was created under.

        Resubmission reuses the original stage chain, so stage rows keep the
        cycle of the first submission. Decision-time rules keep working off
        ``submission_cycle``; chain lookups (which stage is pending, what comes
        next) must use this property so they never filter against a cycle the
        stages were not created under.
        """
        return (
            self.stages.aggregate(chain=Min("submission_cycle"))["chain"] or 1
        )


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
    file_url = models.URLField()
    file_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField()
    content_type = models.CharField(max_length=100)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    # Lifecycle (Unit 17). Documents are never hard-deleted after submission:
    # replaced/removed rows are retired so the audit trail and the revision
    # snapshot can still resolve their names. Only active rows are returned to
    # employees/approvers and counted by the documents validator.
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    retired_at = models.DateTimeField(null=True, blank=True)
    retired_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="retired_documents",
    )
    retire_reason = models.CharField(
        max_length=20,
        choices=RetireReason.choices,
        null=True,
        blank=True,
    )
    replaced_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replaced_documents",
    )

    def retire(self, user, reason, *, replaced_by=None) -> None:
        """Flip this row to ``retired`` (Unit 19).

        Retirement is permanent: a document is never re-activated. The storage
        object is deliberately kept so submitted revision snapshots and the
        audit trail still resolve. ``reason`` is ``replaced`` or ``removed``.
        """
        self.status = self.Status.RETIRED
        self.retired_at = timezone.now()
        self.retired_by = user
        self.retire_reason = reason
        self.replaced_by = replaced_by
        self.save(
            update_fields=[
                "status",
                "retired_at",
                "retired_by",
                "retire_reason",
                "replaced_by",
            ]
        )

    class Meta:
        ordering = ["-uploaded_at"]
        indexes = [
            models.Index(fields=["application", "status"]),
        ]

    def __str__(self) -> str:
        return f"Document({self.file_name})"


class ApplicationRevision(models.Model):
    """Append-only snapshot of an application at one submission (Unit 17).

    ``revision_number`` equals the application's ``submission_cycle`` at write
    time, so every resubmission records the exact state the approver saw before
    deciding. The approval review payload diffs a newer revision against the
    cycle-1 baseline to show "changes since your decision". Immutable like
    ``ApprovalDecision``: rows are write-only history.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        LeaveApplication,
        on_delete=models.PROTECT,
        related_name="revisions",
    )
    revision_number = models.PositiveSmallIntegerField()

    leave_type_id = models.PositiveIntegerField(null=True, blank=True)
    leave_type_name = models.CharField(max_length=120, blank=True, default="")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    working_days = models.PositiveSmallIntegerField(null=True, blank=True)
    reason = models.TextField(blank=True, default="")

    documents = models.JSONField(default=list)
    changes = models.JSONField(null=True, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="application_revisions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-revision_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["application", "revision_number"],
                name="applicationrevision_application_revision_number_uniq",
            ),
            models.CheckConstraint(
                condition=models.Q(revision_number__gte=1),
                name="applicationrevision_revision_number_gte_1",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"Revision({self.revision_number} of "
            f"{self.application.reference_number or self.application_id})"
        )

    def save(self, *args, **kwargs):
        raise ValueError("ApplicationRevision is append-only; it cannot be modified.")

    def delete(self, *args, **kwargs):
        raise ValueError("ApplicationRevision is append-only; it cannot be deleted.")


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


# Unit 18 models live in ``leave/cancellations/models.py`` (same app label). This
# import registers them with the app so ``makemigrations`` sees the new tables.
from .cancellations import models as _cancellations_models  # noqa: E402, F401  # isort: skip
