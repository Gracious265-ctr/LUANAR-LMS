from django.core.exceptions import ValidationError
from django.db import models

from users.models import User


class ApproverRole(models.Model):
    """An HR-managed approver role a workflow stage can require.

    Roles are data, not a hardcoded code list: HR creates, labels, and retires
    them, and workflow stages plus team members reference them by foreign key.

    A role is never deleted. ``is_active`` is a soft retire, refused while the
    role is in use (referenced by an active workflow stage, by a member of an
    active team, or held by an active user through a ``RoleAssignment``), so a
    stage can never be left pointing at a role that has quietly disappeared.
    """

    class HistoryScope(models.TextChoices):
        """What leave history an approver in this role may see."""

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
    """A physical campus in the institution.

    A campus is HR-maintained reference data, not something an employee edits.
    A team may optionally belong to one, which lets HR ask "who approves at this
    campus" without making a free-text field that quietly accumulates typos
    ("Main campus", "main campus", "MAIN").
    """

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


class RoleAssignment(models.Model):
    """An institution-wide holding of an :class:`ApproverRole`.

    Only roles with ``is_institution_wide = True`` can be assigned this way;
    every other role is held through a :class:`TeamMember`, which is what makes
    "who approves what" a property of the team rather than of the person.

    A role has exactly **one** institution-wide approver going forward: the
    service writing a holding refuses to assign a role that already has one,
    naming the current holder, and the Approvers picker does not offer a role
    that has a holder — changing the holder is remove the current one first,
    then assign. Legacy rows that predate the rule (a role with several
    institution holders) are still read as the ambiguity they are, and left
    unstaffed rather than auto-decided.
    """

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
        """Reject a non-institution-wide role; point HR at team membership."""
        super().clean()
        if self.role_id is None:
            return
        if not self.role.is_institution_wide:
            raise ValidationError(
                {
                    "role": (
                        f'"{self.role.label}" is a team role, not an '
                        "institution-wide role. Mark it institution-wide to assign "
                        "it here, or add this person to the team that uses it."
                    )
                }
            )


class CampusRoleAssignment(models.Model):
    """A **campus-wide** holding of an :class:`ApproverRole`.

    One holder per role per campus, and a campus-wide approver only ever
    decides for teams at that same campus — :attr:`Team.campus` is what scopes
    it, so "the Campus Registrar approves for every team at Omu" is written
    once here and resolves for each of them, and for no team anywhere else.

    Only an academic team has a campus, so this is the wide holding that sits
    between the team and the institution: team-wide first, then the applicant's
    own campus, then — for an administration team only — the institution.
    """

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
                {
                    "role": (
                        f'"{self.role.label}" is an institution-wide role. Assign '
                        "its holder under Approvers, not on a campus."
                    )
                }
            )
        if not self.role.is_active:
            raise ValidationError(
                {"role": f'"{self.role.label}" is retired and cannot be assigned.'}
            )
        if not self.campus.is_active:
            raise ValidationError(
                {"campus": f'"{self.campus.name}" is retired and cannot hold approvers.'}
            )
