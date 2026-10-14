from django.db import models

from users.models import User


class Reassignment(models.Model):
    """An HR emergency reassignment of a pending application to an approver.

    ``from_approver`` records who the application was previously with and may be
    ``None`` when a submitted application had not yet been routed (the first
    reassignment is effectively an initial assignment). Reassigning atomically
    writes this history row and updates
    ``LeaveApplication.current_approver`` — the live responsible-approver spine
    Unit 21 consumes.
    """

    application = models.ForeignKey(
        "leave.LeaveApplication",
        on_delete=models.PROTECT,
        related_name="reassignments",
        help_text="The pending leave application being reassigned.",
    )
    from_approver = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="reassignments_from",
        null=True,
        blank=True,
        help_text="The approver the application was previously assigned to.",
    )
    to_approver = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="reassignments_to",
        help_text="The replacement approver who inherits the pending application.",
    )
    reason = models.TextField(
        help_text="HR's mandatory reason for the reassignment.",
    )
    decided_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="reassignments_decided",
        help_text="The HR user who performed the reassignment.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        application = self.application.reference_number or "Draft"
        return f"Reassignment({application} → {self.to_approver.get_full_name()})"


class WorkflowMember(models.Model):
    """One person who is a normal member of a workflow's team.

    Distinct from the section approver: those are the people who decide each
    approval step. A workflow member is part of the team's eligibility pool —
    an employee whose leave routes through the workflow and who may be offered
    as a normal workflow participant — without being appointed to any step.

    A person is a member of at most one workflow per team
    (``workflow_member_team_user_unique``). The ``team`` column is denormalised
    from :attr:`org.Workflow.team` at write time so that uniqueness is
    enforceable at the database level rather than only in a service check that
    two concurrent requests could both pass.
    """

    workflow = models.ForeignKey(
        "org.Workflow",
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
        "org.Team",
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
