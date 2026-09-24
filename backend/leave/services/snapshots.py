import uuid
from django.conf import settings
from django.db import models
from django.db.models import Min
from django.utils.text import slugify

class GradeEntitlement(models.Model):
    """Effective-dated annual leave entitlement for a grade range."""
    grade_start = models.CharField(max_length=20)
    grade_end = models.CharField(max_length=20)
    days = models.PositiveIntegerField()
    effective_from = models.DateField()

    class Meta:
        ordering = ['-effective_from', 'grade_start', 'grade_end']
        constraints = [models.CheckConstraint(condition=models.Q(days__gte=1), name='gradeentitlement_days_gte_1'), models.CheckConstraint(condition=models.Q(grade_start__lte=models.F('grade_end')), name='gradeentitlement_grade_start_le_grade_end')]

    def __str__(self) -> str:
        return f'{self.grade_start}–{self.grade_end}: {self.days} days (from {self.effective_from})'

    def save(self, *args, **kwargs):
        self.grade_start = self.grade_start.strip().upper()
        self.grade_end = self.grade_end.strip().upper()
        super().save(*args, **kwargs)

class LeaveType(models.Model):
    """Named leave type registry entry (annual, maternity, paternity, ...)."""
    name = models.CharField(max_length=120, unique=True)
    code = models.SlugField(max_length=50, unique=True, blank=True)

    class Meta:
        ordering = ['name']

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
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE, related_name='rules')
    max_duration_days = models.PositiveIntegerField()
    eligibility = models.TextField(blank=True)
    min_notice_days = models.PositiveIntegerField(default=0)
    requires_supporting_document = models.BooleanField(default=False)
    consumes_annual_entitlement = models.BooleanField(default=False)
    effective_from = models.DateField()

    class Meta:
        ordering = ['-effective_from', 'leave_type']
        constraints = [models.CheckConstraint(condition=models.Q(max_duration_days__gte=1), name='leaverule_max_duration_days_gte_1'), models.CheckConstraint(condition=models.Q(min_notice_days__gte=0), name='leaverule_min_notice_days_gte_0')]

    def __str__(self) -> str:
        return f'{self.leave_type.name}: {self.max_duration_days} days (from {self.effective_from})'

class FinancialYear(models.Model):
    """A configured financial-year period for the university."""
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=False)

    class Meta:
        ordering = ['-start_date']
        constraints = [models.CheckConstraint(condition=models.Q(end_date__gte=models.F('start_date')), name='financialyear_end_date_gte_start_date')]

    def __str__(self) -> str:
        status = ' (active)' if self.is_active else ''
        return f'{self.start_date} – {self.end_date}{status}'

class PublicHoliday(models.Model):
    """A configured public-holiday date (named, occurs at most once)."""
    name = models.CharField(max_length=200)
    date = models.DateField(unique=True)

    class Meta:
        ordering = ['date']
        constraints = [models.UniqueConstraint(fields=['date'], name='publicholiday_date_unique')]

    def __str__(self) -> str:
        return f'{self.name} ({self.date})'

class LeaveApplication(models.Model):

    class Status(models.TextChoices):
        DRAFT = ('draft', 'Draft')
        SUBMITTED = ('submitted', 'Submitted')
        APPROVED = ('approved', 'Approved')
        REJECTED = ('rejected', 'Rejected')
        CORRECTION_REQUIRED = ('correction_required', 'Correction required')
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='leave_applications')
    leave_type_id = models.PositiveIntegerField(null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    calculated_days = models.PositiveIntegerField(null=True, blank=True)
    reason = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    reference_number = models.CharField(max_length=32, unique=True, null=True, blank=True)
    current_approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='applications_assigned')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    submission_cycle = models.PositiveSmallIntegerField(default=1)
    current_stage = models.ForeignKey('workflows.ApplicationStage', on_delete=models.SET_NULL, null=True, blank=True, related_name='+', help_text='The live workflow stage awaiting (or last acted on) this application.')
    working_days = models.PositiveSmallIntegerField(null=True, blank=True)
    calendar_days = models.PositiveSmallIntegerField(null=True, blank=True)
    financial_year_label = models.CharField(max_length=16, null=True, blank=True)
    rules_snapshot = models.JSONField(null=True, blank=True)
    row_version = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self) -> str:
        ref = self.reference_number or 'Draft'
        return f'LeaveApplication({ref} - {self.employee})'

    @property
    def workflow_chain_cycle(self) -> int:
        """The cycle the live workflow chain was created under.

        Resubmission reuses the original stage chain, so stage rows keep the
        cycle of the first submission. Decision-time rules keep working off
        ``submission_cycle``; chain lookups (which stage is pending, what comes
        next) must use this property so they never filter against a cycle the
        stages were not created under.
        """
        return self.stages.aggregate(chain=Min('submission_cycle'))['chain'] or 1

class SupportingDocument(models.Model):

    class Status(models.TextChoices):
        ACTIVE = ('active', 'Active')
        RETIRED = ('retired', 'Retired')

    class RetireReason(models.TextChoices):
        REPLACED = ('replaced', 'Replaced')
        REMOVED = ('removed', 'Removed')
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(LeaveApplication, on_delete=models.CASCADE, related_name='documents')
    file_path = models.CharField(max_length=512)
    file_url = models.URLField()
    file_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField()
    content_type = models.CharField(max_length=100)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    retired_at = models.DateTimeField(null=True, blank=True)
    retired_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='retired_documents')
    retire_reason = models.CharField(max_length=20, choices=RetireReason.choices, null=True, blank=True)
    replaced_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replaced_documents')

    class Meta:
        ordering = ['-uploaded_at']
        indexes = [models.Index(fields=['application', 'status'])]

    def __str__(self) -> str:
        return f'Document({self.file_name})'

class ReferenceSequence(models.Model):
    """Per-financial-year reference counter (Unit 14, decision D8).

    Each financial year has its own independent, never-reused sequence; the
    ``reference_number`` unique constraint on ``LeaveApplication`` is the final
    safety net against a collision.
    """
    financial_year_label = models.CharField(max_length=16, unique=True)
    last_value = models.PositiveIntegerField(default=0)

    def __str__(self) -> str:
        return f'RefSeq({self.financial_year_label}: {self.last_value})'