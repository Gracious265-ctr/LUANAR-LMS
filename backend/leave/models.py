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