from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from organisation.models import ApproverRole, Campus
from users.models import User


class Team(models.Model):
    """A group of employees sharing one approval workflow.

    A team routes every application its members submit through exactly one
    :class:`Workflow` — the one :attr:`workflow` points at. A team may *own*
    several workflows (:attr:`Workflow.team`), so HR can build a replacement
    chain alongside the one in force, but only one of them ever routes, and it
    is picked explicitly rather than guessed. At submission time the applicant's
    team is what selects the workflow — there is no category matching — and that
    workflow's :class:`Section` rows are who may act at each step.

    There is no department. A team is identified by its name, its
    :attr:`category`, and — for an academic team — the :class:`Campus` it sits
    at, which is what lets HR ask "who approves at this campus" without a
    free-text field that quietly accumulates typos ("Main campus", "main
    campus", "MAIN").

    The chain exists *because* the team does, and is written in the same request
    as the team. There is deliberately no reusable chain a second team can be
    pointed at: a shared chain makes "edit this team's approval steps" and
    "silently re-route someone else's applications" the same action, which is
    not an edit HR can be asked to perform safely.

    :attr:`workflow` is **nullable**, and null only while the team is being
    configured. HR creates a team's identity first and its approval chain
    second, so a chainless team is a real, inspectable object — and it routes
    nothing purely because there is nothing to route through —
    :func:`workflows.services.validate_team` reports the missing chain rather
    than a team that silently fails at submission.

    The lifecycle is one authoritative field, :attr:`status`, and it is
    deliberately a three-value choice rather than a boolean:

    ``DRAFT``
        A legacy state, retained for teams written before creation put a team
        in force. A draft team is invisible to routing, so a half-finished
        configuration cannot strand an employee's application.
    ``ACTIVE``
        The only status that routes (invariant 12.5). Every team is created here:
        creating a team *is* the decision to put it in force, so there is no
        separate activation step.
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

    class Category(models.TextChoices):
        """Which half of the institution this team belongs to.

        The two values are the same words as :attr:`EmployeeProfile.category`,
        and they decide two things and only two things:

        * an **academic** team sits at a :class:`Campus`, which is what makes
          campus-wide approvers reachable for its stages;
        * an **administration** team is not campus-based, and is the only kind
          of team an institution-wide approver may serve.
        """

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
            "Academic and not allowed when it is Administration. Routing always "
            "follows the team — the campus is what scopes campus-wide "
            "approvers and reporting."
        ),
    )
    workflow = models.OneToOneField(
        "workflows.Workflow",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="routed_by",
        help_text=(
            "The one workflow this team routes applications through. A team may "
            "own several workflows (Workflow.team) — for example a replacement "
            "chain being built alongside the live one — but exactly one of them "
            "is ever in force, it is picked here rather than assumed, and no "
            "second team may point at it: a chain belongs to the team it was "
            "built for, and sharing one would mean editing one team's steps "
            "silently re-routing another. Blank only while the team is still a "
            "draft being configured."
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

    def clean(self) -> None:
        """An academic team sits at a campus; an administration team does not."""
        super().clean()
        errors = {}
        if self.category == self.Category.ACADEMIC and self.campus_id is None:
            errors["campus"] = (
                "An academic team sits at a campus — pick one, or create it "
                "first. The campus is what makes campus-wide approvers "
                "reachable for this team's stages."
            )
        if self.category == self.Category.ADMINISTRATION and self.campus_id is not None:
            errors["campus"] = (
                "An administration team is not campus-based. Clear the campus, "
                "or switch the category to Academic if this team should sit at "
                "one."
            )
        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return f"{self.name} ({self.get_status_display()})"


class TeamRoleAssignment(models.Model):
    """A **team-wide** holding of an :class:`ApproverRole`.

    One holder per role per team: "the Head of Department approves for this
    team" is a fact about the team, not about a workflow, so every workflow the
    team owns resolves the role to the same person without HR re-appointing
    them per chain. This is the *automatic* half of stage staffing — the
    workflow-specific half is a manual :class:`Section` appointment, which always
    wins because it is the explicit one.

    A team-wide holder does not have to be a member of the team. Somebody who
    is, is also covered by a manual appointment; the point of the wide holding
    is the case where the office outlives the person holding it — registrar,
    bursar — and HR changes the assignment in one place rather than in every
    chain that names the role.

    Institution-wide roles are deliberately refused here: they have their own
    holding (:class:`RoleAssignment`) and their own, narrower, use.
    """

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
                {
                    "role": (
                        f'"{self.role.label}" is an institution-wide role. Assign '
                        "its holder under Approvers, not on a team."
                    )
                }
            )
        if not self.role.is_active:
            raise ValidationError(
                {"role": f'"{self.role.label}" is retired and cannot be assigned.'}
            )
