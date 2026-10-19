from datetime import date

from django.db import models
from django.utils import timezone

from organisation.models import ApproverRole
from teams.models import Team
from users.models import User


class Workflow(models.Model):
    """A configured approval sequence for a group of employees.

    A workflow is *owned* by exactly one :class:`Team` (:attr:`team`), which is
    what makes "workflow listing for a team" answerable: a team may hold several
    workflows — a replacement chain built alongside the live one, or one per
    campus unit — and HR configures each of them independently. Ownership is
    deliberately separate from :attr:`Team.workflow`, the single workflow that
    actually routes: a team owns many, routes one, and picks which.

    At submission the applicant's team selects the routing workflow, and that
    workflow's ordered :class:`Section` rows are who may act at each step.

    There is no employee category filter. It was a free-text scope field that
    routing never consulted, so two workflows that looked scoped differently
    could route identically — and HR reading the configuration could not tell
    which one an employee's application would use. Scoping is the team, and only
    the team.
    """

    name = models.CharField(max_length=200, unique=True)
    team = models.ForeignKey(
        "teams.Team",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="workflows",
        help_text=(
            "The team that owns this workflow. Null only for a workflow built "
            "outside a team (imported, or being built before its team exists). "
            "Owning a workflow does not route it — Team.workflow does."
        ),
    )
    effective_from = models.DateField(
        null=True,
        blank=True,
        help_text="Blank keeps the workflow a draft; set a date to schedule it.",
    )
    # The academic calendar the chain is written against: a chain is a
    # statement about a term, not about forever, so a new one is scoped to the
    # current academic year's end rather than left open-ended. Blank stays
    # possible only where an older row predates the field.
    effective_to = models.DateField(
        null=True,
        blank=True,
        help_text=(
            "The last day this chain is in force. Defaults to the end of the "
            "academic calendar when the chain is created."
        ),
    )
    is_active = models.BooleanField(default=True)

    class Meta:
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
        """Derived lifecycle state: draft, scheduled, active, or inactive."""
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
    """One mandatory approval step in a workflow: one role and one approver.

    A workflow is a sequence of sections. Each section names the role its
    approver acts as (:attr:`approver_role`) and the one person who does it
    (:attr:`approver`). Exactly one of each, never a list and never a parallel
    pair: stages run in order, and a stage nobody can be jointly responsible for
    has no single person to decide whether it is done.

    :attr:`approver` is the configured answer. :class:`SectionMember` rows stay
    as the effective-dated **record** of who was entitled to act and when — see
    :meth:`SectionMember` — so changing the approver closes one period and opens
    another rather than rewriting the past.
    """

    workflow = models.ForeignKey(
        Workflow, on_delete=models.CASCADE, related_name="sections"
    )
    name = models.CharField(
        max_length=200,
        help_text="What this step is for, as HR labels it (e.g. 'Supervisor review').",
    )
    order = models.PositiveIntegerField()
    approver_role = models.ForeignKey(
        ApproverRole,
        on_delete=models.PROTECT,
        related_name="sections",
        help_text=(
            "The role this section's approver acts as. Held on the section rather "
            "than on the approver so the snapshot an in-flight application is "
            "judged by is fixed when the chain is materialised."
        ),
    )
    approver = models.ForeignKey(
        "users.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="approver_sections",
        help_text=(
            "The one person who acts at this step. Must be a member of the owning "
            "team unless the role is institution-wide. Blank means nobody can act "
            "here yet, which the team's readiness check reports and activation "
            "refuses."
        ),
    )
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)

    @property
    def memberships(self):
        """All member periods for this step, open and closed.

        Served from ``all_objects`` so the record is the point: a closed period
        is how "who held this step in March" stays answerable after the answer
        changed. The reverse relation (:attr:`SectionMember.section`) defaults to
        the open-periods manager, which is what "who may act today" answers but
        not what this property is for.
        """
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
            # One employee on one stage per workflow (Unit 30). Scoped to the
            # workflow, not globally: the same person is the Supervisor on one
            # team's chain and the Bursar on another's without either chain
            # being wrong. It also makes "the applicant's stage" a single stage,
            # which is what the skip-forward routing resolves against.
            models.UniqueConstraint(
                fields=["workflow", "approver"],
                name="section_workflow_approver_unique",
            ),
            # One role on one stage per workflow. A role appearing twice would
            # mean the same capacity signing off twice at two different points
            # in one chain, which is not a thing HR can explain afterwards.
            models.UniqueConstraint(
                fields=["workflow", "approver_role"],
                name="section_workflow_role_unique",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.order}. {self.name} ({self.approver_role.label})"


class OpenSectionMembershipManager(models.Manager):
    """Only memberships that are currently in force.

    :class:`SectionMember` is effective-dated, so the same person can hold the
    same section across several separate periods. The default manager returns
    the open rows only, which is what every "who may act for this section
    today" question wants and what keeps a historical period from being counted
    twice. ``all_objects`` is the full history.
    """

    def get_queryset(self):
        return super().get_queryset().filter(effective_to__isnull=True)


class SectionMemberQuerySet(models.QuerySet):
    def effective_on(self, on: date | None = None) -> "SectionMemberQuerySet":
        """Rows whose period covers ``on`` (today by default)."""
        day = on or timezone.localdate()
        return self.filter(effective_from__lte=day).filter(
            models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=day)
        )


class SectionMember(models.Model):
    """One period during which a person was the approver of a :class:`Section`.

    :attr:`Section.approver` is the single person a step routes to. This row is
    the **record** of that: the period during which the person held the step.
    Changing a step's approver closes one period and opens another, so "who
    approved this in March" stays answerable long after the answer changed.

    A member holds no role of its own — the role belongs to the section. A member
    *acts as* the section's role, so the snapshot an in-flight application is
    judged by (:class:`ApplicationStage`) is fixed at materialisation and cannot
    shift when HR edits membership later (invariant 12.5).

    Membership is **effective-dated rather than deleted**. Removing someone from
    a section closes the period (``effective_to``) instead of dropping the row,
    because a row that used to be pointed at is a record of who *could* have
    acted; a hard delete would quietly rewrite the past and leave no way to
    explain an application that someone with no current membership approved.
    Only one period per (section, user) may be open at a time.
    """

    objects = OpenSectionMembershipManager.from_queryset(SectionMemberQuerySet)()
    all_objects = models.Manager()

    section = models.ForeignKey(
        "workflows.Section", on_delete=models.CASCADE, related_name="members"
    )
    user = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="section_memberships"
    )
    effective_from = models.DateField(
        default=timezone.localdate,
        help_text="The first date this person is eligible to act for the section.",
    )
    effective_to = models.DateField(
        null=True,
        blank=True,
        help_text=(
            "The last date this person is eligible to act for the section; "
            "blank while the membership is open."
        ),
    )
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
        """True when ``on`` (today by default) falls inside this period."""
        day = on or timezone.localdate()
        if self.effective_from > day:
            return False
        return self.effective_to is None or self.effective_to >= day

    def __str__(self) -> str:
        period = (
            f"{self.effective_from} → {self.effective_to or 'open'}"
        )
        return f"{self.user.get_full_name()} — {self.section.name} ({period})"


class WorkflowMember(models.Model):
    """One person who is a normal member of a workflow's team.

    Distinct from :class:`Section.approver`: those are the people who decide
    each approval step. A workflow member is part of the team's eligibility
    pool — an employee whose leave routes through the workflow and who may be
    offered as a normal workflow participant — without being appointed to any
    step.

    A person is a member of at most one workflow per team
    (``workflow_member_team_user_unique``). The ``team`` column is denormalised
    from :attr:`Workflow.team` at write time so that uniqueness is enforceable
    at the database level rather than only in a service check that two
    concurrent requests could both pass.

    The exception is a **wide approver** — somebody who holds an
    institution-wide :class:`RoleAssignment`, a team-wide
    :class:`TeamRoleAssignment` on this team, or a campus-wide
    :class:`CampusRoleAssignment` at this team's campus. A wide approver
    staffs several chain *automatically* from one holding, so they are the one
    person a team may legitimately place on more than one of its chains —
    the team's second chain is built by reassigning the same registrar or
    bursar, not by moving them off the first. To allow that the uniqueness
    constraint above is conditional on :attr:`is_wide_approver`: a non-wide
    member is still one workflow per team, a wide one may sit on several.

    :attr:`is_wide_approver` is denormalised from the live holdings at write
    time purely so the conditional constraint is expressible; eligibility is
    always judged against the live holdings, never against this flag.
    """

    workflow = models.ForeignKey(
        Workflow,
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
        Team,
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
