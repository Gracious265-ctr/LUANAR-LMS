"""Workflow and delegation logic shared by the API serializer, actions, and admin."""

from datetime import date
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, F, Q
from django.db.models.deletion import ProtectedError
from django.utils import timezone
from django.utils.text import slugify

from audit.models import AuditEntry
from audit.services import changed_fields, record_audit
from leave.models import LeaveApplication
from leave.services import active_financial_year, date_ranges_overlap
from users.models import EmployeeProfile, User

from approvals.models import (
    ApplicationStage,
    ApplicationStageApprover,
    ApprovalDecision,
)
from organisation.models import ApproverRole, Campus, CampusRoleAssignment, RoleAssignment, Team, TeamRoleAssignment
from organisation.services import (
    RoleActionError,
    WorkflowMemberError,
    _employee_profile_for,
    _lookup_stage_role,
    _member_display_name,
    _resolve_stage_role,
    create_team_role_assignment,
    is_hr_actor,
    is_team_manager,
    wide_approver_ids_for_team,
)
from workflows.models import Section, SectionMember, Workflow
from approvals.models import Delegation

from approvals.models import Reassignment
from .models import WorkflowMember
from .policies import can_manage_team, is_self_application
from .providers import WorkflowConfigError, resolve_section_approvers


class WorkflowAssignmentError(Exception):
    """The application could not be assigned a workflow; carries messages."""

    def __init__(self, messages: list[str]):
        self.messages = messages
        super().__init__("; ".join(messages))


class StageSequenceError(ValueError):
    """Raised when a submitted workflow stage list is invalid.

    ``field`` is the API field the error belongs to; ``index`` is the 0-based
    stage position when the error is specific to one stage.
    """

    def __init__(self, field: str, message: str, index: int | None = None):
        super().__init__(message)
        self.field = field
        self.message = message
        self.index = index


def _require_can_manage_team(actor, team, error_cls: type[Exception]) -> None:
    """Refuse ``actor`` unless they are HR or ``team``'s designated manager.

    The service-layer half of the team-management delegation: the API scopes
    querysets so a manager cannot *reach* another team, and this makes the write
    itself refuse when it does — a direct service call, an internal helper, or a
    future endpoint that skipped the scoping. ``error_cls`` lets each family of
    operations raise the error its caller already translates.
    """
    if can_manage_team(actor, team):
        return
    raise error_cls(
        "detail", "You do not have permission to manage this team."
    )


def _require_hr_actor(actor, error_cls: type[Exception]) -> None:
    """Refuse ``actor`` unless they are HR: the identity/lifecycle guard."""
    if is_hr_actor(actor):
        return
    raise error_cls("detail", "Only HR may perform this action.")


def _require_team_manager(actor, team, error_cls: type[Exception]) -> None:
    """Refuse ``actor`` unless they are the designated manager of ``team``.

    The handover half of the team-management split: HR creates the team and
    designates the manager, so the operations that follow — building the team's
    chain, staffing its steps, holding its members — belong to the manager, not
    to HR. The service layer refuses rather than the API only scoping, so an
    internal caller cannot widen the delegation by hand.
    """
    if is_team_manager(actor, team) or getattr(actor, "is_superuser", False):
        return
    raise error_cls("detail", "Only the team manager may manage this team.")


def normalize_section_sequence(sections: list[dict]) -> list[dict]:
    """Validate and renumber a workflow's section list in approval order.

    A section names its approver role by ``code`` (``"hod"``) — that is the wire
    contract — or by primary key for convenience. Either way the value is
    resolved against :class:`~workflows.models.ApproverRole`, and the normalized
    payload carries the role's *code* so the sequence round-trips through the API
    without leaking database ids into saved forms.

    A role may **not** repeat across sections of one workflow (Unit 30). It
    could once, on the reasoning that one person can sit at several points in a
    chain — but a role appearing twice means the same capacity signing off twice
    at two different points, and ``section_workflow_role_unique`` now says so at
    the database too. Repeating the role across *different* workflows is still
    fine; the rule is per workflow, not global.

    Returns a list of ``{"name", "approver_role", "order"}``. Raises
    :class:`StageSequenceError` for an empty list, an unknown or inactive
    approver role, a role already used by another section in the same payload, a
    missing/blank name, or a missing/non-positive/duplicate order.
    """
    items = list(sections)
    if not items:
        raise StageSequenceError(
            "sections", "At least one approval section is required."
        )

    seen_orders: set[int] = set()
    seen_roles: dict[int, int] = {}
    normalized: list[dict] = []

    for index, item in enumerate(items):
        role = _section_role(item)
        if role is None:
            raise StageSequenceError(
                "approver_role", "Select a valid approver role.", index
            )
        role_row = role if isinstance(role, ApproverRole) else _resolve_stage_role(role)
        if role_row is None:
            raise StageSequenceError(
                "approver_role",
                "That approver role is missing or deactivated. Pick an active "
                "role, or reactivate the role in Roles.",
                index,
            )
        role = role_row

        name = item.get("name") if isinstance(item, dict) else getattr(item, "name", None)
        name = (name or "").strip() if isinstance(name, str) else ""
        if not name:
            # Fall back to the role's own label so a saved workflow is never
            # nameless; HR still gets to say what the step is for.
            name = role.label

        order = item.get("order")
        if not isinstance(order, int) or isinstance(order, bool) or order < 1:
            raise StageSequenceError(
                "order", "Section order must be a positive whole number.", index
            )
        if order in seen_orders:
            raise StageSequenceError(
                "order", "Section order numbers must be unique within a workflow.", index
            )
        seen_orders.add(order)

        # The role check runs after the order check so the error a caller sees
        # for a payload that is wrong in both ways names the ordering problem
        # first, which is the one they have to fix to make progress.
        first_use = seen_roles.get(role.pk)
        if first_use is not None:
            raise StageSequenceError(
                "approver_role",
                f"The {role.label} role is already assigned to another stage in "
                "this workflow. A role can only be assigned to one stage per "
                "workflow — give this stage a different role, or remove the "
                f"other one (step {first_use + 1}).",
                index,
            )
        seen_roles[role.pk] = index

        normalized.append(
            {"name": name, "approver_role": role.code, "order": index + 1}
        )

    return normalized


@dataclass(frozen=True)
class ActivationIssue:
    """One reason an activation/scheduling submission was rejected.

    ``field`` is the API field the issue belongs to (``"effective_from"`` for a
    scope conflict, ``None`` for a missing approver role). ``message`` is the
    human-readable explanation.
    """

    field: str | None
    message: str


def _section_role(section) -> int | str | ApproverRole | None:
    """The approver role a section payload names, whether dict or model.

    Returns an :class:`ApproverRole`, its primary key, or its code, as named.
    ``None`` means the payload named nothing usable. The ambiguity is harmless
    because :func:`normalize_section_sequence` only ever needs to resolve the
    value against a role, and the choice of code-vs-pk is an input detail.
    """
    if isinstance(section, dict):
        value = section.get("approver_role")
    elif isinstance(getattr(section, "approver_role", None), ApproverRole):
        return section.approver_role
    else:
        value = getattr(section, "approver_role_id", None)
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, ApproverRole)):
        return value
    if isinstance(value, str):
        return value.strip()
    return None






def missing_approver_roles(sections) -> list[str]:
    """Labels of section roles that cannot currently be used, in section order.

    Activation is a configuration check, so the only thing it can know about
    member availability without an applicant is whether the *role itself* is
    usable. A role that has been deactivated is reported; whether a given
    section actually has somebody who can act is resolved per applicant at
    submission time (invariant 12.7 still blocks that submission).
    """
    missing: list[str] = []
    seen: set[int] = set()
    for section in sections:
        role = _section_role(section)
        if role is None:
            continue
        if not isinstance(role, ApproverRole):
            role = _lookup_stage_role(role)
        if role is None:
            continue
        if role.pk in seen:
            continue
        seen.add(role.pk)
        if not role.is_active:
            missing.append(role.label)
    return missing


def replace_workflow_sections(workflow: Workflow, sections) -> list[Section]:
    """Rewrite a workflow's section sequence, preserving membership.

    A section is identified across writes by its ``(role, name)`` pair. A
    section whose pair still appears in the payload keeps its row, and so keeps
    its appointed approver: re-ordering the chain must not silently unstaff the
    people who can act for it.

    A section whose role **or** name changed is a different step and is
    rebuilt empty. Deliberately not carried over: a step that moved to a
    different approver role has a different authority, and quietly handing
    the old appointment to the new role would grant it without HR asking. The
    step shows up with nobody appointed, which is visible and fixable, and
    submission is refused until it is staffed.

    ``(workflow, order)`` is unique, so the write is sequenced to avoid
    colliding with itself: stale sections go first, survivors are parked
    beyond any real order, and only then is the final order applied.

    Lives here rather than on the workflow serializer so a team created with
    its chain inline goes through the *same* rules as a standalone workflow
    edit — one implementation, so the two paths cannot drift apart. Returns
    the resulting sections in approval order.
    """
    existing = list(
        workflow.sections.select_related("approver_role").prefetch_related("members")
    )
    by_identity = {(s.approver_role_id, s.name): s for s in existing}

    resolved: list[tuple[dict, ApproverRole]] = []
    for payload in normalize_section_sequence(sections):
        role = _resolve_stage_role(payload["approver_role"])
        if role is None:
            raise StageSequenceError(
                "approver_role",
                f"Approver role '{payload['approver_role']}' is missing or "
                "deactivated.",
            )
        resolved.append((payload, role))

    # ``(payload, role, survivor_pk)``. A non-``None`` survivor keeps its row
    # and its members; ``None`` means build the step fresh.
    plan: list[tuple[dict, ApproverRole, int | None]] = []
    claimed: set[int] = set()
    for payload, role in resolved:
        survivor = by_identity.get((role.pk, payload["name"]))
        if survivor is not None and survivor.pk not in claimed:
            claimed.add(survivor.pk)
            plan.append((payload, role, survivor.pk))
        else:
            # Either a genuinely new step, or the same role+name a second
            # time in one payload. Role uniqueness (Unit 30) means the second
            # cannot be the same *role*, so reaching here twice with one role
            # means the role changed between the two entries — the second needs
            # its own row rather than reusing the first.
            plan.append((payload, role, None))

    # 1. Drop the steps that are no longer in the payload. Their members
    #    cascade. Doing this first means their orders are free for reuse.
    #    A step an application is still sitting on cannot go: the application's
    #    stage points at it, so deleting it would strand that application with
    #    no approver and no way to say who used to hold the step. Reported as a
    #    validation error naming the step, not as a database integrity error.
    try:
        workflow.sections.exclude(pk__in=claimed).delete()
    except ProtectedError as exc:
        blocked_ids: set[int] = set()
        for protected in exc.protected_objects:
            # Django hands back the referencing rows, not the rows being
            # deleted, so the blocked steps are read back off the referrers.
            for field in ("section_ref", "section"):
                value = getattr(protected, f"{field}_id", None)
                if value is not None:
                    blocked_ids.add(value)
        blocked = Section.objects.filter(pk__in=blocked_ids)
        names = ", ".join(f'"{section.name}"' for section in blocked) or "a step"
        raise StageSequenceError(
            "sections",
            f"Cannot remove {names}: an application is still waiting on that "
            "step. Decide or withdraw those applications first, then change the "
            "steps.",
        ) from exc

    # 2. Park the survivors, so writing the new order cannot collide with a
    #    surviving section that is currently sitting on the target order.
    for _, _, survivor_pk in plan:
        if survivor_pk is not None:
            Section.objects.filter(pk=survivor_pk).update(order=F("order") + 1_000_000)

    # 3. Apply the final order, building the steps that have no row yet.
    for payload, role, survivor_pk in plan:
        if survivor_pk is not None:
            Section.objects.filter(pk=survivor_pk).update(order=payload["order"])
            continue
        Section.objects.create(
            workflow=workflow,
            name=payload["name"],
            approver_role=role,
            order=payload["order"],
        )

    return list(workflow.sections.select_related("approver_role").order_by("order"))








def _active_delegation_for_id(approver_id: int) -> Delegation | None:
    """The delegation currently covering an approver, keyed by user id."""
    today = timezone.localdate()
    return (
        Delegation.objects.filter(
            approver_id=approver_id,
            status=Delegation.Status.APPROVED,
            starts_on__lte=today,
        )
        .filter(Q(ends_on__isnull=True) | Q(ends_on__gte=today))
        .order_by("-starts_on")
        .first()
    )


def eligible_approver_ids(application, stage=None) -> list[int]:
    """Every person entitled to act on the application's pending stage, right now.

    The authorisation half of the spine. A section is resolved by whoever acts
    first, so the authoritative answer is a *set* read from the stage's
    eligibility snapshot — never from ``current_approver``, which only records
    that somebody has already acted. The applicant was removed from the snapshot
    when the chain was materialised, so self-approval cannot appear here.

    ``stage`` is an optional already-loaded :class:`ApplicationStage`, so a
    caller that fetched the chain with ``prefetch_related("eligible_approvers")``
    does not re-read the snapshot row by row.
    """
    stage = stage if stage is not None else _current_stage(application)
    if stage is None:
        return []
    return stage.eligible_approver_ids()


def _current_stage(application):
    if application.current_stage_id is None:
        return None
    return ApplicationStage.objects.filter(pk=application.current_stage_id).first()


def acting_approver_ids(application, eligible: list[int] | None = None) -> list[int]:
    """The eligible people after delegation is applied.

    Anyone who can act, plus the delegate of any eligible person who has
    delegated while a delegation covers them. Single-level only: a delegate's own
    active delegation is never cascaded.

    ``eligible`` lets a caller that has already read the snapshot pass it in
    rather than have it read again.
    """
    if eligible is None:
        eligible = eligible_approver_ids(application)
    if not eligible:
        return []
    result: list[int] = []
    for approver_id in eligible:
        delegation = _active_delegation_for_id(approver_id)
        if delegation is not None and delegation.delegate_id is not None:
            result.append(delegation.delegate_id)
        else:
            result.append(approver_id)
    return result


def user_may_act(user, application) -> bool:
    """Whether ``user`` is entitled to decide the application's pending stage.

    The single authoritative authority check for an open section stage, and the
    only one the decision path should consult. A person's authority comes from
    being in the stage's eligibility snapshot (or being an eligible approver's
    active delegate) — never from ``User.role``, and never from holding the same
    role in some other team's configuration.
    """
    user_id = user.id if hasattr(user, "id") else user
    if user_id is None:
        return False
    return user_id in acting_approver_ids(application)


# ---------------------------------------------------------------------------
# Approver roles, role assignments, and teams (HR-managed configuration).
#
# Every write here is a configuration change: it runs inside a transaction,
# records one audit entry, and refuses any state that would leave a workflow
# stage or a routing decision unresolvable.
# ---------------------------------------------------------------------------














































@dataclass(frozen=True)
class TeamIssue:
    """One reason a team is not ready to route applications.

    ``code`` is stable and machine-readable so a client can react to a specific
    problem rather than parsing the sentence; ``field`` is the API field the
    issue belongs to, so a form can put it next to the input that caused it.
    ``section`` is the 1-based approval order when the issue is about one step.
    """

    code: str
    field: str
    message: str
    section: int | None = None
    approver_role: str = ""


@dataclass(frozen=True)
class TeamReadiness:
    """The outcome of checking a team, and whether it may be activated.

    ``ready`` is False when *any* issue was found: a team is only ever
    all-or-nothing, because a chain with one unstaffed step strands every
    application that reaches it and the employee finds out at the worst
    possible moment. The issues are returned whole rather than the first
    failure so HR can fix the configuration in one pass.
    """

    team: Team
    issues: tuple[TeamIssue, ...] = ()

    @property
    def ready(self) -> bool:
        return not self.issues

    def as_dict(self) -> dict:
        return {
            "ready": self.ready,
            "issues": [
                {
                    "code": issue.code,
                    "field": issue.field,
                    "message": issue.message,
                    "section": issue.section,
                    "approver_role": issue.approver_role,
                }
                for issue in self.issues
            ],
        }


class TeamActionError(ValueError):
    """Raised when a team or team-member write cannot be applied.

    ``field`` is the API field the error belongs to. ``issues`` carries the
    structured :class:`TeamIssue` list when the refusal came from validating a
    whole configuration (activation), so a client can render each problem
    against the step that caused it instead of parsing one long sentence.
    """

    def __init__(
        self,
        field: str,
        message: str,
        issues: tuple[TeamIssue, ...] | list[TeamIssue] | None = None,
    ):
        super().__init__(message)
        self.field = field
        self.message = message
        self.issues = tuple(issues or ())


def _unique_team_code(name: str) -> str:
    """Derive a unique slug code from a team name.

    HR names a team; the code is machine-facing (it is what other systems and
    reports key off), so it is derived rather than typed. Two different names
    can slug to the same thing — "R & D" and "R&D" both give "r-d" — so the
    suffix loop keeps creation from failing on the unique index.
    """
    base = slugify(name)[:40] or "team"
    candidate = base
    suffix = 2
    while Team.objects.filter(code=candidate).exists():
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def wide_holder_ids(team: Team, role: ApproverRole) -> set[int]:
    """Everyone who can staff ``role`` for ``team`` without an appointment.

    The set :func:`validate_team` needs to tell "this approver is outside the
    team, which is a problem" from "this approver is outside the team, which is
    the point of a wide holding". Scoped exactly as resolution is: the team's own
    holder, the holder at the team's campus, and — for an administration team —
    the institution-wide holder.
    """
    ids = set(
        TeamRoleAssignment.objects.filter(
            team=team, role=role, user__is_active=True
        ).values_list("user_id", flat=True)
    )
    if team.campus_id is not None:
        ids |= set(
            CampusRoleAssignment.objects.filter(
                campus_id=team.campus_id, role=role, user__is_active=True
            ).values_list("user_id", flat=True)
        )
    if role.is_institution_wide and team.category == Team.Category.ADMINISTRATION:
        ids |= set(
            RoleAssignment.objects.filter(
                role=role, user__is_active=True
            ).values_list("user_id", flat=True)
        )
    return ids


def validate_team(team: Team) -> TeamReadiness:
    """Check whether a team can route an application's approvals.

    Side-effect free and safe to call at any time: the validation endpoint and
    the activation action run the same function, so HR sees exactly the
    problems that will block activation, no more and no fewer.

    The checks are deliberately about the team's *own* configuration — the
    workflow, its sections, their roles, and whether somebody can act at each
    step today. Per-applicant resolution (an applicant who is themselves the
    only approver of a step, say) cannot be known without an application and is
    still refused at submission by invariant 12.7.
    """
    issues: list[TeamIssue] = []
    workflow = team.workflow

    if workflow is None:
        issues.append(
            TeamIssue(
                "workflow_missing",
                "workflow",
                f"The {team.name} team has no approval workflow. Describe the "
                "approval steps this team routes through.",
            )
        )
        return TeamReadiness(team=team, issues=tuple(issues))

    if not workflow.is_active:
        issues.append(
            TeamIssue(
                "workflow_inactive",
                "workflow",
                f"Workflow '{workflow.name}' is inactive. Reactivate it, or point "
                f"the {team.name} team at an active workflow.",
            )
        )

    if (
        workflow.effective_from is not None
        and workflow.effective_from > timezone.localdate()
    ):
        issues.append(
            TeamIssue(
                "workflow_scheduled",
                "workflow",
                f"Workflow '{workflow.name}' does not start until "
                f"{workflow.effective_from.isoformat()}. Move its start date "
                f"earlier, or wait until then to activate the {team.name} team.",
            )
        )

    sections = list(
        workflow.sections.filter(is_active=True)
        .order_by("order")
        .select_related("approver_role")
    )
    if not sections:
        issues.append(
            TeamIssue(
                "no_sections",
                "sections",
                f"Workflow '{workflow.name}' has no active approval sections. Add "
                "at least one step before activating the team.",
            )
        )

    for section in sections:
        role = section.approver_role
        if not role.is_active:
            issues.append(
                TeamIssue(
                    "inactive_role",
                    "sections",
                    f'The "{section.name}" step needs the "{role.label}" role, which '
                    "is deactivated. Reactivate it in Roles, or replace the step.",
                    section=section.order,
                    approver_role=role.code,
                )
            )
            continue
        # A step whose approver has since been deactivated resolves to nobody,
        # which is the same failure as no approver at all: a step HR believes is
        # staffed with somebody who cannot log in. The resolver *raises* for an
        # unstaffable step rather than returning an empty set, so the reason is
        # captured and the whole configuration is still reported.
        try:
            approvers = resolve_section_approvers(section)
        except WorkflowConfigError:
            approvers = ()
        if not approvers:
            if role.is_institution_wide and team.category != Team.Category.ADMINISTRATION:
                hint = (
                    "An institution-wide role may only serve an administration "
                    "team — appoint one of this team's members, or give the role "
                    "a team-wide or campus-wide holder."
                )
            elif team.campus_id is not None:
                hint = (
                    "Appoint somebody from the team, or give the role a "
                    "team-wide or campus-wide holder."
                )
            else:
                hint = (
                    "Appoint somebody from the team, or give the role a "
                    "team-wide holder."
                )
            issues.append(
                TeamIssue(
                    "no_approver",
                    "sections",
                    f'Nobody can act on the "{section.name}" step '
                    f"({role.label}). {hint}",
                    section=section.order,
                    approver_role=role.code,
                )
            )
        else:
            # An approver appointed before they joined the team, or whose own
            # employee record moved since, still routes — the write-time check only
            # ran when the appointment was made. Report it rather than let a team be
            # activated whose approver is outside it. A wide holding is the
            # deliberate exception: not being on the team is the whole point of
            # one.
            wide_ids = wide_holder_ids(team, role)
            for approver_id in approvers:
                if approver_id in wide_ids:
                    continue
                profile = getattr(
                    User.objects.filter(pk=approver_id).first(), "employee_profile", None
                )
                if profile is not None and profile.team_id != team.pk:
                    issues.append(
                        TeamIssue(
                            "approver_outside_team",
                            "sections",
                            f'The approver of the "{section.name}" step is no longer '
                            "a member of this team. Appoint one of the team's "
                            "members, or move the approver's employee record.",
                            section=section.order,
                            approver_role=role.code,
                        )
                    )
                    break

    if (
        team.effective_from is not None
        and team.effective_to is not None
        and team.effective_to < team.effective_from
    ):
        issues.append(
            TeamIssue(
                "window_ordered",
                "effective_to",
                f"The end date ({team.effective_to.isoformat()}) is before the "
                f"start date ({team.effective_from.isoformat()}).",
            )
        )

    if team.effective_to is not None and team.effective_to < timezone.localdate():
        issues.append(
            TeamIssue(
                "window_ended",
                "effective_to",
                f"This team's last routing date was "
                f"{team.effective_to.isoformat()}, which has passed. Move the end "
                "date into the future, or leave it blank, to activate the team.",
            )
        )

    return TeamReadiness(team=team, issues=tuple(issues))


def _unique_workflow_name(base: str, exclude_pk: int | None = None) -> str:
    """A unique workflow name derived from the team being created or edited.

    ``exclude_pk`` is the workflow being renamed, which does not count as a
    clash with itself — otherwise saving a team without touching the chain name
    would rename it to "… (2)" every time.
    """
    base = (base or "").strip() or "Team workflow"
    candidate = base
    suffix = 2
    while (
        Workflow.objects.filter(name=candidate)
        .exclude(pk=exclude_pk)
        .exists()
    ):
        candidate = f"{base} ({suffix})"
        suffix += 1
    return candidate


def _ensure_team_category(team: Team) -> None:
    """Refuse a category/campus pair that cannot mean anything.

    An academic team sits at a campus — that is what makes campus-wide
    approvers reachable for its stages — and an administration team does not,
    because it is the institution that serves it. Checked on every write rather
    than left to a database constraint, because the sentence HR reads has to
    name the fix: create or pick a campus, or switch the category.

    The model's ``clean`` says the same thing; this is the API's copy of it so
    the refusal arrives as a field error instead of a 500.
    """
    try:
        team.full_clean(exclude=["name", "code", "status", "workflow"])
    except ValidationError as exc:
        message_dict = getattr(exc, "message_dict", None)
        if message_dict:
            field, messages = next(iter(message_dict.items()))
            message = messages[0]
        else:
            field, message = "campus", "; ".join(
                str(item) for item in exc.messages
            )
        if field == "__all__":
            # A model-level constraint (the effective-date window) is about the
            # team as a whole, and no form field owns it.
            field = "detail"
        raise TeamActionError(field, message)


def create_team(*, actor, data: dict, manager: dict | None = None) -> Team:
    """Create a team and, optionally, designate its manager in the same pass.

    ``data`` holds the team's own editable fields. The team's approval chain is
    deliberately *not* written here: HR creates the team and hands it to a
    manager, and the manager configures the chain from their own portal. The
    team is **in force the moment HR creates it** — there is no separate "put
    into force" step — so it routes as soon as it owns a chain, and sits inert
    until then purely because there is nothing yet to route through.

    ``manager`` is ``{"role": <ApproverRole>, "user": <User>}``, the second page
    of HR's create flow. When given, that team-scoped role is appointed to the
    person as a team-wide holding and flagged the team's manager, in the same
    transaction as the team, through
    :func:`organisation.services.create_team_role_assignment`. Naming the role
    *and* the person is the whole instruction: the holding is what lets the
    manager act, so "assign the manager" is not a separate object to keep in
    step.

    A team starts **active** whatever else is true of it, and does not route
    until it owns a chain. Creating it is the act of putting it in force: HR
    does not confirm that afterwards, and :func:`create_team` never lands a
    draft.
    """
    _require_hr_actor(actor, TeamActionError)
    with transaction.atomic():
        data = dict(data)
        data.setdefault("code", _unique_team_code(data.get("name", "")))
        # Creating a team *is* putting it in force. HR does not confirm this on
        # a second screen, and a team left sitting as a draft would be a team
        # nobody could reach the configuration of, so the draft state has no
        # work left to do.
        data["status"] = Team.Status.ACTIVE

        team = Team(**data)
        _ensure_team_category(team)
        team.save()

        record_audit(
            actor=actor,
            action=AuditEntry.Action.CREATED,
            target_type=AuditEntry.TargetType.TEAM,
            target_id=team.pk,
            target_summary=team.name,
            detail={"before": None, "after": _team_snapshot(team)},
        )
        if manager is not None:
            create_team_role_assignment(
                team=team,
                role=manager["role"],
                user=manager["user"],
                actor=actor,
                is_team_manager=True,
            )
    return team


def _workflow_snapshot(workflow: Workflow) -> dict:
    """A workflow's chain, in role *codes* with its current open members.

    Codes rather than ids so the entry stays readable years after the role is
    renamed; the member list is the open memberships only, which is the roster
    the chain actually routes with.
    """
    return {
        "name": workflow.name,
        "effective_from": workflow.effective_from,
        "effective_to": workflow.effective_to,
        "is_active": workflow.is_active,
        "sections": [
            {
                "name": section.name,
                "order": section.order,
                "approver_role": section.approver_role.code,
                "approver": (
                    {
                        "user_id": section.approver_id,
                        "name": section.approver.get_full_name()
                        or section.approver.username,
                    }
                    if section.approver_id
                    else None
                ),
            }
            for section in workflow.sections.order_by("order").select_related(
                "approver_role"
            )
        ],
    }


def _appoint_institution_wide_holder(*, section: Section, actor=None) -> None:
    """Appoint the role's holder when a stage selects an institution-wide role.

    A step whose role is institution-wide is not a team's to staff, so the
    team-scoped picker cannot offer the holder and HR would otherwise have to
    leave the step empty. Selecting the role *is* the appointment, so the role's
    active holder is written to the step here.

    Only an unambiguous holding is applied: exactly one active holder. A role
    with none, or with several, is left unstaffed because picking one of many
    would silently decide an ambiguity only HR can resolve — the same rule
    :func:`~workflows.providers.resolve_section_approvers` applies at submission.
    Inspection and validation therefore keep reporting the real problem instead
    of the auto-appointment hiding it.

    An academic team is left unstaffed too, and for a different reason: an
    institution-wide approver may not serve it at all, so appointing one would
    write a configuration the requirement forbids. :func:`validate_team` then
    reports the step with a message that says which way to go.
    """
    role = section.approver_role
    if not role.is_institution_wide:
        return
    team = section.workflow.team if section.workflow_id else None
    if team is not None and team.category != Team.Category.ADMINISTRATION:
        return
    holders = list(
        RoleAssignment.objects.filter(role=role, user__is_active=True)
        .order_by("user_id")
        .select_related("user")
    )
    if len(holders) != 1:
        return
    holder = holders[0].user
    if (
        section.approver_id == holder.pk
        and SectionMember.objects.filter(section=section, user=holder).exists()
    ):
        # Already the configured approver; re-sending the same chain is not a new
        # appointment and must not open a second period for the same person.
        return
    add_section_member(section=section, user=holder, actor=actor)


def _attach_section_approvers(
    *,
    team: Team,
    workflow: Workflow,
    sections: list[Section],
    config: list[dict],
    actor=None,
) -> None:
    """Appoint the requested approver on each newly written section.

    Appointment goes through the same guards as the standalone action
    (:func:`ensure_membership_allowed`) so a chain cannot be created with a
    deactivated account, an approver from outside the team, or a second role for
    somebody who already holds one on it — the rules live in one place, and this
    path cannot grant something the other path would refuse.

    The team is passed in rather than looked up because a chain may be written
    alongside a team being created; the team the approver is checked against is
    the one the chain belongs to.
    """
    # Paired by position, not by name: two steps may legitimately share a label
    # (same role, same "Approval" text twice in a row), and matching on the
    # name alone would hand the second step's approver to the first one.
    by_order = {section.order: section for section in sections}
    for position, payload in enumerate(config):
        section = by_order.get(position + 1)
        if section is None:
            continue

        user_pk = payload.get("approver")
        if user_pk in (None, ""):
            # An unstaffed step is allowed at draft time on purpose: HR builds the
            # chain and names the people afterwards, and activation is the gate
            # that refuses a team which is not fully staffed. Refusing it here
            # would force every step to be staffed before the team could even be
            # saved, which is the opposite of what a two-page configuration needs.
            #
            # An institution-wide role is the exception. Its holders approve from
            # outside any one team, so the team-scoped picker cannot offer them
            # and HR has no way to staff the step by hand. Selecting the role
            # is the whole instruction, so the role's single active holder is
            # appointed here. Ambiguity (no holder, or several) is left unstaffed
            # and reported by :func:`validate_team` and submission, exactly as an
            # unstaffed step has always been.
            _appoint_institution_wide_holder(section=section, actor=actor)
            continue
        if isinstance(user_pk, (list, tuple)):
            raise TeamActionError(
                "approver",
                'The "approver" step field takes one person. A step has exactly '
                "one approver — pick the single employee responsible for it.",
            )
        user = User.objects.filter(pk=user_pk, is_active=True).first()
        if user is None:
            raise TeamActionError(
                "approver",
                f"Approver {user_pk} is missing or is not an active user. Pick "
                "an active employee, or activate their account first.",
            )
        ensure_membership_allowed(section, user)
        if (
            section.approver_id == user.pk
            and SectionMember.objects.filter(section=section, user=user).exists()
        ):
            # Saving a chain that did not change is not an appointment. Without
            # this, a reorder or a chain rename would close the existing period
            # and open a new one for the same person — history full of handovers
            # nobody made.
            continue
        add_section_member(section=section, user=user, actor=actor)


def update_team(
    *, team: Team, actor, data: dict, manager: dict | None = None
) -> Team:
    """Update a team's editable fields and, optionally, its designated manager.

    ``status`` is not editable here. Teams start in force when HR creates them,
    and the one move left — retirement — goes through :func:`deactivate_team`,
    so it is audited as the distinct event it is rather than being a PATCH that
    quietly takes a team out of service.

    ``workflow`` is not editable here either. Routing a team through one of its
    chains is the manager's decision and goes through :func:`route_team`; the
    chain's steps are configured by the manager through the workflow endpoints.
    Keeping both out of a generic PATCH means editing a team's name can never
    quietly re-route it.

    ``manager`` is the same ``{"role", "user"}`` instruction as on
    :func:`create_team`: the role is appointed to the person as a team-wide
    holding and designated the team's manager. Passing it re-designates the
    manager without touching anything else.
    """
    _require_hr_actor(actor, TeamActionError)
    with transaction.atomic():
        team = Team.objects.select_for_update().get(pk=team.pk)
        before = _team_snapshot(team)
        for field, value in data.items():
            if field in ("status", "workflow"):
                continue
            setattr(team, field, value)
        _ensure_team_category(team)
        team.save()
        record_audit(
            actor=actor,
            action=AuditEntry.Action.UPDATED,
            target_type=AuditEntry.TargetType.TEAM,
            target_id=team.pk,
            target_summary=team.name,
            detail=changed_fields(before, _team_snapshot(team)),
        )

        if manager is not None:
            create_team_role_assignment(
                team=team,
                role=manager["role"],
                user=manager["user"],
                actor=actor,
                is_team_manager=True,
            )
    return team


def route_team(*, team: Team, actor, workflow: Workflow) -> Team:
    """Point a team at one of the chains it owns, as the team's manager.

    Routing is the manager's call: they build the team's chains and decide which
    one is in force. The workflow named must be one the team already owns
    (:attr:`Workflow.team`), so "route through this chain instead" can never
    become "adopt somebody else's chain" — which would strand every application
    inside the old one at a step nobody staffs.

    HR stays out of this deliberately: HR creates the team and assigns its
    manager, and the manager owns the routing decision from then on.
    """
    _require_team_manager(actor, team, TeamActionError)
    with transaction.atomic():
        team = Team.objects.select_for_update().get(pk=team.pk)
        if workflow is None or workflow.team_id != team.pk:
            raise TeamActionError(
                "workflow",
                "A team can only route through a workflow it owns. Create the "
                "workflow under this team first, then point the team at it.",
            )
        if team.workflow_id == workflow.pk:
            return team
        before = _team_snapshot(team)
        team.workflow = workflow
        team.save(update_fields=["workflow", "updated_at"])
        record_audit(
            actor=actor,
            action=AuditEntry.Action.UPDATED,
            target_type=AuditEntry.TargetType.TEAM,
            target_id=team.pk,
            target_summary=team.name,
            detail=changed_fields(before, _team_snapshot(team)),
            reason=f'Routed through "{workflow.name}".',
        )
    return team


def academic_calendar_end() -> date | None:
    """The last day of the academic calendar a chain is written against.

    The configured academic year — the active
    :class:`leave.models.FinancialYear` — is what "the end of the academic
    calendar" means here: a chain is a statement about a term, so a new one
    runs to the end of the current year rather than open-ended. Nothing
    configured means no boundary at all (``None``), which is what an
    installation that has not set up its year should get rather than a crash
    in a create.
    """
    year = active_financial_year()
    return year.end_date if year is not None else None


def create_workflow(*, team: Team, actor, data: dict) -> Workflow:
    """Build a workflow the team owns, with its stages, in one transaction.

    A team may own several workflows — the one it routes through, and a
    replacement HR is building alongside it — so a workflow is created *for* a
    team and ownership is written at creation. Ownership is not routing:
    :attr:`Team.workflow` still decides which chain an application follows, and
    it is only moved here when the team has no chain at all, because silently
    re-routing a team that already routes is the one change this must never
    make.

    ``sections`` is the same stage list the team form sends, so stage
    configuration is one implementation whether HR is editing the chain they
    just created or the one a team has used for a year.
    """
    _require_team_manager(actor, team, WorkflowActionError)
    with transaction.atomic():
        payload = dict(data)
        sections_payload = payload.pop("sections", None)
        members_payload = payload.pop("members", None)
        # A chain is named for what it approves, not for the team it hangs off:
        # a team has several chains over a year, and "<team name> workflow"
        # cannot be told apart from the team itself or from the replacement
        # beside it. The name is the caller's to give.
        raw_name = str(payload.get("name") or "").strip()
        if not raw_name:
            raise WorkflowActionError(
                "name",
                "Every workflow needs a name of its own. Name it for what it "
                "approves — a chain named after its team cannot be told apart "
                "from the team, or from the replacement chain beside it.",
            )
        workflow = Workflow(
            name=_unique_workflow_name(raw_name),
            team=team,
            # In force from today unless the caller says otherwise, and running
            # to the end of the academic calendar: a chain is written against
            # a term, so it does not outlive one by default.
            effective_from=payload.get("effective_from") or timezone.localdate(),
            effective_to=(
                payload.get("effective_to")
                if payload.get("effective_to") is not None
                else academic_calendar_end()
            ),
            is_active=payload.get("is_active", True),
        )
        workflow.save()

        if sections_payload:
            sections = replace_workflow_sections(
                workflow, [dict(section) for section in sections_payload]
            )
            _attach_section_approvers(
                team=team,
                workflow=workflow,
                sections=sections,
                config=[dict(section) for section in sections_payload],
                actor=actor,
            )

        if team.workflow_id is None:
            team.workflow = workflow
            team.save(update_fields=["workflow", "updated_at"])

        if members_payload is not None:
            sync_workflow_members(
                workflow=workflow, user_ids=members_payload, actor=actor
            )

        record_audit(
            actor=actor,
            action=AuditEntry.Action.CREATED,
            target_type=AuditEntry.TargetType.WORKFLOW,
            target_id=workflow.pk,
            target_summary=workflow.name,
            detail={"before": None, "after": _workflow_snapshot(workflow)},
            reason=f"Created for the {team.name} team.",
        )
    return workflow


def update_workflow(*, workflow: Workflow, actor, data: dict) -> Workflow:
    """Edit a workflow's own fields and, optionally, replace its stages.

    Editing stages goes through :func:`replace_workflow_sections`, the same
    function the team form uses, so section identity, ordering, and the
    ``PROTECT`` guard on a step a live application points at are one
    implementation rather than two that can drift.

    A workflow that owns no team cannot be edited here: stage rules are scoped
    to a team (an approver must be a member of it), so there is nothing to check
    an edit against.
    """
    _require_can_manage_team(actor, workflow.team, WorkflowActionError)
    with transaction.atomic():
        locked = Workflow.objects.select_for_update().get(pk=workflow.pk)
        team = locked.team
        if team is None:
            raise WorkflowActionError(
                "team",
                f'"{locked.name}" is not attached to a team, so its stages '
                "cannot be checked against one. Attach it to a team first.",
            )
        before = _workflow_snapshot(locked)

        for field, value in data.items():
            if field in ("sections", "name", "team", "members"):
                continue
            setattr(locked, field, value)
        if data.get("name") and str(data["name"]).strip() != locked.name:
            locked.name = _unique_workflow_name(
                str(data["name"]).strip(), exclude_pk=locked.pk
            )
        locked.save()

        if "members" in data:
            sync_workflow_members(
                workflow=locked, user_ids=data.get("members"), actor=actor
            )

        if data.get("sections") is not None:
            sections_payload = [dict(section) for section in data["sections"]]
            try:
                sections = replace_workflow_sections(locked, sections_payload)
            except StageSequenceError as exc:
                raise WorkflowActionError(exc.field, exc.message)
            _attach_section_approvers(
                team=team,
                workflow=locked,
                sections=sections,
                config=sections_payload,
                actor=actor,
            )

        record_audit(
            actor=actor,
            action=AuditEntry.Action.UPDATED,
            target_type=AuditEntry.TargetType.WORKFLOW,
            target_id=locked.pk,
            target_summary=locked.name,
            detail=changed_fields(before, _workflow_snapshot(locked))
            | {"team": team.name},
            reason=f"Approval steps changed on the {team.name} team.",
        )
    return locked


class WorkflowActionError(ValueError):
    """Raised when a workflow write cannot be applied.

    ``field`` is the API field the error belongs to.
    """

    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field
        self.message = message


def deactivate_team(*, team: Team, actor) -> Team:
    """Retire a team from routing, keeping its configuration and its history.

    Retiring rather than deleting is the whole reason a team is a
    ``status`` rather than a boolean that HR ticks: an application already
    inside this team's chain still has to be decided, and the stages that prove
    who was entitled to decide it are the team's configuration. The team stops
    routing *new* applications the moment this returns, and everything that
    pointed at it keeps resolving.
    """
    _require_hr_actor(actor, TeamActionError)
    with transaction.atomic():
        locked = Team.objects.select_for_update().get(pk=team.pk)
        if locked.status == Team.Status.INACTIVE:
            return locked

        locked.status = Team.Status.INACTIVE
        locked.save(update_fields=["status", "updated_at"])
        record_audit(
            actor=actor,
            action=AuditEntry.Action.DEACTIVATED,
            target_type=AuditEntry.TargetType.TEAM,
            target_id=locked.pk,
            target_summary=locked.name,
            detail=changed_fields(
                {"status": Team.Status.ACTIVE}, {"status": Team.Status.INACTIVE}
            ),
            reason=f"{locked.name} retired from routing.",
        )
    return locked


def _team_snapshot(team: Team) -> dict:
    return {
        "name": team.name,
        "code": team.code,
        "description": team.description,
        # Both the id and the name: the id is what the row points at and the name
        # is what an audit reader can read without a second lookup. A model
        # instance would not survive being written to the audit's JSON detail.
        "campus_id": team.campus_id,
        "campus": team.campus.name if team.campus_id else "",
        "workflow_id": team.workflow_id,
        "status": team.status,
        "effective_from": team.effective_from,
        "effective_to": team.effective_to,
    }


def team_for_section(section: Section) -> Team | None:
    """The team this section is staffed from, if any.

    A section belongs to a workflow and a workflow is owned by at most one team
    (:attr:`Workflow.team`), so this is one row at most. It is the bridge that
    turns "the approver must be in the team" into a check the membership path
    can perform without the caller passing the team in separately, and it is
    also what every wide holding — team, campus, institution — is scoped by.

    A chain can genuinely have no team: during creation, before the team row is
    attached, or a workflow imported outside any team. That is a real answer to
    this lookup, not an error to raise out of it.
    """
    if section.workflow_id is None:
        return None
    return section.workflow.team


def ensure_team_eligibility(section: Section, user: User) -> None:
    """Refuse an approver who is not a member of the owning team.

    Two roles are the deliberate exception, and they are exceptions for
    different reasons:

    * an **institution-wide** role is not a team's to staff — a
      vice-chancellor's office approves from outside any team — so it is
      appointed without the membership rule. It is also an *administration*
      office: an academic team may not use one at all, and that is refused
      here rather than silently resolved at submission.
    * a **team-wide or campus-wide** holder never reaches this check, because
      those resolve a stage without being appointed to it. What is written on a
      section is always somebody the team itself holds.

    Every other role is scoped, and the scoping is the rule rather than a
    suggestion: somebody approving for a team they are not a member of would be
    approving on a budget and a procedure they do not hold.

    A team with no members cannot scope an approver, so nothing is eligible for
    it. Treating "empty team" as "anybody may approve" would make the rule
    opt-out rather than opt-in, and HR would reach it by creating the team
    before hiring anybody.
    """
    role = section.approver_role
    team = team_for_section(section)
    if role.is_institution_wide:
        if team is not None and team.category != Team.Category.ADMINISTRATION:
            raise TeamActionError(
                "approver",
                f'"{role.label}" is an institution-wide role, and an '
                "institution-wide approver may only serve an administration "
                f'team. "{team.name}" is an academic team — appoint one of its '
                "members to the step, or give the role a team-wide or "
                "campus-wide holder instead.",
            )
        return

    if team is None:
        raise TeamActionError(
            "approver",
            "This chain is not attached to a team yet, so it has nobody to "
            "appoint. Attach the chain to its team first, then appoint an "
            "approver.",
        )

    profile = getattr(user, "employee_profile", None)
    if profile is None:
        raise TeamActionError(
            "approver",
            f"{user.get_full_name() or user.username} has no employee record, so "
            f"there is no team to place them on {team.name} with. Complete their "
            "employee record first.",
        )
    if profile.team_id != team.pk:
        raise TeamActionError(
            "approver",
            f"{user.get_full_name() or user.username} is on "
            f'"{_team_name(profile)}", not on the "{team.name}" team this chain '
            "belongs to. An approver must be a member of the team's own team.",
        )


def ensure_role_consistency(section: Section, user: User) -> None:
    """Refuse an appointment that would give one person two roles on a team.

    The rule being enforced: across every team, an employee holds one approver
    role. The same person may be the approver on several teams, but only ever in
    the same capacity.

    Without it, "Dr Ade is the HOD for ICT but the Bursar for Estate" becomes
    reachable, and the consequence is not confusion in a list but in an audit:
    the same person decides a step under two different roles, each with its own
    history scope, so what they could see depends on which team the application
    arrived through. A role is a statement about capacity, and two capacities at
    once is not something HR can explain afterwards.

    Only live appointments are compared. Closed periods are history and cannot
    conflict with what is being set now.
    """
    team = team_for_section(section)
    team_id = team.pk if team is not None else None
    if team_id is None:
        # Nothing to be consistent with; ``ensure_team_eligibility`` is what
        # refuses this configuration, with a message about the missing team.
        return

    conflicting = (
        Section.objects.filter(
            approver=user,
            is_active=True,
            workflow__team__pk=team_id,
        )
        .exclude(approver_role_id=section.approver_role_id)
        .exclude(pk=section.pk)
        .select_related("approver_role", "workflow__team")
        .distinct()
    )
    conflict = conflicting.first()
    if conflict is None:
        return

    conflict_team = team_for_section(conflict)
    team_name = conflict_team.name if conflict_team is not None else "another team"
    raise TeamActionError(
        "approver",
        f"{user.get_full_name() or user.username} is already appointed as "
        f"{conflict.approver_role.label} on the {team_name} team. One employee "
        f"holds one approver role per team: either use "
        f"{conflict.approver_role.label} here too, or appoint somebody else to "
        "this step.",
    )


def _team_name(profile) -> str:
    """The employee's team name, or a placeholder for a missing one."""
    team = getattr(profile, "team", None)
    return team.name if team is not None else "no team"


def ensure_membership_allowed(section: Section, user: User) -> None:
    """Refuse an appointment the section cannot hold, naming what is wrong.

    Shared by the add-approver action and by writing a chain inline with a team,
    so there is one definition of "this person may be appointed here" and no way
    for the two paths to disagree about it.

    Order matters for which refusal HR reads. The per-workflow check runs before
    the per-team role check because an employee on two stages of one chain breaks
    both, and "John is already on step 1 of this workflow" is the more actionable
    of the two messages.
    """
    if not section.is_active:
        raise TeamActionError(
            "section",
            f'The "{section.name}" section is inactive. Activate it before '
            "appointing an approver.",
        )
    if not user.is_active:
        raise TeamActionError(
            "user",
            f"{user.get_full_name() or user.username} is not an active user. "
            "Activate the account before appointing them to a step.",
        )
    if not section.approver_role.is_active:
        raise TeamActionError(
            "section",
            f'"{section.approver_role.label}" is deactivated. Reactivate it in '
            "Roles before appointing an approver to this section.",
        )
    if section.approver_id == user.pk:
        return
    ensure_team_eligibility(section, user)
    ensure_single_stage_per_workflow(section, user)
    ensure_not_assigned_elsewhere(section, user)
    ensure_role_consistency(section, user)


def ensure_single_stage_per_workflow(section: Section, user: User) -> None:
    """Refuse an approver who already holds another stage of the same workflow.

    Unit 30. Within one workflow an employee appears on exactly one stage, which
    is the third leg of "one employee, one stage, one role per workflow". It also
    is what makes the skip-forward routing unambiguous: "the applicant's stage" is
    a single stage precisely because the employee cannot hold two.

    Scoped to ``section.workflow``, so the same person may be the Supervisor on
    one team's chain and the Bursar on another's — the restriction is per
    workflow, never global.

    The section being written is excluded from the comparison, so re-saving a
    step that already appoints this person is not a conflict with itself; that is
    what lets "John moves from step 1 to step 2" through.

    Mirrored by ``section_workflow_approver_unique`` at the database level. This
    check exists to produce a message naming the person and the other step; the
    constraint exists so nothing can route around the check.
    """
    if section.workflow_id is None:
        return
    other = (
        Section.objects.filter(workflow_id=section.workflow_id, approver=user)
        .exclude(pk=section.pk)
        .select_related("approver_role")
        .order_by("order")
        .first()
    )
    if other is None:
        return
    label = user.get_full_name() or user.username
    raise TeamActionError(
        "approver",
        f"{label} is already assigned to step {other.order} "
        f"({other.approver_role.label}) in this workflow. An employee can only "
        "be assigned to one stage per workflow — appoint somebody else to this "
        "step, or remove the other one.",
    )


def ensure_not_assigned_elsewhere(section: Section, user: User) -> None:
    """Refuse an employee who already sits on another of the team's chains.

    The per-workflow rule (:func:`ensure_single_stage_per_workflow`) stops an
    employee at one stage of *one* chain. This rule goes one further: an
    employee sits on at most **one** of the team's chains at a time, whether
    as a step approver or as a normal workflow member. It is what makes a
    second chain a fresh pool rather than a reshuffle of the first one — the
    people who staff the team's live chain are the people that live chain
    needs, and a replacement chain built from them would staff the same
    people twice.

    The one exception is a **wide approver**: somebody whose holdings (team-
    wide on this team, campus-wide at this team's campus, or institution-wide)
    staff a chain automatically. Their exception is deliberate — a team that
    reaches for its registrar or bursar on the second chain is not moving that
    office off the first one, and :func:`workflow_member_pool` and the
    approver picker keep offering them to every chain.

    The section's own workflow is excluded from the comparison, so re-saving
    a step that already appoints this person is not a conflict with itself —
    the same convention as :func:`ensure_single_stage_per_workflow`.
    """
    team = team_for_section(section)
    if team is None:
        return
    if user.pk in wide_approver_ids_for_team(team):
        return

    others = list(
        Workflow.objects.filter(team=team)
        .exclude(pk=section.workflow_id)
        .values_list("pk", flat=True)
    )
    if not others:
        return

    label = user.get_full_name() or user.username
    membership = (
        WorkflowMember.objects.filter(
            team=team, user=user, workflow_id__in=others
        )
        .select_related("workflow")
        .first()
    )
    if membership is not None:
        raise TeamActionError(
            "approver",
            f"{label} is already a normal member of the "
            f'"{membership.workflow.name}" workflow on this team. One employee '
            "serves one of the team's chains at a time: remove them there "
            "before appointing them to a step here, or leave them where they "
            "are.",
        )

    other_section = (
        Section.objects.filter(
            workflow_id__in=list(others),
            approver=user,
            is_active=True,
        )
        .select_related("workflow", "approver_role")
        .order_by("order")
        .first()
    )
    if other_section is not None:
        raise TeamActionError(
            "approver",
            f"{label} already staffs step {other_section.order} "
            f"({other_section.approver_role.label}) of the "
            f'"{other_section.workflow.name}" workflow on this team. One '
            "employee serves one of the team's chains at a time: keep them "
            f"on {other_section.workflow.name}, or remove them from it before "
            "appointing them to a step here.",
        )


def add_section_member(
    *, section: Section, user: User, actor, effective_from: date | None = None
) -> SectionMember:
    """Appoint one person as a section's approver and audit it.

    A section holds exactly one approver, so this both sets
    :attr:`Section.approver` and opens the :class:`SectionMember` period that
    records it. Appointing somebody new closes the outgoing person's period
    first: leaving two open rows would make "who holds this step" answerable two
    ways, and the roster the snapshot is built from would no longer be the
    configuration.

    A handover happens now or it does not happen. ``effective_from`` is accepted
    for symmetry with the rest of the history, but a date in the future is
    refused: :attr:`Section.approver` is what the step routes to, so a
    not-yet-started appointment would either route to somebody nobody has told
    they are an approver yet, or leave the step pointed at the outgoing person
    forever. Both are worse than making the change on the day it happens, and the
    outgoing person's period is closed on the day of the handover, so the record
    of who held the step still answers every date.
    """
    _require_can_manage_team(actor, team_for_section(section), TeamActionError)
    today = timezone.localdate()
    starts = effective_from or today
    if starts > today:
        raise TeamActionError(
            "effective_from",
            "An approver takes over on the day you appoint them. A step routes "
            "to whoever is named as its approver right now, so there is no way "
            f'to schedule one for {starts.isoformat()}. Make the change on the '
            "day it happens instead.",
        )
    with transaction.atomic():
        ensure_membership_allowed(section, user)
        if section.approver_id == user.pk:
            # Re-saving a form that did not change must not fail, and must not
            # open a second period for somebody already holding the step. The
            # existing open period *is* the answer, so it is returned unchanged
            # rather than replaced with a fresh one.
            existing = SectionMember.objects.filter(
                section=section, user=user
            ).first()
            if existing is not None:
                return existing
        outgoing = section.approver if section.approver_id != user.pk else None
        if outgoing is not None:
            # Close the period on the day the incoming one starts, so no date is
            # covered by two holders and no date is covered by none.
            SectionMember.objects.filter(
                section=section, user=outgoing, effective_to__isnull=True
            ).update(effective_to=max(starts, today))
        section.approver = user
        section.save(update_fields=["approver"])
        membership = SectionMember(
            section=section,
            user=user,
            effective_from=starts,
        )
        membership.full_clean()
        membership.save()
        # When an employee is assigned as a workflow approver, they automatically
        # become a team member. The institution-wide holder is the deliberate
        # exception: their post approves *across* teams, and placing them on this
        # one would re-route their own leave through it and take them off whatever
        # team actually holds them.
        team = team_for_section(section)
        if not section.approver_role.is_institution_wide:
            try:
                profile = user.employee_profile
            except Exception:
                profile = None
            if profile is not None and team is not None and profile.team_id != team.pk:
                profile.team = team
                profile.save(update_fields=["team"])
        record_audit(
            actor=actor,
            action=AuditEntry.Action.CREATED,
            # The workflow, not one of its teams: a section belongs to the
            # workflow, several teams may share it, and "the first team that
            # happens to use this workflow" would attribute the change to a team
            # whose config did not change.
            target_type=AuditEntry.TargetType.WORKFLOW,
            target_id=section.workflow_id,
            target_summary=f"{section.workflow.name} / {section.name}",
            detail=changed_fields(
                {},
                {
                    "approver_user_id": user.pk,
                    "approver": user.get_full_name() or user.username,
                    "section": section.name,
                    "role": section.approver_role.label,
                    "effective_from": membership.effective_from,
                    "replaced_user_id": outgoing.pk if outgoing else None,
                },
            ),
            reason=(
                f"{user.get_full_name() or user.username} appointed as "
                f"{section.approver_role.label} for the {section.name} section"
                + (
                    f", replacing {outgoing.get_full_name() or outgoing.username}."
                    if outgoing
                    else "."
                )
            ),
        )
    return membership


def remove_section_member(
    *, membership: SectionMember, actor, effective_to: date | None = None
) -> SectionMember:
    """Take one section's approver out of force, keeping the record of it.

    The row is **closed** (``effective_to`` set) rather than deleted, because it
    is a record of who was entitled to act and when. Deleting it would rewrite
    the past: an application approved last month by a person with no membership
    today would be left with an approver no configuration can explain.

    :attr:`Section.approver` is cleared at the same time. A step whose period has
    closed must not keep pointing at the person it closed, or the configuration
    would claim somebody is appointed after they stopped being appointed.

    ``effective_to`` defaults to today, so the person stops routing from today
    onwards — a period ending today still covers today, so they can act on what
    they were given, and stops from tomorrow. A period that has not started yet
    never took effect, so it is removed outright rather than left as a row that
    says somebody held a step they never held.
    """
    _require_can_manage_team(
        actor, team_for_section(membership.section), TeamActionError
    )
    with transaction.atomic():
        locked = SectionMember.objects.select_for_update().get(pk=membership.pk)
        section = locked.section
        user = locked.user
        role = section.approver_role
        today = timezone.localdate()
        if effective_to is not None and effective_to < locked.effective_from:
            raise TeamActionError(
                "effective_to",
                f"The membership starts on {locked.effective_from.isoformat()}, "
                f"which is after {effective_to.isoformat()}. The end date cannot "
                "precede the start date.",
            )
        end = effective_to or today

        # A period that has not begun yet never took effect, so removing it
        # deletes the row. A handover that was called off must not leave a record
        # saying somebody was — or was about to be — on a step.
        never_effective = locked.effective_from > today
        detail = changed_fields(
            {
                "member_user_id": user.pk,
                "member": user.get_full_name() or user.username,
                "section": section.name,
                "role": role.label,
                "effective_to": None,
            },
            {"effective_to": None if never_effective else end},
        )
        if never_effective:
            locked.delete()
            # A period that never took effect cannot have been the section's
            # answer, so clearing the appointment would only take away somebody
            # who was never holding it. Left in place deliberately.
        else:
            locked.effective_to = end
            locked.save(update_fields=["effective_to"])
        if section.approver_id == user.pk:
            # The step no longer has an approver, and the team must say so rather
            # than route to a person whose period has closed. This is the
            # "unstaffed step" case the readiness check reports and activation
            # refuses — the point at which it becomes visible.
            section.approver = None
            section.save(update_fields=["approver"])
        record_audit(
            actor=actor,
            action=AuditEntry.Action.DEACTIVATED,
            target_type=AuditEntry.TargetType.WORKFLOW,
            target_id=section.workflow_id,
            target_summary=f"{section.workflow.name} / {section.name}",
            detail=detail,
            reason=(
                f"{user.get_full_name() or user.username} removed from the "
                f"{section.name} section"
                + (
                    "."
                    if never_effective
                    else f", effective {end.isoformat()}."
                )
            ),
        )
        membership = locked
    return membership


def workflow_section_roles(workflow: Workflow) -> list[ApproverRole]:
    """The distinct roles a workflow's sections ask for, in first-seen order.

    A role may repeat across sections; the picker only needs to know which roles
    are in play, once each.
    """
    if workflow.pk is None:
        return []
    role_ids = list(
        workflow.sections.order_by("order")
        .values_list("approver_role", flat=True)
        .distinct()
    )
    if not role_ids:
        return []
    by_id = {
        role.pk: role
        for role in ApproverRole.objects.filter(pk__in=role_ids).select_related()
    }
    return [by_id[role_id] for role_id in role_ids if role_id in by_id]












def _team_member_blockers(team: Team, user: User) -> list[str]:
    """Every responsibility that stops somebody leaving ``team``.

    Each answer names the responsibility so HR can go and release it, rather
    than a single "cannot remove" that would leave the roster stuck.
    """
    reasons: list[str] = []
    team_workflows = Workflow.objects.filter(team=team)
    workflow_ids = list(team_workflows.values_list("id", flat=True))

    if workflow_ids:
        section_approverships = Section.objects.filter(
            workflow_id__in=workflow_ids, approver=user, is_active=True
        ).select_related("approver_role")
        for section in section_approverships:
            reasons.append(
                f'appointed to the "{section.name}" step '
                f'({section.approver_role.label}) on workflow '
                f'"{section.workflow.name}".'
            )

        open_memberships = SectionMember.objects.filter(
            section__workflow_id__in=workflow_ids, user=user, effective_to__isnull=True
        ).select_related("section", "section__workflow")
        for membership in open_memberships:
            reasons.append(
                f'still holds an open approver period on the '
                f'"{membership.section.name}" step of '
                f'"{membership.section.workflow.name}".'
            )

        workflow_memberships = WorkflowMember.objects.filter(
            workflow_id__in=workflow_ids, user=user
        ).select_related("workflow")
        for membership in workflow_memberships:
            reasons.append(
                f'a normal member of the "{membership.workflow.name}" '
                f'workflow. Remove them from that workflow first.'
            )

    team_role_holdings = TeamRoleAssignment.objects.filter(team=team, user=user).select_related(
        "role"
    )
    for holding in team_role_holdings:
        reasons.append(
            f'the team-wide "{holding.role.label}" holder for this team. '
            "Replace or remove that holding first."
        )
    return reasons


def remove_team_member(*, team: Team, user: User, actor) -> None:
    """Take an employee off a team, refusing while they still hold a role.

    A roster entry that still staffs a step, holds a team-wide role, or is a
    normal member of one of the team's workflows is not idle data: routing and
    validation read it. Clearing it anyway would leave a configuration that
    looks staffed and cannot act, so each responsibility is named and must be
    released first.
    """
    _require_can_manage_team(actor, team, WorkflowMemberError)
    profile = _employee_profile_for(user)
    if profile is None:
        raise WorkflowMemberError(
            "user",
            f"{_member_display_name(user)} has no employee record.",
        )
    if profile.team_id != team.pk:
        raise WorkflowMemberError(
            "user",
            f"{_member_display_name(user)} is not on the {team.name} team.",
        )
    blockers = _team_member_blockers(team, user)
    if blockers:
        raise WorkflowMemberError(
            "user",
            f"{_member_display_name(user)} still has responsibilities on "
            f"{team.name}: " + " ".join(blockers),
        )
    with transaction.atomic():
        locked_profile = EmployeeProfile.objects.select_for_update().get(
            pk=profile.pk
        )
        if locked_profile.team_id != team.pk:
            raise WorkflowMemberError(
                "user",
                f"{_member_display_name(user)} is not on the {team.name} team.",
            )
        locked_profile.team = None
        locked_profile.save(update_fields=["team"])
        record_audit(
            actor=actor,
            action=AuditEntry.Action.UPDATED,
            target_type=AuditEntry.TargetType.EMPLOYEE,
            target_id=locked_profile.user_id,
            target_summary=_member_display_name(locked_profile.user),
            detail=changed_fields(
                {"team_id": team.pk, "team": team.name},
                {"team_id": None, "team": None},
            ),
            reason=f"Removed from the {team.name} team.",
        )


def _workflow_team_or_error(workflow: Workflow) -> Team:
    if workflow.team_id is None:
        raise WorkflowMemberError(
            "team",
            f'Workflow "{workflow.name}" is not attached to a team, so it has '
            "no eligibility pool. Attach it to a team first.",
        )
    return workflow.team


def assign_workflow_member(
    *,
    workflow: Workflow,
    user: User,
    actor,
    added_by: User | None = None,
) -> WorkflowMember:
    """Add one team member to a workflow's normal-member pool.

    The eligibility rule is one line: the person must already be on the
    workflow's team. That is enforced in the service against the employee's
    own :attr:`EmployeeProfile.team_id` — a cross-table rule the unique
    constraint cannot express alone — and again at the database by
    ``workflow_member_team_user_unique``, so a concurrent write that slips past
    the service check is still refused rather than creating a second pool
    entry.

    One employee serves at most one of the team's chains at a time, as a
    normal member *or* as a step approver, so somebody already placed on
    another of the team's chains is refused here too. A wide approver is the
    deliberate exception (see :func:`ensure_not_assigned_elsewhere`): their
    holdings staff chains automatically, so they may sit on several, and the
    row is marked with :attr:`~workflows.models.WorkflowMember.is_wide_approver`
    so the database's conditional uniqueness lets them through.
    """
    team = _workflow_team_or_error(workflow)
    _require_can_manage_team(actor, team, WorkflowMemberError)
    if not user.is_active:
        raise WorkflowMemberError(
            "user",
            f"{_member_display_name(user)} is not an active user. Activate the "
            "account before adding them to a workflow.",
        )
    profile = _employee_profile_for(user)
    if profile is None:
        raise WorkflowMemberError(
            "user",
            f"{_member_display_name(user)} has no employee record, so they "
            "cannot be a workflow member. Complete their employee record first.",
        )
    if profile.team_id != team.pk:
        team_name = profile.team.name if profile.team else "no team"
        raise WorkflowMemberError(
            "user",
            f"{_member_display_name(user)} is not on the {team.name} team "
            f'(they are on "{team_name}"). Add them to the team first — a '
            "normal workflow member is always a member of the workflow's team.",
        )

    existing_here = WorkflowMember.objects.filter(workflow=workflow, user=user).first()
    if existing_here is not None:
        return existing_here

    is_wide = user.pk in wide_approver_ids_for_team(team)
    if not is_wide:
        _ensure_member_not_assigned_elsewhere(
            team=team, user=user, workflow=workflow
        )

    with transaction.atomic():
        member = WorkflowMember.objects.create(
            workflow=workflow,
            user=user,
            team=team,
            is_wide_approver=is_wide,
            added_by=added_by or actor,
        )
        record_audit(
            actor=actor,
            action=AuditEntry.Action.CREATED,
            target_type=AuditEntry.TargetType.WORKFLOW,
            target_id=workflow.pk,
            target_summary=f"{workflow.name} / normal member",
            detail=changed_fields(
                {},
                {
                    "user_id": user.pk,
                    "user": _member_display_name(user),
                    "team": team.name,
                },
            ),
            reason=(
                f"{_member_display_name(user)} added as a normal member of the "
                f"{workflow.name} workflow."
            ),
        )
    return member


def _ensure_member_not_assigned_elsewhere(
    *, team: Team, user: User, workflow: Workflow
) -> None:
    """Refuse placing ``user`` on ``workflow`` when they already serve another.

    The same one-chain-per-employee rule as :func:`ensure_not_assigned_elsewhere`,
    from the membership side: a person who is already a normal member of
    another of the team's chains, or already staffs a step of one, cannot be
    placed on this one. Called only for non-wide members, so the refusal
    messages can be plain about "one chain per employee".
    """
    label = _member_display_name(user)
    elsewhere_row = (
        WorkflowMember.objects.filter(team=team, user=user)
        .exclude(workflow=workflow)
        .select_related("workflow")
        .first()
    )
    if elsewhere_row is not None:
        raise WorkflowMemberError(
            "user",
            f"{label} is already a normal member of the "
            f'"{elsewhere_row.workflow.name}" workflow on this team. One '
            "employee is a normal member of one workflow per team — remove "
            "them there first, or leave them where they are.",
        )

    other_section = (
        Section.objects.filter(
            workflow__team=team,
            approver=user,
            is_active=True,
        )
        .exclude(workflow=workflow)
        .select_related("workflow", "approver_role")
        .order_by("order")
        .first()
    )
    if other_section is not None:
        raise WorkflowMemberError(
            "user",
            f"{label} already staffs step {other_section.order} "
            f"({other_section.approver_role.label}) of the "
            f'"{other_section.workflow.name}" workflow on this team. One '
            "employee serves one of the team's chains at a time — remove them "
            "from its steps first, or leave them where they are.",
        )


def remove_workflow_member(*, member: WorkflowMember, actor) -> None:
    """Remove one person from a workflow's normal-member pool."""
    with transaction.atomic():
        locked = WorkflowMember.objects.select_for_update().select_related(
            "workflow", "user", "team"
        ).get(pk=member.pk)
        workflow = locked.workflow
        _require_can_manage_team(actor, locked.team, WorkflowMemberError)
        user = locked.user
        locked.delete()
        record_audit(
            actor=actor,
            action=AuditEntry.Action.DEACTIVATED,
            target_type=AuditEntry.TargetType.WORKFLOW,
            target_id=workflow.pk,
            target_summary=f"{workflow.name} / normal member",
            detail=changed_fields(
                {
                    "user_id": user.pk,
                    "user": _member_display_name(user),
                    "team": locked.team.name if locked.team else None,
                },
                {},
            ),
            reason=(
                f"{_member_display_name(user)} removed as a normal member of "
                f"the {workflow.name} workflow."
            ),
        )


def _pool_person(profile: EmployeeProfile, extra: dict | None = None) -> dict:
    user = profile.user
    payload = {
        "id": user.pk,
        "user": user.pk,
        "full_name": _member_display_name(user),
        "email": user.email,
        "designation": profile.designation,
        "category": profile.category,
        "faculty": profile.faculty,
        "grade": profile.grade,
        "is_active": user.is_active,
    }
    if extra:
        payload.update(extra)
    return payload


def workflow_member_pool(*, team: Team, workflow: Workflow | None = None) -> dict:
    """The eligibility pool for a team's workflow memberships.

    ``available`` is every active team member who is not already serving
    another of the team's chains — as a normal member (:class:`WorkflowMember`)
    or as the single approver staffing a step of one. A **wide approver** is
    the exception and stays available: their holdings staff another chain
    automatically, and a team reuses its registrar or bursar on a second chain
    rather than moving them off the first. When ``workflow`` is given, its own
    members are included in ``available`` (they are already selected) and
    listed separately under ``current`` so a client can render them as checked
    rather than as a second assignment.

    ``assigned_elsewhere`` is read-only: people the team has already placed on
    a different chain, with the workflow named so the refusal message and the
    UI can both say where they already sit.
    """
    team_profiles = list(
        EmployeeProfile.objects.filter(team=team, user__is_active=True)
        .select_related("user", "team")
        .order_by("user__first_name", "user__last_name", "user_id")
    )
    memberships = WorkflowMember.objects.filter(team=team).select_related(
        "workflow", "user"
    )
    by_workflow: dict[int, list[WorkflowMember]] = {}
    for membership in memberships:
        by_workflow.setdefault(membership.workflow_id, []).append(membership)

    current_ids: set[int] = set()
    if workflow is not None:
        current_ids = {m.user_id for m in by_workflow.get(workflow.pk, [])}

    member_elsewhere: dict[int, WorkflowMember] = {}
    for wf_id, rows in by_workflow.items():
        if workflow is not None and wf_id == workflow.pk:
            continue
        for row in rows:
            member_elsewhere[row.user_id] = row

    # Staffing a step of another chain is every bit as "assigned" as being a
    # normal member of one, so step approvers are pooled the same way. Wide
    # approvers are re-added to ``available`` below, whichever source marks
    # them.
    approver_elsewhere: dict[int, tuple[int, str]] = {}
    approver_sections = Section.objects.filter(
        is_active=True, approver__isnull=False, workflow__team=team
    )
    if workflow is not None:
        approver_sections = approver_sections.exclude(workflow=workflow)
    for row in approver_sections.values(
        "approver_id", "workflow__id", "workflow__name"
    ).distinct():
        if row["approver_id"] not in member_elsewhere:
            approver_elsewhere[row["approver_id"]] = (
                row["workflow__id"],
                row["workflow__name"],
            )

    wide_ids = wide_approver_ids_for_team(team)
    elsewhere_ids = (set(member_elsewhere) | set(approver_elsewhere)) - wide_ids
    profiles_by_user = {profile.user_id: profile for profile in team_profiles}

    elsewhere_payload: list[dict] = []
    for user_id in sorted(elsewhere_ids):
        if user_id in member_elsewhere:
            row = member_elsewhere[user_id]
            profile = profiles_by_user.get(user_id)
            if profile is None:
                # A member of another chain who is no longer an active member
                # of the team: not offerable, but still named so the UI can say
                # where they sit.
                user = row.user
                elsewhere_payload.append(
                    {
                        "id": user.pk,
                        "user": user.pk,
                        "full_name": _member_display_name(user),
                        "email": user.email,
                        "workflow_id": row.workflow_id,
                        "workflow_name": row.workflow.name,
                    }
                )
                continue
            payload = _pool_person(
                profile,
                {
                    "workflow_id": row.workflow_id,
                    "workflow_name": row.workflow.name,
                },
            )
        else:
            profile = profiles_by_user.get(user_id)
            if profile is None:
                # Someone staffing a step of another chain from off the team:
                # no longer assignable, and not part of this team's pool.
                continue
            wf_id, wf_name = approver_elsewhere[user_id]
            payload = _pool_person(
                profile,
                {"workflow_id": wf_id, "workflow_name": wf_name},
            )
        elsewhere_payload.append(payload)

    available = [
        _pool_person(profile)
        for profile in team_profiles
        if profile.user_id not in elsewhere_ids
    ]
    current = [
        _pool_person(
            next(p for p in team_profiles if p.user_id == user_id)
        )
        for user_id in sorted(current_ids)
        if any(p.user_id == user_id for p in team_profiles)
    ]
    # Members of the current workflow who are no longer active team members
    # still appear under ``current`` so the edit screen can show and clear them.
    current_user_ids = {row["user"] for row in current}
    for membership in by_workflow.get(workflow.pk if workflow else None, []) or []:
        if membership.user_id in current_user_ids:
            continue
        current.append(
            {
                "id": membership.user_id,
                "user": membership.user_id,
                "full_name": _member_display_name(membership.user),
                "email": membership.user.email,
                "designation": getattr(
                    getattr(membership.user, "employee_profile", None),
                    "designation",
                    "",
                )
                or "",
                "category": getattr(
                    getattr(membership.user, "employee_profile", None),
                    "category",
                    "",
                )
                or "",
                "faculty": getattr(
                    getattr(membership.user, "employee_profile", None),
                    "faculty",
                    "",
                )
                or "",
                "grade": getattr(
                    getattr(membership.user, "employee_profile", None),
                    "grade",
                    "",
                )
                or "",
                "is_active": membership.user.is_active,
            }
        )

    workflow_payload = None
    if workflow is not None:
        workflow_payload = {
            "id": workflow.pk,
            "name": workflow.name,
            "state": workflow.state,
            "is_active": workflow.is_active,
            "is_routing": team.workflow_id == workflow.pk,
        }

    return {
        "team": {"id": team.pk, "name": team.name, "code": team.code},
        "workflow": workflow_payload,
        "available": available,
        "current": current,
        "assigned_elsewhere": sorted(
            elsewhere_payload, key=lambda row: (row["full_name"], row["workflow_name"])
        ),
    }


def sync_workflow_members(
    *, workflow: Workflow, user_ids: list[int] | None, actor
) -> list[WorkflowMember]:
    """Replace a workflow's normal-member list with ``user_ids``.

    Used by the workflow write path so HR can set membership in the same pass
    as the chain itself. ``None`` means "leave membership alone"; an empty list
    means "clear it". Every id is validated through
    :func:`assign_workflow_member`, so a write cannot smuggle in somebody from
    another team or a second workflow of this one.
    """
    if user_ids is None:
        return list(
            WorkflowMember.objects.filter(workflow=workflow).select_related("user")
        )
    team = _workflow_team_or_error(workflow)
    wanted_ids = list(dict.fromkeys(int(pk) for pk in user_ids))
    users = {
        user.pk: user
        for user in User.objects.filter(pk__in=wanted_ids, is_active=True)
    }
    missing = [pk for pk in wanted_ids if pk not in users]
    if missing:
        raise WorkflowMemberError(
            "members",
            f"Workflow member {missing[0]} is missing or is not an active user.",
        )

    with transaction.atomic():
        current = {
            membership.user_id: membership
            for membership in WorkflowMember.objects.filter(workflow=workflow)
        }
        for user_id, membership in list(current.items()):
            if user_id not in wanted_ids:
                remove_workflow_member(member=membership, actor=actor)

        before_ids = set(current)
        members: list[WorkflowMember] = []
        for user_id in wanted_ids:
            members.append(
                assign_workflow_member(
                    workflow=workflow,
                    user=users[user_id],
                    actor=actor,
                    added_by=actor,
                )
            )
        after_ids = {membership.user_id for membership in members}
        if before_ids != after_ids:
            record_audit(
                actor=actor,
                action=AuditEntry.Action.UPDATED,
                target_type=AuditEntry.TargetType.WORKFLOW,
                target_id=workflow.pk,
                target_summary=f"{workflow.name} / normal members",
                detail=changed_fields(
                    {"user_ids": sorted(before_ids)},
                    {"user_ids": sorted(after_ids), "team": team.name},
                ),
                reason=f"Normal workflow members updated on {workflow.name}.",
            )
        return members


def team_member_summaries(team: Team) -> list[dict]:
    """Roster rows for the team members screen, with their workflow footprint."""
    profiles = (
        EmployeeProfile.objects.filter(team=team)
        .select_related("user", "team")
        .order_by("user__first_name", "user__last_name", "user_id")
    )
    workflow_ids = list(Workflow.objects.filter(team=team).values_list("id", flat=True))
    memberships_by_user: dict[int, list[WorkflowMember]] = {}
    if workflow_ids:
        for membership in WorkflowMember.objects.filter(
            workflow_id__in=workflow_ids
        ).select_related("workflow", "user"):
            memberships_by_user.setdefault(membership.user_id, []).append(membership)

    approver_user_ids = set()
    if workflow_ids:
        approver_user_ids = set(
            Section.objects.filter(
                workflow_id__in=workflow_ids, is_active=True, approver__isnull=False
            ).values_list("approver_id", flat=True)
        )

    role_holdings = {
        holding.user_id: holding.role.code
        for holding in TeamRoleAssignment.objects.filter(team=team).select_related("role")
    }

    rows: list[dict] = []
    for profile in profiles:
        user = profile.user
        memberships = memberships_by_user.get(user.pk, [])
        rows.append(
            {
                "id": user.pk,
                "user": user.pk,
                "full_name": _member_display_name(user),
                "email": user.email,
                "designation": profile.designation,
                "category": profile.category,
                "faculty": profile.faculty,
                "grade": profile.grade,
                "is_active": user.is_active,
                "is_section_approver": user.pk in approver_user_ids,
                "team_role": role_holdings.get(user.pk),
                "workflow_memberships": [
                    {
                        "workflow_id": membership.workflow_id,
                        "workflow_name": membership.workflow.name,
                    }
                    for membership in memberships
                ],
                "workflow_count": len(memberships),
            }
        )
    return rows
