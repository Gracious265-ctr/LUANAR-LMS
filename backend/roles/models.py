"""Role registry (split from the former organisation app)."""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class ApproverRole(models.Model):
    """A named approval role that may be required by any workflow."""

    class HistoryScope(models.TextChoices):
        ALL = "all", "Full history"
        SAME_TEAM = "same_team", "Same team only"
        SAME_CAMPUS = "same_campus", "Same campus only"
        SAME_FACULTY = "same_faculty", "Same faculty only"
        CURRENT_FINANCIAL_YEAR = "current_financial_year", "Current financial year only"
        NONE = "none", "No history"

    code = models.SlugField(
        unique=True,
        help_text=(
            "Stable identifier. Immutable once any stage or member references it."
        ),
    )
    label = models.CharField(
        max_length=80,
        help_text="Human-readable name shown wherever the role appears.",
    )
    description = models.TextField(
        blank=True,
        default="",
        help_text="What this role is responsible for.",
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


class RoleAssignment(models.Model):
    """An institution-wide holding of an :class:`ApproverRole`."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="role_assignments",
    )
    role = models.ForeignKey(
        ApproverRole,
        on_delete=models.PROTECT,
        related_name="role_assignments",
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
