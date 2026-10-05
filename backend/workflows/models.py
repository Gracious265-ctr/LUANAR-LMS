from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from users.models import EmployeeProfile, User


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
        SAME_DEPARTMENT = "same_department", "Same department only"
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
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Team(models.Model):
    """A group of employees sharing one approval workflow, inside a department.

    A team owns at most one :class:`Workflow` — one-to-one, never shared. At
    submission time the applicant's team is what selects the workflow — there is
    no category/department matching — and that workflow's :class:`Section` rows
    are who may act at each step.

    A :class:`users.models.Department` holds **one or more** teams. The department
    is what scopes approvers: only an employee in the same department may be made
    a team's approver, and one employee keeps one role across every team of that
    department. It is not a routing key — routing follows the team.

    The chain exists *because* the team does, and is written in the same request
    as the team. There is deliberately no reusable chain a second team can be
    pointed at: a shared chain makes "edit this team's approval steps" and
    "silently re-route someone else's applications" the same action, which is
    not an edit HR can be asked to perform safely.

    :attr:`workflow` is **nullable**, and null only while the team is being
    configured. HR creates a team's identity first and its approval chain
    second, so a draft team is a real, inspectable object before it can route;
    :func:`workflows.services.activate_team` refuses to put a team with no chain
    into force, so the window in which a team exists without one can never
    overlap the window in which it routes.

    The lifecycle is one authoritative field, :attr:`status`, and it is
    deliberately a three-value choice rather than a boolean:

    ``DRAFT``
        Being configured. A draft team is invisible to routing, so a
        half-finished configuration cannot strand an employee's application.
    ``ACTIVE``
        The only status that routes (invariant 12.5). Reaching it is a separate,
        validated action — see :func:`workflows.services.activate_team`.
    ``INACTIVE``
        Retired but retained. The team keeps its configuration and every
        historical stage snapshot that points at it, so applications already in
        flight can still be read and decided.

    :attr:`effective_from` / :attr:`effective_to` are the window the team is
    *operative* inside, which is a different question from its status: a team
    whose window has closed is inactive for routing even while its status still
    reads ``ACTIVE``, and HR is told so rather than being allowed to assume the
    configuration still applies.
    """

    class Status(models.TextChoices):
        """The team's lifecycle, and the single field that says which."""

        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    name = models.CharField(max_length=200, unique=True)
    code = models.SlugField(max_length=50, unique=True)
    description = models.TextField(blank=True, default="")
    department = models.ForeignKey(
        "users.Department",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="teams",
        help_text=(
            "The department this team belongs to. A department holds one or "
            "more teams. It is what scopes approvers — only an employee in "
            "this department may be made this team's approver — but it is not "
            "a routing key: routing follows the team."
        ),
    )
    campus = models.ForeignKey(
        Campus,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="teams",
        help_text=(
            "The campus this team belongs to; blank when the team is not "
            "campus-based. Informational — routing always follows the team."
        ),
    )
    workflow = models.OneToOneField(
        "workflows.Workflow",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="team",
        help_text=(
            "The approval workflow this team is routed through. One-to-one, not "
            "a foreign key: a chain belongs to the team it was built for, and a "
            "shared chain would mean editing one team's steps silently "
            "re-routing every other team pointing at it. It owns the sections, "
            "so its steps define who may act for this team. Blank only while "
            "the team is still a draft being configured."
        ),
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        help_text=(
            "Draft teams do not route. Only an active team inside its "
            "effective dates routes an application."
        ),
    )
    effective_from = models.DateField(
        null=True,
        blank=True,
        help_text=(
            "The first date this team routes applications. Blank means active "
            "from the moment it is activated."
        ),
    )
    effective_to = models.DateField(
        null=True,
        blank=True,
        help_text=(
            "The last date this team routes applications; blank routes "
            "indefinitely. Past this date the team is retired for routing while "
            "its configuration is kept."
        ),
    )
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
        """True when today falls inside the team's effective window.

        A blank bound is open-ended, so a team with no dates is always inside
        its window and only its ``status`` decides whether it routes.
        """
        today = timezone.localdate()
        if self.effective_from is not None and self.effective_from > today:
            return False
        if self.effective_to is not None and self.effective_to < today:
            return False
        return True

    def __str__(self) -> str:
        return f"{self.name} ({self.get_status_display()})"


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


class RoleAssignment(models.Model):
    """An institution-wide holding of an :class:`ApproverRole`.

    Only roles with ``is_institution_wide = True`` can be assigned this way;
    every other role is held through a :class:`TeamMember`, which is what makes
    "who approves what" a property of the team rather than of the person.
    """

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


class Workflow(models.Model):
    """A configured approval sequence for a group of employees."""

    name = models.CharField(max_length=200, unique=True)
    employee_category = models.CharField(
        max_length=20,
        choices=EmployeeProfile.Category.choices,
        blank=True,
        help_text="Blank applies the workflow to every employee category.",
    )
    department = models.CharField(
        max_length=200,
        blank=True,
        help_text="Blank applies the workflow to every department.",
    )
    effective_from = models.DateField(
        null=True,
        blank=True,
        help_text="Blank keeps the workflow a draft; set a date to schedule it.",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    @property
    def scope(self) -> tuple[str, str]:
        """The (category, department) a workflow applies to; blank means any."""
        return (self.employee_category or "", self.department or "")

    @property
    def state(self) -> str:
        """Derived lifecycle state: draft, scheduled, active, or inactive."""
        if self.effective_from is None:
            return "draft"
        if not self.is_active:
            return "inactive"
        if self.effective_from > timezone.localdate():
            return "scheduled"
        return "active"

    def __str__(self) -> str:
        scope = self.employee_category or "All categories"
        if self.department:
            scope = f"{scope} / {self.department}"
        return f"{self.name} ({scope})"


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
        help_text="What this step is for, as HR labels it (e.g. 'Departmental review').",
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
            "The single person who approves this step. Must be in the owning "
            "team's department, and must already hold the role above for that "
            "department. Blank means the step is not staffed yet, which the "
            "team's readiness check reports and activation refuses."
        ),
    )
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)

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


class Delegation(models.Model):
    """A temporary transfer of an approver's pending decisions to a delegate.

    The delegation is person-based: a specific original approver ``User`` hands
    their pending approvals to a specific delegate ``User`` while they are
    unavailable. Applications do not exist yet, so the actual routing body is
    Unit 21; this record plus :func:`active_delegation_for` are the boundary it
    consumes.
    """

    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    approver = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="delegations_as_approver",
        help_text="The approver whose pending decisions are delegated.",
    )
    delegate = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="delegations_as_delegate",
        null=True,
        blank=True,
        help_text="The person temporarily acting for the approver; required once approved.",
    )
    starts_on = models.DateField()
    ends_on = models.DateField(
        null=True,
        blank=True,
        help_text="Blank means the delegation stays active until HR cancels it.",
    )
    request_reason = models.TextField(
        blank=True,
        help_text="The approver's reason for requesting delegation.",
    )
    requested_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="delegations_requested",
        help_text="Who submitted the request (the approver or HR on their behalf).",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.REQUESTED,
    )
    decision_reason = models.TextField(
        blank=True,
        help_text="HR's mandatory reason when approving, rejecting, or cancelling.",
    )
    decided_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="delegations_decided",
        null=True,
        blank=True,
        help_text="The HR user who decided the request.",
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
            # The service-level ``open_request_exists`` check gives the friendly
            # 400, but it is a bare SELECT ... EXISTS and two concurrent requests
            # for the same approver could both pass it. This partial unique
            # index is the database backstop that closes the race.
            models.UniqueConstraint(
                fields=["approver"],
                condition=models.Q(status="requested"),
                name="one_open_request_per_approver",
            ),
        ]

    @property
    def state(self) -> str:
        """The calendar-aware lifecycle state shown in the UI.

        ``approved`` maps to ``scheduled`` / ``active`` / ``ended`` depending on
        today against the delegation period.
        """
        if self.status == self.Status.APPROVED:
            today = timezone.localdate()
            if self.ends_on is not None and self.ends_on < today:
                return "ended"
            if self.starts_on > today:
                return "scheduled"
            return "active"
        return self.status

    def __str__(self) -> str:
        delegate = self.delegate.get_full_name() if self.delegate else "unassigned"
        return f"{self.approver.get_full_name()} → {delegate} ({self.state})"


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


class ApplicationStage(models.Model):
    """One immutable position in an application's assigned approval chain.

    Stages are created in one batch by ``assign_workflow`` when the application
    is first submitted; only the stage that ``LeaveApplication.current_stage``
    points at is live, and exactly one stage is ``pending`` at a time.

    On resubmission (Unit 17) the chain is *kept*, not rebuilt: the scheme
    keeps the same reference and the same stage/approver, so stages never leave
    the cycle they were created under. The current stage flips back to
    ``pending`` in place and ``decision_version`` increments; earlier and later
    stages are untouched and ``LieaveApplication.submission_cycle`` increments
    while stage ``submission_cycle`` stays at the chain-creation cycle. Chain
    lookups use ``LeaveApplication.workflow_chain_cycle`` (the minimum stage
    cycle, i.e. usually 1), never ``submission_cycle``.

    ``decision_version`` starts at ``1`` and is optimistically incremented every
    time the stage is acted upon (approve/reject/correction/resubmission).
    Decision requests carry the version they read; a mismatch aborts with a
    stale/conflict (409).
    """

    class Status(models.TextChoices):
        WAITING = "waiting", "Waiting"
        PENDING = "pending", "Pending action"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CORRECTION_REQUESTED = "correction_requested", "Correction requested"
        SUPERSEDED = "superseded", "Superseded by resubmission"
        # A stage the applicant's own position made unnecessary (Unit 30). An
        # approver applicant does not approve their own leave, and may not
        # approve their own leave *or* sit below the step that has to decide it,
        # so the stages at and below their own are skipped rather than routed to
        # them. Terminal: a skipped stage is never reopened, because the reason it
        # was skipped cannot change while the application is in flight.
        SKIPPED = "skipped", "Skipped"
        # A pending stage closed by an employee withdrawing their application
        # (Unit 18). The application leaves the approver queues and any decision
        # on it returns 409.
        CANCELLED = "cancelled", "Cancelled"

    application = models.ForeignKey(
        "leave.LeaveApplication",
        on_delete=models.CASCADE,
        related_name="stages",
        help_text="The application this stage belongs to.",
    )
    submission_cycle = models.PositiveSmallIntegerField(
        default=1,
        help_text="The resubmission cycle this stage belongs to.",
    )
    stage_order = models.PositiveIntegerField(
        help_text="Position in the chain, 1-based and unique per application/cycle.",
    )
    role = models.CharField(
        max_length=50,
        help_text=(
            "The approver role responsible for this stage, snapshotted as its "
            "code. Kept as a plain string — and kept forever — so a later rename "
            "or retirement of the role can never rewrite history."
        ),
    )
    role_label = models.CharField(
        max_length=80,
        help_text="Human-readable label for ``role``, snapshotted at materialization.",
    )
    role_ref = models.ForeignKey(
        ApproverRole,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="application_stages",
        help_text=(
            "The live role this stage was materialised from. Null only for rows "
            "written before roles became data; ``role`` stays authoritative in "
            "that case. Kept for traceability — not for reading behaviour."
        ),
    )
    history_scope = models.CharField(
        max_length=32,
        blank=True,
        default="",
        help_text=(
            "Snapshot of the role's leave-history scope at materialization. This "
            "— not the live role — is what an in-flight application is judged "
            "by, so widening or narrowing a role later never rewrites the review "
            "history of an application already in flight. Blank on rows written "
            "before roles became data."
        ),
    )
    handles_cancellation = models.BooleanField(
        default=False,
        help_text=(
            "Snapshot of the role's cancellation-handling flag at materialization, "
            "so an in-flight application never changes behaviour when HR edits "
            "the role."
        ),
    )
    assigned_approver = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="application_stages",
        help_text=(
            "The member of the stage's section who actually decided it, or who "
            "claimed it by acting. Null while the stage is still open, because a "
            "section is resolved by whoever acts first — the people entitled to "
            "act are the eligible_approvers snapshot, not this field."
        ),
    )
    section_ref = models.ForeignKey(
        "workflows.Section",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="application_stages",
        help_text=(
            "The live section this stage was materialised from. Null only for "
            "rows written before sections existed; the snapshotted role fields "
            "stay authoritative in that case. Kept for traceability — not for "
            "reading behaviour."
        ),
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.WAITING,
    )
    is_final = models.BooleanField(
        default=False,
        help_text="True for the last stage; approving it finalises the application.",
    )
    skip_reason = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text=(
            "Why this stage was skipped, set at materialisation and never "
            "changed. Blank on any stage that was not skipped. Recorded because a "
            "chain that visibly starts at step 2 with steps 1 marked skipped is "
            "the only way a reader can tell a deliberate skip from a stage that "
            "was quietly dropped."
        ),
    )
    decision_version = models.PositiveIntegerField(
        default=1,
        help_text="Optimistic-lock counter, incremented on every decision.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["application", "submission_cycle", "stage_order"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(stage_order__gte=1),
                name="stage_order_positive",
            ),
            models.UniqueConstraint(
                fields=["application", "submission_cycle", "stage_order"],
                name="unique_stage_order_per_application",
            ),
            models.UniqueConstraint(
                fields=["application", "submission_cycle"],
                condition=models.Q(status="pending"),
                name="unique_pending_stage_per_application",
            ),
        ]
        indexes = [
            models.Index(
                fields=["assigned_approver", "status"],
                name="idx_stage_approver_status",
            )
        ]

    def __str__(self) -> str:
        return (
            f"Stage {self.stage_order} (cycle {self.submission_cycle},"
            f" {self.role_label})"
            f" #{self.application.reference_number or self.application_id}"
        )

    def eligible_approver_ids(self) -> tuple[int, ...]:
        """The people who were entitled to act, from the snapshot.

        Reads through :class:`ApplicationStageApprover` rather than
        ``assigned_approver``, because the point of the snapshot is that
        eligibility does not change when configuration does.

        A caller that prefetched ``eligible_approvers`` is served from that
        cache, so reading a whole chain's snapshots costs one query rather than
        one per stage.
        """
        if "eligible_approvers" in getattr(
            self, "_prefetched_objects_cache", {}
        ):
            return tuple(
                sorted(
                    row.user_id
                    for row in self.eligible_approvers.all()
                )
            )
        return tuple(
            self.eligible_approvers.order_by("user_id").values_list(
                "user_id", flat=True
            )
        )


class ApplicationStageApprover(models.Model):
    """Who was entitled to act on a stage when the chain was materialised.

    A section is resolved by whoever acts first, so eligibility is a set rather
    than a single person. It is snapshotted here, at materialisation, for two
    reasons: the people entitled to an in-flight application must not change
    when HR later edits a section's membership (invariant 12.5), and the
    applicant's own membership is dropped on the way in, so self-approval is
    prevented by what was *not* written here rather than by a check that has to
    be remembered at every later read.

    Append-only. Changing who may act on a live application is an explicit
    administrative operation (reassignment), recorded in the audit log — never a
    side effect of editing configuration.
    """

    stage = models.ForeignKey(
        ApplicationStage, on_delete=models.CASCADE, related_name="eligible_approvers"
    )
    user = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="stage_eligibility"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["stage", "user"]
        constraints = [
            models.UniqueConstraint(
                fields=["stage", "user"],
                name="stageapprover_stage_user_unique",
            )
        ]
        indexes = [
            models.Index(
                fields=["user"], name="idx_stage_elig_user"
            )
        ]

    def __str__(self) -> str:
        return f"{self.user.get_full_name()} eligible for stage {self.stage_id}"


class ApprovalDecisionLockedError(Exception):
    """Raised on any attempt to update or delete an ``ApprovalDecision``."""


class ApprovalDecisionQuerySet(models.QuerySet):
    """Append-only: queryset-wide update/delete are rejected."""

    def update(self, *args: object, **kwargs: object):
        raise ApprovalDecisionLockedError(
            "Approval decisions are append-only and cannot be updated."
        )

    def delete(self):
        raise ApprovalDecisionLockedError(
            "Approval decisions are append-only and cannot be deleted."
        )


class ApprovalDecisionManager(models.Manager.from_queryset(ApprovalDecisionQuerySet)):
    """Manager enforcing the append-only invariant."""


class ApprovalDecision(models.Model):
    """One recorded worker; append-only by design (spec 6.4).

    A decision belongs to exactly one stage of one application. It is written
    once, atomically with the stage/app transition it causes, and can never be
    updated or deleted — not via the API, the admin, or ORM helpers.
    """

    class Action(models.TextChoices):
        APPROVE = "approve", "Approve"
        REJECT = "reject", "Reject"
        RETURN_FOR_CORRECTION = "return_for_correction", "Return for correction"

    application = models.ForeignKey(
        "leave.LeaveApplication",
        on_delete=models.PROTECT,
        related_name="approval_decisions",
        help_text="The application the decision was made on.",
    )
    stage = models.ForeignKey(
        ApplicationStage,
        on_delete=models.PROTECT,
        related_name="decisions",
        help_text="The stage this decision was recorded against.",
    )
    approver = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="approval_decisions",
        help_text="The user who made the decision.",
    )
    approver_name = models.CharField(
        max_length=150,
        help_text="Snapshot of the approver's full name at decision time.",
    )
    role_label = models.CharField(
        max_length=80,
        help_text="Snapshot of the stage's role label.",
    )
    action = models.CharField(
        max_length=24,
        choices=Action.choices,
    )
    comment = models.TextField(
        blank=True,
        default="",
        help_text="Mandatory for reject and return-for-correction.",
    )
    submission_cycle = models.PositiveIntegerField(
        default=1,
        help_text="The resubmission cycle this decision belongs to.",
    )
    decided_at = models.DateTimeField(
        default=timezone.now,
        help_text="Explicit timestamp recorded by the decision service.",
    )

    objects = ApprovalDecisionManager()

    class Meta:
        ordering = ["-decided_at"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(action__in=("reject", "return_for_correction"))
                | ~models.Q(comment=""),
                name="comment_required_for_reject_or_return",
            )
        ]
        indexes = [
            models.Index(
                fields=["approver", "decided_at"],
                name="idx_decision_approver_time",
            )
        ]

    def __str__(self) -> str:
        return (
            f"{self.get_action_display()} ({self.approver_name})"
            f" on {self.application.reference_number or self.application_id}"
        )

    def delete(self, *args: object, **kwargs: object) -> None:
        raise ApprovalDecisionLockedError(
            "Approval decisions are append-only and cannot be deleted."
        )

    def save(self, *args: object, **kwargs: object) -> None:
        if not self._state.adding:
            raise ApprovalDecisionLockedError(
                "Approval decisions are append-only and cannot be updated."
            )
        super().save(*args, **kwargs)