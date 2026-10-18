from datetime import date

from django.db import models
from django.utils import timezone

from organisation.models import ApproverRole
from users.models import User


class Workflow(models.Model):
    name = models.CharField(max_length=200, unique=True)
    team = models.ForeignKey(
        "organisation.Team",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="workflows",
    )
    effective_from = models.DateField(null=True, blank=True)
    # The academic calendar the chain is written against: a chain is a
    # statement about a term, not about forever, so a new one is scoped to the
    # current academic year's end rather than left open-ended. Blank stays
    # possible only where an older row predates the field.
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "workflows_workflow"
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_from__isnull=True)
                | models.Q(effective_to__gte=models.F("effective_from")),
                name="workflow_effective_window_ordered",
            ),
        ]

    @property
    def state(self) -> str:
        if self.effective_from is None:
            return "draft"
        if not self.is_active:
            return "inactive"
        if self.effective_to is not None and self.effective_to < timezone.localdate():
            return "inactive"
        if self.effective_from > timezone.localdate():
            return "scheduled"
        return "active"

    @property
    def is_effective(self) -> bool:
        """Whether this chain is in force today — window and flag together."""
        return self.state == "active"

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
        db_table = "workflows_section"
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
        "workflows.Section", on_delete=models.CASCADE, related_name="members"
    )
    user = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="section_memberships"
    )
    effective_from = models.DateField(default=timezone.localdate)
    effective_to = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "workflows_sectionmember"
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


class WorkflowMember(models.Model):
    """One person who is a normal member of a workflow's team.

    Distinct from the section approver: those are the people who decide each
    approval step. A workflow member is part of the team's eligibility pool —
    an employee whose leave routes through the workflow and who may be offered
    as a normal workflow participant — without being appointed to any step.

    A person is a member of at most one workflow per team
    (``workflow_member_team_user_unique``). The ``team`` column is denormalised
    from :attr:`organisation.Workflow.team` at write time so that uniqueness is
    enforceable at the database level rather than only in a service check that
    two concurrent requests could both pass.
    """

    workflow = models.ForeignKey(
        "workflows.Workflow",
        on_delete=models.CASCADE,
        related_name="workflow_members",
        help_text=(
            "The workflow whose team this person is a normal member of. "
            "Removing the workflow removes the membership with it."
        ),
    )
    user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="workflow_memberships",
        help_text=(
            "The employee who is a normal member of the workflow's team. "
            "Must already be on that team; the service refuses anyone else."
        ),
    )
    team = models.ForeignKey(
        "organisation.Team",
        on_delete=models.CASCADE,
        related_name="workflow_member_assignments",
        help_text=(
            "The owning team, copied from the workflow when the membership is "
            "written. Denormalised so one employee cannot be a normal member "
            "of two workflows of the same team, even under concurrent writes."
        ),
    )
    added_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        help_text="The HR user who recorded this membership.",
    )
    is_wide_approver = models.BooleanField(
        default=False,
        help_text=(
            "Denormalised from the wide-approver holdings (institution-wide, "
            "team-wide on this team, or campus-wide at this team's campus) at "
            "the time the membership was written, so the database can enforce "
            "that a primary member sits on one workflow per team while a wide "
            "approver may sit on several. Eligibility is always re-checked "
            "against the live holdings; this flag only backs the constraint."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["user__first_name", "user__last_name", "user_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["workflow", "user"],
                name="workflow_member_workflow_user_unique",
            ),
            models.UniqueConstraint(
                fields=["team", "user"],
                condition=models.Q(is_wide_approver=False),
                name="workflow_member_team_user_unique",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user.get_full_name()} on {self.workflow.name}"
