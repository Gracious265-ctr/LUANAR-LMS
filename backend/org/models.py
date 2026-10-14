from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from users.models import EmployeeProfile, User


class ApproverRole(models.Model):
    """An HR-managed approver role a workflow stage can require."""

    class HistoryScope(models.TextChoices):
        ALL = "all", "Full history"
        SAME_TEAM = "same_team", "Same team only"
        SAME_CAMPUS = "same_campus", "Same campus only"
        SAME_FACULTY = "same_faculty", "Same faculty only"
        CURRENT_FINANCIAL_YEAR = (
            "current_financial_year",
            "Current financial year only",
        )
        NONE = "none", "No history"

    code = models.SlugField(
        max_length=50,
        unique=True,
        help_text="Stable identifier. Immutable once any stage or member references it.",
    )
    label = models.CharField(
        max_length=80,
        help_text="Human-readable name shown wherever the role appears.",
    )
    description = models.TextField(
        blank=True, default="", help_text="What this role is responsible for."
    )
    is_active = models.BooleanField(default=True)
    history_scope = models.CharField(
        max_length=32,
        choices=HistoryScope.choices,
        default=HistoryScope.CURRENT_FINANCIAL_YEAR,
        help_text="Which leave history an approver in this role may see.",
    )
    handles_cancellation = models.BooleanField(
        default=False,
        help_text="Whether this role's stages decide Unit 18 cancellation requests.",
    )
    is_institution_wide = models.BooleanField(
        default=False,
        help_text=(
            "Whether the role may be resolved from a global role assignment when "
            "a team has no member holding it."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["label"]

    def __str__(self) -> str:
        return self.label


class Campus(models.Model):
    """A physical campus in the institution."""

    name = models.CharField(max_length=200, unique=True)
    code = models.SlugField(max_length=50, unique=True)
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Team(models.Model):
    """A group of employees sharing one approval workflow."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    class Category(models.TextChoices):
        ACADEMIC = "academic", "Academic"
        ADMINISTRATION = "administration", "Administration"

    name = models.CharField(max_length=200, unique=True)
    code = models.SlugField(max_length=50, unique=True)
    description = models.TextField(blank=True, default="")
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.ADMINISTRATION,
        help_text=(
            "Academic teams sit at a campus and may use campus-wide "
            "approvers; administration teams are institution-wide and may use "
            "institution-wide approvers."
        ),
    )
    campus = models.ForeignKey(
        Campus,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="teams",
        help_text=(
            "The campus an academic team sits at; required when the category is "
            "Academic and not allowed when it is Administration."
        ),
    )
    workflow = models.OneToOneField(
        "org.Workflow",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="routed_by",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_from__isnull=True)
                | models.Q(effective_to__gte=models.F("effective_from")),
                name="team_effective_window_ordered",
            )
        ]

    @property
    def is_effective(self) -> bool:
        today = timezone.localdate()
        if self.effective_from is not None and self.effective_from > today:
            return False
        if self.effective_to is not None and self.effective_to < today:
            return False
        return True

    def clean(self) -> None:
        super().clean()
        errors = {}
        if self.category == self.Category.ACADEMIC and self.campus_id is None:
            errors["campus"] = "An academic team sits at a campus."
        if self.category == self.Category.ADMINISTRATION and self.campus_id is not None:
            errors["campus"] = "An administration team is not campus-based."
        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.name} ({self.get_status_display()})"


class OpenSectionMembershipManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(effective_to__isnull=True)


class SectionMemberQuerySet(models.QuerySet):
    def effective_on(self, on: date | None = None) -> "SectionMemberQuerySet":
        day = on or timezone.localdate()
        return self.filter(effective_from__lte=day).filter(
            models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=day)
        )


class SectionMember(models.Model):
    objects = OpenSectionMembershipManager.from_queryset(SectionMemberQuerySet)()
    all_objects = models.Manager()

    section = models.ForeignKey(
        "org.Section", on_delete=models.CASCADE, related_name="members"
    )
    user = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="section_memberships"
    )
    effective_from = models.DateField(default=timezone.localdate)
    effective_to = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["section", "user", "effective_from"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gte=models.F("effective_from")),
                name="sectionmember_effective_window_ordered",
            ),
            models.UniqueConstraint(
                fields=["section", "user"],
                condition=models.Q(effective_to__isnull=True),
                name="sectionmember_open_section_user_unique",
            ),
        ]

    def is_effective(self, on: date | None = None) -> bool:
        day = on or timezone.localdate()
        if self.effective_from > day:
            return False
        return self.effective_to is None or self.effective_to >= day

    def __str__(self) -> str:
        period = f"{self.effective_from} → {self.effective_to or 'open'}"
        return f"{self.user.get_full_name()} — {self.section.name} ({period})"


class RoleAssignment(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="role_assignments"
    )
    role = models.ForeignKey(
        ApproverRole, on_delete=models.PROTECT, related_name="role_assignments"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["role", "user"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "role"], name="roleassignment_user_role_unique"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user.get_full_name()} — {self.role.label} (institution-wide)"

    def clean(self) -> None:
        super().clean()
        if self.role_id is None:
            return
        if not self.role.is_institution_wide:
            raise ValidationError(
                {
                    "role": (
                        f'"{self.role.label}" is a team role, not an '
                        "institution-wide role."
                    )
                }
            )


class TeamRoleAssignment(models.Model):
    team = models.ForeignKey(
        Team, on_delete=models.CASCADE, related_name="role_assignments"
    )
    role = models.ForeignKey(
        ApproverRole, on_delete=models.PROTECT, related_name="team_role_assignments"
    )
    user = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="team_role_assignments"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["team", "role"]
        constraints = [
            models.UniqueConstraint(
                fields=["team", "role"], name="teamroleassignment_team_role_unique"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.team.name}: {self.role.label} — {self.user.get_full_name()}"

    def clean(self) -> None:
        super().clean()
        if self.role_id is None or self.team_id is None:
            return
        if self.role.is_institution_wide:
            raise ValidationError(
                {"role": '"%s" is an institution-wide role.' % self.role.label}
            )
        if not self.role.is_active:
            raise ValidationError(
                {"role": '"%s" is retired and cannot be assigned.' % self.role.label}
            )


class CampusRoleAssignment(models.Model):
    campus = models.ForeignKey(
        Campus, on_delete=models.CASCADE, related_name="role_assignments"
    )
    role = models.ForeignKey(
        ApproverRole,
        on_delete=models.PROTECT,
        related_name="campus_role_assignments",
    )
    user = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="campus_role_assignments"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["campus", "role"]
        constraints = [
            models.UniqueConstraint(
                fields=["campus", "role"],
                name="campusroleassignment_campus_role_unique",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.campus.name}: {self.role.label} — {self.user.get_full_name()}"

    def clean(self) -> None:
        super().clean()
        if self.role_id is None or self.campus_id is None:
            return
        if self.role.is_institution_wide:
            raise ValidationError(
                {"role": '"%s" is an institution-wide role.' % self.role.label}
            )
        if not self.role.is_active:
            raise ValidationError(
                {"role": '"%s" is retired and cannot be assigned.' % self.role.label}
            )
        if not self.campus.is_active:
            raise ValidationError(
                {"campus": '"%s" is retired and cannot hold approvers.' % self.campus.name}
            )


class Workflow(models.Model):
    name = models.CharField(max_length=200, unique=True)
    team = models.ForeignKey(
        "org.Team",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="workflows",
    )
    effective_from = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    @property
    def state(self) -> str:
        if self.effective_from is None:
            return "draft"
        if not self.is_active:
            return "inactive"
        if self.effective_from > timezone.localdate():
            return "scheduled"
        return "active"

    def __str__(self) -> str:
        return f"{self.name} ({self.state})"


class Section(models.Model):
    workflow = models.ForeignKey(
        Workflow, on_delete=models.CASCADE, related_name="sections"
    )
    name = models.CharField(max_length=200)
    order = models.PositiveIntegerField()
    approver_role = models.ForeignKey(
        ApproverRole,
        on_delete=models.PROTECT,
        related_name="sections",
    )
    approver = models.ForeignKey(
        "users.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="approver_sections",
    )
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)

    @property
    def memberships(self):
        return SectionMember.all_objects.filter(section=self).order_by(
            "effective_from", "id"
        )

    class Meta:
        ordering = ["order"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(order__gte=1),
                name="section_order_gte_1",
            ),
            models.UniqueConstraint(
                fields=["workflow", "order"],
                name="section_workflow_order_unique",
            ),
            models.UniqueConstraint(
                fields=["workflow", "approver"],
                name="section_workflow_approver_unique",
            ),
            models.UniqueConstraint(
                fields=["workflow", "approver_role"],
                name="section_workflow_role_unique",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.order}. {self.name} ({self.approver_role.label})"


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
