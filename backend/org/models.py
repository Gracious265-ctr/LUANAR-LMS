from django.conf import settings
from django.db import models


class OrgUnit(models.Model):
    """An organisation unit mirrored from the external directory.

    Rows are owned by the organisation data provider's sync
    (``org.services.sync_org_structure_from_provider``): ``external_id`` is the
    provider's key, and a re-sync updates units in place rather than creating
    duplicates. This is the minimum of the unbuilt org-tree blueprint the
    sync needs — the full blueprint will extend it with its own behaviour.
    """

    class UnitType(models.TextChoices):
        INSTITUTION = "institution", "Institution"
        CAMPUS = "campus", "Campus"
        FACULTY = "faculty", "Faculty"
        DEPARTMENT_ACADEMIC = "department_academic", "Academic Department"
        DEPARTMENT_ADMIN = "department_admin", "Administrative Department"
        TEAM = "team", "Team"

    external_id = models.CharField(max_length=100, unique=True)
    unit_type = models.CharField(max_length=30, choices=UnitType.choices)
    name = models.CharField(max_length=200)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="children",
    )
    has_teams = models.BooleanField(
        default=False,
        help_text="Whether this unit is composed of teams.",
    )
    designated_approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="org_units",
    )

    class Meta:
        ordering = ["unit_type", "name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_unit_type_display()})"
