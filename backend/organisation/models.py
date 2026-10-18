from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from users.models import User


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
        db_table = "workflows_approverrole"
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
        db_table = "workflows_campus"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Team(models.Model):
    """A group of employees sharing one or more approval workflows.

    A team may own several chains (``Workflow.team``) and every one of them can
    be in force at the same time. Which chain an application follows is not a
    property of the team but of the applicant: each employee is a normal member
    of exactly one of the team's workflows (:class:`workflows.models.WorkflowMember`)
    and routes through that one, so two people on the same team can be inside
    two different chains simultaneously.
    """

    class Status(models.TextChoices):
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
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "workflows_team"
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


class RoleAssignment(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="role_assignments"
    )
    role = models.ForeignKey(
        ApproverRole, on_delete=models.PROTECT, related_name="role_assignments"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "workflows_roleassignment"
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
    is_team_manager = models.BooleanField(
        default=False,
        help_text=(
            "Whether this team-wide holder is the team's designated manager. "
            "A manager may manage the team's members and workflows; at most one "
            "holder on a team carries this flag."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "workflows_teamroleassignment"
        ordering = ["team", "role"]
        constraints = [
            models.UniqueConstraint(
                fields=["team", "role"], name="teamroleassignment_team_role_unique"
            ),
            models.UniqueConstraint(
                fields=["team"],
                condition=models.Q(is_team_manager=True),
                name="teamroleassignment_one_manager_per_team",
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
        db_table = "workflows_campusroleassignment"
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
