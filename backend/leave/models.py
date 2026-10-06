import uuid

from django.conf import settings
from django.db import models
from django.db.models import Min
from django.utils import timezone
from django.utils.text import slugify


class LeaveType(models.Model):
    """Named leave type registry entry (annual, maternity, paternity, ...)."""

    name = models.CharField(max_length=120, unique=True)
    code = models.SlugField(max_length=50, unique=True, blank=True)
    is_active = models.BooleanField(
        default=True,
        help_text=(
            "Whether HR still offers this type. Retiring a type hides it from "
            "employees without deleting it, so applications already filed against "
            "it keep their type and its rules keep their history."
        ),
    )
    requires_institutional_approval = models.BooleanField(
        default=False,
        help_text=(
            "Whether an application of this type must reach the institution even "
            "when the applicant's own chain would stop earlier. Off by default: "
            "a type that quietly required the registrar to sign off every "
            "request would be discovered by an employee, not by HR."
        ),
    )

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


class GradeEntitlement(models.Model):
    """Effective-dated entitlement to a leave type for a grade range.

    This is what makes a leave type appear in an employee's selection: the band
    says which type the grade is granted, and ``effective_from`` says from when.
    Without a band, the type is offered to nobody.

    ``leave_type`` is nullable, and a null means the pre-existing meaning: this
    band *is* the annual leave entitlement, with no type named. Rows created
    before the field existed are left that way rather than being given an
    invented type. A null grants no selectable type and does not fund a specific
    one, so it is the fallback the balance resolver uses when nothing is linked.
    """

    grade_start = models.CharField(max_length=20)
    grade_end = models.CharField(max_length=20)
    days = models.PositiveIntegerField()
    effective_from = models.DateField()
    leave_type = models.ForeignKey(
        LeaveType,
        on_delete=models.PROTECT,
        related_name="grade_entitlements",
        null=True,
        blank=True,
        help_text=(
            "The leave type this band grants. Naming it is what puts the type in "
            "the employee's selection for grades in this range."
        ),
    )

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
            # One row per (type, grade range). Postgres treats the null in
            # ``leave_type`` as distinct from itself and from every other null,
            # so untyped bands are only constrained by the overlap check, which
            # is where they are actually policed.
            models.UniqueConstraint(
                fields=["leave_type", "grade_start", "grade_end"],
                name="gradeentitlement_type_range_unique",
            ),
        ]

    def __str__(self) -> str:
        # The type is in the label because the admin's band picker and the audit
        # trail both read this string, and a list of bands that does not say
        # which leave type each one grants is not distinguishable.
        granted = self.leave_type.name if self.leave_type_id else "annual leave"
        return (
            f"{self.grade_start}–{self.grade_end}: {self.days} {granted} days "
            f"(from {self.effective_from})"
        )

    def save(self, *args, **kwargs):
        self.grade_start = self.grade_start.strip().upper()
        self.grade_end = self.grade_end.strip().upper()
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

    # The approver who has actually taken up this pending application. A section
    # is resolved by whoever acts first, so this is null while a stage is still
    # open and is written the moment one of its eligible members decides (or is
    # placed there by HR emergency reassignment). The people who may act are
    # ``Application.current_stage.eligible_approvers`` — this field records who
    # did, not who could.
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

    # Set once, inside the approval transaction, when the application reaches
    # its final ``APPROVED`` state (Unit 23b). The generated approved document
    # states when the leave was approved, so the date has to be recorded rather
    # than re-derived at render time. Never rewritten afterwards.
    approved_on = models.DateTimeField(null=True, blank=True)

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
    file_url = models.URLField(
        max_length=2048,
        help_text=(
            "Cached signed URL; a fresh one is minted per read. Must comfortably "
            "exceed a Supabase signed URL at maximum length: a 255-char "
            "file_name yields a ~311-char storage path, which signs to roughly "
            "900 characters. Reads re-sign from file_path, so this column is a "
            "cache/fallback only."
        ),
    )
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


class ApplicationRevisionLockedError(Exception):
    """Raised on any attempt to update or delete an ``ApplicationRevision``."""


class ApplicationRevisionQuerySet(models.QuerySet):
    """Append-only: queryset-wide update/delete are rejected."""

    def update(self, *args: object, **kwargs: object):
        raise ApplicationRevisionLockedError(
            "Application revisions are append-only and cannot be updated."
        )

    def delete(self):
        raise ApplicationRevisionLockedError(
            "Application revisions are append-only and cannot be deleted."
        )


class ApplicationRevisionManager(models.Manager.from_queryset(ApplicationRevisionQuerySet)):
    """Manager enforcing the append-only invariant."""


class ApplicationRevision(models.Model):
    """Append-only snapshot of an application at one submission (Unit 17, Unit 24).

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

    objects = ApplicationRevisionManager()

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

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ApplicationRevisionLockedError(
            "Application revisions are append-only and cannot be deleted."
        )

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ApplicationRevisionLockedError(
                "Application revisions are append-only and cannot be updated."
            )
        super().save(*args, **kwargs)


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
