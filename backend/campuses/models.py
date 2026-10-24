"""Campus registry (split from the former organisation app)."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from roles.models import ApproverRole


class Campus(models.Model):
    """A physical/campus unit used to scope campus-wide approvals."""

    name = models.CharField(max_length=200, unique=True)
    code = models.SlugField(unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "workflows_campus"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class CampusRoleAssignment(models.Model):
    """A campus-wide holding of an :class:`ApproverRole`."""

    campus = models.ForeignKey(
        Campus, on_delete=models.CASCADE, related_name="role_assignments"
    )
    role = models.ForeignKey(
        ApproverRole,
        on_delete=models.PROTECT,
        related_name="campus_role_assignments",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="campus_role_assignments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "workflows_campusroleassignment"
        ordering = ["campus", "role"]
        constraints = [
            models.UniqueConstraint(
                fields=["campus", "role"], name="campusroleassignment_campus_role_unique"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user.get_full_name()} — {self.role.label} ({self.campus.name})"
