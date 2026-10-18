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

from .models import (
    ApplicationStage,
    ApplicationStageApprover,
    Campus,
    CampusRoleAssignment,
    ApprovalDecision,
    ApproverRole,
    Delegation,
    Reassignment,
    RoleAssignment,
    Section,
    SectionMember,
    Team,
    TeamRoleAssignment,
    Workflow,
    WorkflowMember,
)
from .policies import is_self_application
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


def _resolve_stage_role(value) -> ApproverRole | None:
    """Look up an *active* :class:`ApproverRole` by code or primary key."""
    role = _lookup_stage_role(value)
    return role if role is not None and role.is_active else None


def _lookup_stage_role(value) -> ApproverRole | None:
    """Look up an :class:`ApproverRole` by code or primary key, active or not.

    Callers that need to distinguish "deactivated" from "unknown" use this;
    callers that just need a usable role use :func:`_resolve_stage_role`.
    """
    if isinstance(value, ApproverRole):
        return value
    if isinstance(value, str) and not value.strip().isdigit():
        return ApproverRole.objects.filter(code=value).first()
    try:
        pk = int(value)
    except (TypeError, ValueError):
        return None
    return ApproverRole.objects.filter(pk=pk).first()


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


class DelegationActionError(ValueError):
    """Raised when a delegation decision cannot be applied.

    ``field`` is the API field the error belongs to (``"decision_reason"``,
    ``"delegate"``, or ``"detail"``).
    """

    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field
        self.message = message


def is_approver_user(user) -> bool:
    """Whether ``user`` currently holds at least one active approver role.

    The one and only definition of "is an approver", replacing every former
    role-name check. A person is an approver when they can act for at least one
    section whose :class:`~workflows.models.ApproverRole` is active, or when
    they hold a wide holding of an active role:

    * a :class:`~workflows.models.SectionMember` row, or
    * a :class:`~workflows.models.TeamRoleAssignment` row (team-wide), or
    * a :class:`~workflows.models.CampusRoleAssignment` row (campus-wide), or
    * a :class:`~workflows.models.RoleAssignment` row (institution-wide).

    The wide holdings belong here for the same reason the section roster does:
    they are what *resolves* a stage, so a campus registrar whose team's chain
    names their role with no local appointment is an approver in every sense
    that matters — they just never appears on a section.

    Deactivating a role therefore retires the approver status it conferred, and
    ``User.role`` is irrelevant: it records system access, not a place in an
    approval chain.
    """
    if not user or not getattr(user, "is_active", False):
        return False
    user_id = user.pk if hasattr(user, "pk") else user
    if user_id is None:
        return False
    if SectionMember.objects.effective_on().filter(
        user_id=user_id, section__approver_role__is_active=True
    ).exists():
        return True
    if TeamRoleAssignment.objects.filter(
        user_id=user_id, role__is_active=True
    ).exists():
        return True
    if CampusRoleAssignment.objects.filter(
        user_id=user_id, role__is_active=True
    ).exists():
        return True
    return RoleAssignment.objects.filter(
        user_id=user_id, role__is_active=True
    ).exists()


def is_hr_actor(actor) -> bool:
    """Whether ``actor`` is HR or a superuser — the unrestricted team role."""
    return bool(
        actor
        and getattr(actor, "is_authenticated", False)
        and (
            getattr(actor, "role", None) == User.Role.HR
            or getattr(actor, "is_superuser", False)
        )
    )


def is_team_manager(user, team: Team | None) -> bool:
    """Whether ``user`` is the designated manager of ``team``.

    A team's manager is the one team-wide holder flagged
    :attr:`~workflows.models.TeamRoleAssignment.is_team_manager`. Only that
    person — not every wide holder — is authorised to manage the team's members
    and workflows, so management is scoped to a single designated approver.
    """
    if team is None or not getattr(user, "is_authenticated", False):
        return False
    return TeamRoleAssignment.objects.filter(
        team=team, user=user, is_team_manager=True, role__is_active=True
    ).exists()


def _require_hr_actor(actor, error_cls: type[Exception]) -> None:
    """Refuse ``actor`` unless they are HR: the identity/lifecycle guard."""
    if is_hr_actor(actor):
        return
    raise error_cls("detail", "Only HR may perform this action.")


def _require_can_manage_team(actor, team, error_cls: type[Exception]) -> None:
    """Refuse ``actor`` unless they are HR or ``team``'s designated manager.

    A team's day-to-day configuration belongs to its manager once HR has handed
    the team over, but HR keeps the same reach so an installation that has not
    yet designated a manager is not locked out of its own teams. ``error_cls``
    lets each family of operations raise the error its caller already
    translates.
    """
    if is_hr_actor(actor) or is_team_manager(actor, team):
        return
    raise error_cls(
        "detail", "You do not have permission to manage this team."
    )


def approver_role_codes_for(user) -> list[str]:
    """The active approver-role codes ``user`` holds, de-duplicated and sorted.

    Sorted rather than ranked so the answer is stable: a person holding several
    roles is described the same way on every request, which matters for surfaces
    that render a single role label (the delegation list) and for API payloads
    that should not reshuffle between reads.
    """
    if not user or not getattr(user, "is_active", False):
        return []
    user_id = user.pk if hasattr(user, "pk") else user
    codes = set(
        SectionMember.objects.effective_on()
        .filter(user_id=user_id, section__approver_role__is_active=True)
        .values_list("section__approver_role__code", flat=True)
    )
    codes.update(
        RoleAssignment.objects.filter(
            user_id=user_id, role__is_active=True
        ).values_list("role__code", flat=True)
    )
    codes.update(
        TeamRoleAssignment.objects.filter(
            user_id=user_id, role__is_active=True
        ).values_list("role__code", flat=True)
    )
    codes.update(
        CampusRoleAssignment.objects.filter(
            user_id=user_id, role__is_active=True
        ).values_list("role__code", flat=True)
    )
    return sorted(code for code in codes if code)


def approver_role_labels_for(user) -> list[str]:
    """The active approver-role labels ``user`` holds, in a stable order.

    Used by HR surfaces (the delegate candidate list) so a person is described by
    the roles they actually hold rather than by a system access level.
    """
    if not user or not getattr(user, "is_active", False):
        return []
    user_id = user.pk if hasattr(user, "pk") else user
    labels = set(
        SectionMember.objects.effective_on()
        .filter(user_id=user_id, section__approver_role__is_active=True)
        .values_list("section__approver_role__label", flat=True)
    )
    labels.update(
        RoleAssignment.objects.filter(
            user_id=user_id, role__is_active=True
        ).values_list("role__label", flat=True)
    )
    labels.update(
        TeamRoleAssignment.objects.filter(
            user_id=user_id, role__is_active=True
        ).values_list("role__label", flat=True)
    )
    labels.update(
        CampusRoleAssignment.objects.filter(
            user_id=user_id, role__is_active=True
        ).values_list("role__label", flat=True)
    )
    return sorted(label for label in labels if label)


def resolve_delegate_user(approver, delegate_pk: int | None):
    """Return the delegate user when valid, else ``None``.

    A delegate must be an active user holding an approver role and must differ
    from the approver.
    """
    if delegate_pk is None:
        return None
    try:
        delegate = User.objects.get(pk=delegate_pk)
    except User.DoesNotExist:
        return None
    if not is_approver_user(delegate):
        return None
    if approver is not None and delegate.pk == approver.pk:
        return None
    return delegate


def open_request_exists(approver_pk: int) -> bool:
    """True when ``approver_pk`` already has a request awaiting HR review."""
    return Delegation.objects.filter(
        approver_id=approver_pk, status=Delegation.Status.REQUESTED
    ).exists()


def effective_end(ends_on: date | None) -> date:
    """The inclusive end of a delegation period; open-ended becomes ``date.max``."""
    return ends_on or date.max


def find_conflicting_delegation(
    delegation_pk: int | None,
    approver_pk: int,
    starts_on: date,
    ends_on: date | None,
) -> Delegation | None:
    """Another approved delegation of ``approver_pk`` overlapping the period.

    A blank ``ends_on`` means open-ended (overlaps anything from ``starts_on``
    onward). The delegation being decided (``delegation_pk``) is excluded, and
    rejected/cancelled/ended delegations never conflict.
    """
    candidates = Delegation.objects.filter(
        approver_id=approver_pk, status=Delegation.Status.APPROVED
    )
    if delegation_pk is not None:
        candidates = candidates.exclude(pk=delegation_pk)
    for candidate in candidates:
        if date_ranges_overlap(
            starts_on,
            effective_end(ends_on),
            candidate.starts_on,
            effective_end(candidate.ends_on),
        ):
            return candidate
    return None


def active_delegation_for(approver_user) -> Delegation | None:
    """The delegation currently covering ``approver_user``, or ``None``.

    This is the Unit 21 routing boundary: pending approvals assigned to an
    approver move to the delegate while such a delegation is active, and fall
    back to the original approver when none is active (ended or cancelled).
    """
    return _active_delegation_for_id(approver_user.pk)


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


def acting_approver_identity(
    application,
) -> tuple[int | None, str]:
    """``(acting_approver_id, name)`` for a single application.

    The display-name counterpart of :func:`acting_approver_id`, for payloads
    that must show HR *who is actually holding* the application and not only
    the responsible approver the spine names.
    """
    acting_id = acting_approver_id(application)
    if acting_id is None:
        return None, ""
    user = User.objects.filter(pk=acting_id).first()
    return acting_id, (user.get_full_name() if user is not None else "")


def acting_approver_map(
    applications,
) -> dict:
    """``{application_id: (acting_approver_id, name)}`` for a page of rows.

    The bulk counterpart of :func:`acting_approver_identity`: two queries for
    the whole page (one delegation pass, one user-name pass) instead of two per
    application. Only applications with a resolvable responsible approver appear
    in the map, so callers fall back to the single-row resolver for the rest.
    """
    responsible: dict = {}
    for application in applications:
        approver_id = responsible_approver_id(application)
        if approver_id is not None:
            responsible[application.pk] = approver_id

    delegations = active_delegations_for_ids(set(responsible.values()))
    user_ids = set(responsible.values()) | {
        delegation.delegate_id
        for delegation in delegations.values()
        if delegation.delegate_id is not None
    }
    names = {
        user.pk: user.get_full_name() for user in User.objects.filter(pk__in=user_ids)
    }

    resolved: dict = {}
    for application_id, approver_id in responsible.items():
        delegation = delegations.get(approver_id)
        if delegation is not None and delegation.delegate_id is not None:
            resolved[application_id] = (
                delegation.delegate_id,
                names.get(delegation.delegate_id, ""),
            )
        else:
            resolved[application_id] = (approver_id, names.get(approver_id, ""))
    return resolved


def active_delegations_for_ids(
    approver_ids: list[int] | set[int] | tuple[int, ...],
) -> dict[int, Delegation]:
    """The active delegation covering each of ``approver_ids``, keyed by user id.

    The batched twin of :func:`_active_delegation_for_id`, for callers that
    resolve a whole page of applications at once (HR's intervention queue) and
    would otherwise pay one delegation query per row. Overlapping delegations
    cannot happen per approver — the one-open-cover rule plus the approve-time
    overlap check make the newest active row the only one — so a single pass
    with ``-starts_on`` ordering resolves the same winner per approver.
    """
    if not approver_ids:
        return {}
    today = timezone.localdate()
    delegations = (
        Delegation.objects.filter(
            approver_id__in=approver_ids,
            status=Delegation.Status.APPROVED,
            starts_on__lte=today,
        )
        .filter(Q(ends_on__isnull=True) | Q(ends_on__gte=today))
        .order_by("-starts_on")
    )
    resolved: dict[int, Delegation] = {}
    for delegation in delegations:
        resolved.setdefault(delegation.approver_id, delegation)
    return resolved


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


def responsible_approver_id(application, stage=None) -> int | None:
    """The person who has taken up the pending stage, or the sole candidate.

    Display only. An unclaimed section can have many candidates, in which case
    there is no single "responsible" person and this returns ``None``; the
    payloads render that as the candidate list. Authorisation never reads this.

    ``stage`` is an optional already-loaded :class:`ApplicationStage`.
    """
    if application.current_approver_id is not None:
        return application.current_approver_id
    if application.current_stage_id is None:
        return None
    stage = stage if stage is not None else _current_stage(application)
    if stage is None:
        return None
    if stage.assigned_approver_id is not None:
        return stage.assigned_approver_id
    eligible = stage.eligible_approver_ids()
    return eligible[0] if len(eligible) == 1 else None


def acting_approver_id(application, stage=None) -> int | None:
    """The single user entitled to act now, or ``None`` when several may.

    Display only; see :func:`user_may_act` for the authority check. Returns
    ``None`` for an unclaimed section with more than one candidate, because
    naming one of them would be a guess.
    """
    acting = acting_approver_ids(application, eligible_approver_ids(application, stage))
    return acting[0] if len(acting) == 1 else None


def acting_approver_predicate(user) -> Q:
    """Query predicate selecting applications the user may act on now.

    The user may act when the pending stage lists them as eligible — except
    while an active delegation covers them away — and when the pending stage is
    eligible to somebody whose active delegation names the user as delegate.

    Written as explicit ``__in`` subqueries on ``current_stage_id`` rather than
    joins through the multi-valued ``eligible_approvers`` relation: a negated
    condition across a multi-valued join is the shape Django silently splits
    into a subquery, and the intent here is worth stating outright.
    """
    today = timezone.localdate()
    delegations = Delegation.objects.filter(
        status=Delegation.Status.APPROVED,
        starts_on__lte=today,
        delegate__isnull=False,
    ).filter(Q(ends_on__isnull=True) | Q(ends_on__gte=today))
    delegated_approver_ids = list(
        delegations.values_list("approver_id", flat=True).distinct()
    )
    received_approver_ids = list(
        delegations.filter(delegate=user)
        .values_list("approver_id", flat=True)
        .distinct()
    )
    own = Q(
        current_stage_id__in=ApplicationStageApprover.objects.filter(user=user).values_list(
            "stage_id", flat=True
        )
    )
    if user.pk in delegated_approver_ids:
        # This user is away under an active delegation, so their own eligibility
        # does not put anything in their queue. The exclusion is scoped to
        # *them*: subtracting every stage that also holds some other away
        # approver would hide a section from a colleague who is available to act
        # on it, which matters now that a section holds several people.
        own = Q(pk__in=[])
    acting = Q(
        current_stage_id__in=ApplicationStageApprover.objects.filter(
            user_id__in=received_approver_ids
        ).values_list("stage_id", flat=True)
    ) if received_approver_ids else Q(pk__in=[])
    return own | acting


def require_decision_reason(decision_reason: object) -> str:
    """Trim and require an HR decision reason; raises ``DelegationActionError``."""
    reason = (decision_reason or "").strip()
    if not reason:
        raise DelegationActionError(
            "decision_reason", "A decision reason is required."
        )
    return reason


def delegation_summary(delegation: Delegation) -> str:
    approver = delegation.approver.get_full_name()
    delegate = (
        delegation.delegate.get_full_name()
        if delegation.delegate_id
        else "pending"
    )
    period = (
        f"{delegation.starts_on.isoformat()} – "
        f"{(delegation.ends_on.isoformat() if delegation.ends_on else 'open-ended')}"
    )
    return f"Delegation: {approver} → {delegate} ({period})"


def _record_delegation_audit(
    delegation: Delegation, *, action: str, reason: str, before: dict
) -> None:
    if delegation.decided_by is None:
        return
    after = {
        "status": delegation.status,
        "delegate_id": delegation.delegate_id,
    }
    record_audit(
        actor=delegation.decided_by,
        action=action,
        target_type=AuditEntry.TargetType.DELEGATION,
        target_id=delegation.pk,
        target_summary=delegation_summary(delegation),
        detail=changed_fields(before, after),
        reason=reason,
    )


def _overlap_message(delegation: Delegation, conflict: Delegation) -> str:
    """Human-readable conflict naming the other delegate and their period."""
    return (
        f"This period overlaps an approved delegation for "
        f"{delegation.approver.get_full_name()} delegated to "
        f"{conflict.delegate.get_full_name()} "
        f"({conflict.starts_on.isoformat()} to "
        f"{(conflict.ends_on or 'open-ended')})."
    )


def _lock_for_decision(delegation: Delegation) -> Delegation:
    """Re-read ``delegation`` under lock, serialising decisions per approver.

    Locking the approver row *before* the delegation row gives every decision
    for one approver the same lock order, so two concurrent decisions cannot
    interleave (and cannot deadlock against each other). Locking the delegation
    alone would not be enough for ``approve``: the overlap check reads the
    approver's *other* approved rows, which an approver-scoped lock is what
    actually serialises.

    Must be called inside ``transaction.atomic()``.
    """
    User.objects.select_for_update().filter(pk=delegation.approver_id).first()
    return Delegation.objects.select_for_update().get(pk=delegation.pk)


def approve_delegation(delegation: Delegation, actor, data: dict) -> Delegation:
    """Approve a requested delegation with a concrete delegate and reason."""
    from notifications.delegations import DELEGATION_APPROVED, notify_delegation

    if delegation.status != Delegation.Status.REQUESTED:
        raise DelegationActionError(
            "detail", "Only a requested delegation can be approved."
        )
    reason = require_decision_reason(data.get("decision_reason"))
    delegate_pk = data.get("delegate").pk if data.get("delegate") else None
    delegate = resolve_delegate_user(delegation.approver, delegate_pk)
    if delegate is None:
        raise DelegationActionError(
            "delegate",
            "Select an active user with an approver role as the delegate.",
        )
    # Cheap pre-check purely for a fast, friendly error on the common case; the
    # authoritative re-check happens under the approver lock below.
    conflict = find_conflicting_delegation(
        delegation.pk, delegation.approver_id, delegation.starts_on, delegation.ends_on
    )
    if conflict is not None:
        raise DelegationActionError("detail", _overlap_message(delegation, conflict))
    with transaction.atomic():
        delegation = _lock_for_decision(delegation)
        if delegation.status != Delegation.Status.REQUESTED:
            raise DelegationActionError(
                "detail", "Only a requested delegation can be approved."
            )
        conflict = find_conflicting_delegation(
            delegation.pk,
            delegation.approver_id,
            delegation.starts_on,
            delegation.ends_on,
        )
        if conflict is not None:
            raise DelegationActionError("detail", _overlap_message(delegation, conflict))
        delegation.delegate = delegate
        delegation.status = Delegation.Status.APPROVED
        delegation.decision_reason = reason
        delegation.decided_by = actor
        delegation.decided_at = timezone.now()
        delegation.save(
            update_fields=[
                "delegate",
                "status",
                "decision_reason",
                "decided_by",
                "decided_at",
                "updated_at",
            ]
        )
        _record_delegation_audit(
            delegation,
            action=AuditEntry.Action.APPROVED,
            reason=reason,
            before={"status": Delegation.Status.REQUESTED, "delegate_id": None},
        )
        notify_delegation(delegation.pk, DELEGATION_APPROVED)
    return delegation


def reject_delegation(delegation: Delegation, actor, data: dict) -> Delegation:
    """Reject a requested delegation with a mandatory reason."""
    from notifications.delegations import DELEGATION_REJECTED, notify_delegation

    if delegation.status != Delegation.Status.REQUESTED:
        raise DelegationActionError(
            "detail", "Only a requested delegation can be rejected."
        )
    reason = require_decision_reason(data.get("decision_reason"))
    with transaction.atomic():
        delegation = _lock_for_decision(delegation)
        if delegation.status != Delegation.Status.REQUESTED:
            raise DelegationActionError(
                "detail", "Only a requested delegation can be rejected."
            )
        delegation.status = Delegation.Status.REJECTED
        delegation.decision_reason = reason
        delegation.decided_by = actor
        delegation.decided_at = timezone.now()
        delegation.save(
            update_fields=[
                "status",
                "decision_reason",
                "decided_by",
                "decided_at",
                "updated_at",
            ]
        )
        _record_delegation_audit(
            delegation,
            action=AuditEntry.Action.REJECTED,
            reason=reason,
            before={"status": Delegation.Status.REQUESTED, "delegate_id": None},
        )
        notify_delegation(delegation.pk, DELEGATION_REJECTED)
    return delegation


def cancel_delegation(delegation: Delegation, actor, data: dict) -> Delegation:
    """Cancel a scheduled or active approved delegation."""
    from notifications.delegations import DELEGATION_CANCELLED, notify_delegation

    if delegation.status != Delegation.Status.APPROVED:
        raise DelegationActionError(
            "detail", "Only an approved delegation can be cancelled."
        )
    if delegation.state == "ended":
        raise DelegationActionError(
            "detail", "A completed delegation cannot be cancelled."
        )
    reason = require_decision_reason(data.get("decision_reason"))
    with transaction.atomic():
        delegation = _lock_for_decision(delegation)
        # The caller's copy can go stale between the pre-check and this lock.
        if delegation.status != Delegation.Status.APPROVED:
            raise DelegationActionError(
                "detail", "Only an approved delegation can be cancelled."
            )
        if delegation.state == "ended":
            raise DelegationActionError(
                "detail", "A completed delegation cannot be cancelled."
            )
        delegation.status = Delegation.Status.CANCELLED
        delegation.decision_reason = reason
        delegation.decided_by = actor
        delegation.decided_at = timezone.now()
        delegation.save(
            update_fields=[
                "status",
                "decision_reason",
                "decided_by",
                "decided_at",
                "updated_at",
            ]
        )
        _record_delegation_audit(
            delegation,
            action=AuditEntry.Action.CANCELLED,
            reason=reason,
            before={"status": Delegation.Status.APPROVED},
        )
        notify_delegation(delegation.pk, DELEGATION_CANCELLED)
    return delegation


class ReassignmentError(ValueError):
    """Raised when a reassignment cannot be applied.

    ``field`` is the API field the error belongs to (``"application"``,
    ``"to_approver"``, ``"reason"``, or ``"detail"``).
    """

    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field
        self.message = message


def require_reassignment_reason(reason: object) -> str:
    """Trim and require an HR reassignment reason; raises ``ReassignmentError``."""
    reason = (reason or "").strip()
    if not reason:
        raise ReassignmentError(
            "reason", "A reassignment reason is required."
        )
    return reason


class SelfApprovalBlockedError(Exception):
    """No approver in the remaining chain may act because it is the applicant.

    Raised when every remaining stage of a chain would resolve to the applicant
    themself, so there is nobody left to route to. The mandatory stage cannot be
    skipped (invariant 12.3) and the applicant must never approve their own
    leave, so the operation that would have handed the application to them is
    refused and rolled back instead. HR must correct the workflow configuration
    or reassign the application.
    """

    def __init__(self, messages: list[str]):
        self.messages = messages
        super().__init__("; ".join(messages))


def is_self_approver(user_id: int | None, application: LeaveApplication) -> bool:
    """Whether ``user_id`` is the applicant who owns ``application``.

    A thin id-based wrapper over the authoritative
    :func:`workflows.policies.is_self_application`, for the call sites that hold
    a user id (a resolved ``StageDefinition.approver_user_id``) rather than a
    loaded ``User``.
    """
    return is_self_application(user_id, application)


def reassign_application(
    *,
    application: LeaveApplication,
    to_approver: User,
    actor: User,
    reason: object,
) -> Reassignment:
    """Reassign a pending application to a replacement approver.

    Validates that the application is pending (``submitted``), the replacement
    is an active user with an approver role, the replacement differs from the
    current approver (when one is set) and from the applicant, and that a
    reason is supplied. On success, records a :class:`Reassignment` history row,
    moves ``LeaveApplication.current_approver``, and adds the replacement to the
    open stage's eligibility snapshot.

    The snapshot write is what makes the reassignment actionable: authority is
    read from the snapshot, not from the spine, so without it the replacement
    would be named as the owner of the application and still be refused a
    403. The original members are kept rather than replaced — a section is
    resolved by whoever acts first, so adding HR's replacement widens the
    section instead of revoking the colleague who was already on it.
    """
    if application.status != LeaveApplication.Status.SUBMITTED:
        raise ReassignmentError(
            "application",
            "Only a pending (submitted) application can be reassigned.",
        )
    reason = require_reassignment_reason(reason)
    if not is_approver_user(to_approver):
        raise ReassignmentError(
            "to_approver",
            "Select an active user with an approver role as the replacement.",
        )
    if (
        application.current_approver is not None
        and to_approver.pk == application.current_approver.pk
    ):
        raise ReassignmentError(
            "to_approver",
            "The application is already assigned to this approver.",
        )
    if is_self_approver(to_approver.pk, application):
        raise ReassignmentError(
            "to_approver",
            "A pending application cannot be assigned to its own applicant.",
        )
    with transaction.atomic():
        application = LeaveApplication.objects.select_for_update().get(
            pk=application.pk
        )
        if application.status != LeaveApplication.Status.SUBMITTED:
            raise ReassignmentError(
                "application",
                "Only a pending (submitted) application can be reassigned.",
            )
        from_approver = application.current_approver
        reassignment = Reassignment.objects.create(
            application=application,
            from_approver=from_approver,
            to_approver=to_approver,
            reason=reason,
            decided_by=actor,
        )
        application.current_approver = to_approver
        application.save(update_fields=["current_approver", "updated_at"])
        # Authority is read from the stage's eligibility snapshot, so the
        # replacement has to be added to it. ``get_or_create`` keeps this
        # idempotent for a second HR intervention that picks the same person.
        if application.current_stage_id is not None:
            ApplicationStageApprover.objects.get_or_create(
                stage_id=application.current_stage_id,
                user=to_approver,
            )
        if actor is not None:
            record_audit(
                actor=actor,
                action=AuditEntry.Action.REASSIGNED,
                target_type=AuditEntry.TargetType.REASSIGNMENT,
                target_id=reassignment.pk,
                target_summary=(
                    f"Reassignment of {application.reference_number}"
                ),
                detail=changed_fields(
                    {"current_approver_id": from_approver.pk if from_approver else None},
                    {"current_approver_id": to_approver.pk},
                ),
                reason=reason,
            )
        # Both approvers' queues just changed; tell them once this is durable.
        from notifications.reassignments import notify_reassignment

        notify_reassignment(reassignment.pk)
    return reassignment


def assign_workflow(application):
    """Materialise the configured section chain for ``application``.

    Runs idempotently: if the current submission cycle already has stages, the
    existing live stage is returned unchanged. Otherwise the workflow provider's
    section definitions are validated and bulk-created with exactly one ``pending``
    stage, and ``application.current_stage`` is pointed at it.

    **The chain always starts at section one, and no section is ever skipped.**
    A step names one person, and if that person is the applicant they cannot act
    on their own leave, so the provider refuses to resolve the step at all and
    submission is refused there rather than routing the application past a step
    (invariants 12.3, 12.7). The old "start after the applicant's last stage,
    never travelling backwards" rule is gone with the multi-approver sections it
    existed for: there is nothing to skip, because there is nothing else in a
    step.

    Raises :class:`WorkflowAssignmentError` when the provider yields no/ill-formed
    sections or a section cannot be resolved to at least one active user other
    than the applicant.
    Returns the first (pending) stage.
    """
    from .providers import WorkflowConfigError, get_workflow_provider

    with transaction.atomic():
        cycle = application.submission_cycle
        existing = application.stages.filter(submission_cycle=cycle).first()
        if existing is not None:
            return application.current_stage

        try:
            definitions = get_workflow_provider().get_stage_definitions(application)
        except WorkflowConfigError as exc:
            raise WorkflowAssignmentError([str(exc)])
        if not definitions:
            raise WorkflowAssignmentError(["No workflow sections configured."])
        orders = [definition.order for definition in definitions]
        if sorted(orders) != list(range(1, len(definitions) + 1)):
            raise WorkflowAssignmentError(
                ["Workflow sections must be ordered 1..N."]
            )
        # A section nobody can act for is refused here rather than materialised
        # and left pending forever. The provider normally raises for this, but
        # assign_workflow is also reachable with a provider that returns a gap,
        # and an eligibility row cannot name nobody.
        unstaffed = [
            f'No active approver for the "{definition.role_label}" approval section.'
            for definition in definitions
            if not definition.approver_user_ids and not definition.skipped
        ]
        if unstaffed:
            raise WorkflowAssignmentError(unstaffed)

        # Every routable definition carries at least one eligible user: the
        # provider refuses an unsatisfiable section rather than returning a gap,
        # and it has already removed the applicant. A *skipped* definition
        # deliberately carries none -- nobody may act there -- so it is exempt
        # from the check above (Unit 30).
        #
        # The chain's shape is therefore decided by the provider, not here. It
        # starts at section one for an ordinary applicant, at the first stage
        # above the applicant's own for an approver applicant, and at an appended
        # HR stage when the applicant holds the final step.
        last_index = len(definitions) - 1
        # The one stage that opens pending: the lowest order the provider did not
        # skip. Every provider must leave at least one routable stage, or there
        # is nothing to decide -- the HR destination is what stops that happening
        # when the applicant holds the final step.
        pending_order = min(
            (d.order for d in definitions if not d.skipped),
            default=None,
        )
        if pending_order is None:
            raise WorkflowAssignmentError(
                ["This workflow has no approval stage left for HR to decide."]
            )
        stages = [
            ApplicationStage(
                application=application,
                submission_cycle=cycle,
                stage_order=definition.order,
                role=definition.role,
                role_label=definition.role_label,
                role_ref_id=definition.role_id,
                history_scope=definition.history_scope or "",
                handles_cancellation=definition.handles_cancellation,
                section_ref_id=definition.section_id,
                assigned_approver=None,
                status=_initial_stage_status(definition, pending_order),
                skip_reason=definition.skip_reason,
                is_final=index == last_index,
            )
            for index, definition in enumerate(definitions)
        ]

        ApplicationStage.objects.bulk_create(stages)

        # Snapshot who may act on each section, now. This is what makes an
        # in-flight application immune to later membership edits (invariant
        # 12.5) and what self-approval is enforced through.
        ApplicationStageApprover.objects.bulk_create(
            ApplicationStageApprover(stage=stage, user_id=user_id)
            for stage, definition in zip(stages, definitions)
            for user_id in definition.approver_user_ids
        )

        # The application opens at the stage that was materialised pending, not
        # at the first stage in the chain: a chain that starts with skipped stages
        # has to point at the one somebody can act on (Unit 30).
        opening = next(
            stage
            for stage in stages
            if stage.status == ApplicationStage.Status.PENDING
        )
        application.current_stage = opening
        application.current_approver = None
        application.save(update_fields=["current_stage", "current_approver", "updated_at"])
        _record_skipped_stages(application, stages)
        return opening


def _record_skipped_stages(application, stages) -> None:
    """Audit the stages an application was not routed through (Unit 30).

    Written by the applicant, because the applicant is who caused it: their own
    position decided the chain. Without this the audit trail would show a chain
    starting at stage two with nothing saying why, which is the one question an
    audit exists to answer.
    """
    skipped = [
        {
            "order": stage.stage_order,
            "role_label": stage.role_label,
            "reason": stage.skip_reason,
        }
        for stage in stages
        if stage.status == ApplicationStage.Status.SKIPPED
    ]
    if not skipped:
        return
    orders = ", ".join(str(entry["order"]) for entry in skipped)
    record_audit(
        actor=application.employee,
        action=AuditEntry.Action.STAGE_SKIPPED,
        target_type=AuditEntry.TargetType.APPLICATION,
        target_id=application.pk,
        target_summary=(
            f"{application.reference_number}: stage(s) {orders} skipped"
        ),
        detail={
            "stages": skipped,
            "reason": "The applicant's own position is at or below this stage.",
        },
    )


def _initial_stage_status(definition, pending_order: int) -> str:
    """The status a freshly materialised stage starts in.

    Driven by the definition rather than by its position (Unit 30). The provider
    decides which stage the application actually opens at:

    * a **skipped** stage is born ``SKIPPED`` -- terminal, carrying the reason the
      provider recorded. It is never pending, so it never reaches an approver's
      queue and never raises a notification;
    * the first stage the provider did not skip is ``PENDING`` and the rest are
      ``WAITING``. For an ordinary applicant that is section one; for an approver
      applicant it is the first stage above their own.
    """
    if definition.skipped:
        return ApplicationStage.Status.SKIPPED
    if definition.order == pending_order:
        return ApplicationStage.Status.PENDING
    return ApplicationStage.Status.WAITING


class ApprovalNotFoundError(Exception):
    """The application does not exist or is not viewable by the approver."""


class ApprovalNotAllowedError(Exception):
    """The approver may not decide right now; carries a reason code."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


class ApprovalStageChangedError(Exception):
    """The stage was already decided by someone else (stale/conflict, 409)."""


class ApprovalConflictError(Exception):
    """Approving would over-subscribe the applicant's team on some day.

    A hard block enforced at every stage (UI/UX Phase 2, spec 3.2): the same
    number the team calendar flags is refused here, so a client cannot skip the
    rule. Carries the :class:`leave.conflicts.TeamConflict` that stopped it.
    """

    def __init__(self, conflict):
        self.conflict = conflict
        super().__init__("approval_conflict")


class ApprovalValidationError(ValueError):
    """Invalid action or comment; carries a dict of field errors."""

    def __init__(self, errors: dict):
        self.errors = errors
        super().__init__(str(errors))


def _next_activatable_stage(application, decided_stage):
    """The next stage to activate after ``decided_stage`` was approved.

    The first stage above ``decided_stage`` that is still waiting. A **skipped**
    stage is never activated (Unit 30): it resolves nobody by construction, so
    activating it would strand the chain, and continuing past it is the whole
    point of having skipped it in the first place. It is still looked up under a
    row lock and its eligibility re-checked, because a stage with no one able to
    act is a chain that cannot finish and must be reported rather than activated
    as a dead end.

    Raises ``ApprovalValidationError`` when the chain simply ends or when only
    skipped stages remain, and :class:`SelfApprovalBlockedError` when the next
    stage has no eligible approver — which can only happen on a chain materialised
    before sections, where the applicant used to be skipped forward over.

    Must be called inside ``transaction.atomic()``.
    """
    remaining = list(
        ApplicationStage.objects.select_for_update()
        .filter(
            application=application,
            submission_cycle=application.workflow_chain_cycle,
            stage_order__gt=decided_stage.stage_order,
        )
        .order_by("stage_order")
    )
    if not remaining:
        raise ApprovalValidationError({"action": "Workflow chain is incomplete."})

    candidate = next(
        (
            stage
            for stage in remaining
            if stage.status == ApplicationStage.Status.WAITING
        ),
        None,
    )
    if candidate is None:
        raise ApprovalValidationError({"action": "Workflow chain is incomplete."})
    if not candidate.eligible_approvers.exists():
        raise SelfApprovalBlockedError(
            [
                "This application cannot be advanced: nobody can act on the "
                f"{candidate.role_label} stage, so there is no approver left to "
                "sign it off. An approver cannot approve their own leave "
                "application, and a mandatory section cannot be skipped. Human "
                "Resources must appoint another member of that section, or change "
                "the workflow, before this application can be decided."
            ]
        )
    return candidate


def decide(*, application_id, actor, action: str, comment: str = "", expected_version: int):
    """Record one decision and advance the application (Unit 16, spec 6.3).

    Runs in one transaction under a row lock on both the application and its
    current stage. Writes exactly one immutable :class:`ApprovalDecision`,
    transitions stage/application state, increments ``decision_version``, and
    emits the approval event on commit.

    Raises ``ApprovalNotFoundError`` (404), ``ApprovalValidationError`` (400),
    ``ApprovalNotAllowedError`` (403) or ``ApprovalStageChangedError`` (409).
    Returns the persisted application.
    """
    from .events import (
        APPLICATION_FINALISED,
        DECISION_RECORDED,
        ApprovalEvent,
        emit_approval_event,
    )
    from .policies import get_decision_authority

    if action not in ApprovalDecision.Action.values:
        raise ApprovalValidationError({"action": "Must be approve, reject or return_for_correction."})

    comment = (comment or "").strip()
    if len(comment) > 1000:
        raise ApprovalValidationError({"comment": "Must be at most 1000 characters."})
    if action in (ApprovalDecision.Action.REJECT, ApprovalDecision.Action.RETURN_FOR_CORRECTION) and not comment:
        raise ApprovalValidationError(
            {"comment": "A comment is required when rejecting or returning for correction."}
        )

    from .policies import get_decision_authority as _authority

    app = None
    with transaction.atomic():
        app = LeaveApplication.objects.select_for_update().filter(id=application_id).first()
        if app is None:
            raise ApprovalNotFoundError()

        if app.status == LeaveApplication.Status.CANCELLED:
            # Unit 18: a withdrawn or cancelled application can never be decided
            # again; surface as a conflict so clients can refresh.
            raise ApprovalStageChangedError()

        if app.current_stage_id is None:
            raise ApprovalNotAllowedError("application_closed")

        stage = (
            ApplicationStage.objects.select_for_update()
            .filter(pk=app.current_stage_id)
            .first()
        )
        # The live chain lives under ``workflow_chain_cycle`` (stages are reused
        # across resubmission cycles per Unit 17); the guard must not compare
        # against ``app.submission_cycle``, which increments on resubmission.
        if stage is None or stage.submission_cycle != app.workflow_chain_cycle:
            raise ApprovalNotAllowedError("application_closed")

        if stage.decision_version != expected_version:
            raise ApprovalStageChangedError()

        if ApprovalDecision.objects.filter(
            application=app,
            approver=actor,
            submission_cycle=app.submission_cycle,
        ).exists():
            raise ApprovalStageChangedError()

        authority = _authority(actor, app)
        if not authority.can_decide:
            raise ApprovalNotAllowedError(authority.reason or "not_current_stage")
        if stage.status != ApplicationStage.Status.PENDING:
            raise ApprovalNotAllowedError("already_decided")

        if action == ApprovalDecision.Action.APPROVE:
            # UI/UX Phase 2, spec 3.2: an approval that would leave the
            # applicant's team over-subscribed on any day is refused, at every
            # stage, from the same number the team calendar shows. Imported here
            # because ``leave.conflicts`` reaches back into leave models.
            from leave.conflicts import find_team_conflict  # noqa: PLC0415

            conflict = find_team_conflict(app)
            if conflict is not None:
                raise ApprovalConflictError(conflict)

        before_status = app.status
        before_order = stage.stage_order
        before_version = stage.decision_version

        # Claim the stage by acting on it. A section is open to all of its
        # members, so this is the moment the stage stops being open: the
        # ``select_for_update`` above is what makes the claim exclusive, and the
        # optimistic ``decision_version`` check refuses the loser of a race with
        # 409 rather than letting two people decide the same section.
        stage.assigned_approver = actor
        app.current_approver = actor

        ApprovalDecision.objects.create(
            application=app,
            stage=stage,
            approver=actor,
            approver_name=actor.get_full_name(),
            role_label=stage.role_label,
            action=action,
            comment=comment,
            submission_cycle=app.submission_cycle,
        )

        stage.decision_version = before_version + 1
        next_stage = None
        if action == ApprovalDecision.Action.APPROVE:
            stage.status = ApplicationStage.Status.APPROVED
            if stage.is_final:
                app.status = LeaveApplication.Status.APPROVED
            else:
                next_stage = _next_activatable_stage(app, stage)
                next_stage.status = ApplicationStage.Status.PENDING
        elif action == ApprovalDecision.Action.REJECT:
            stage.status = ApplicationStage.Status.REJECTED
            app.status = LeaveApplication.Status.REJECTED
        else:
            stage.status = ApplicationStage.Status.CORRECTION_REQUESTED
            app.status = LeaveApplication.Status.CORRECTION_REQUIRED

        # Persist the decided stage first so a single ``pending`` stage always
        # exists at any one moment (enforced by the partial unique constraint).
        stage.save(
            update_fields=[
                "status",
                "decision_version",
                "assigned_approver",
                "updated_at",
            ]
        )
        if next_stage is not None:
            next_stage.save(update_fields=["status", "decision_version", "updated_at"])
            app.current_stage = next_stage
            # The spine follows the stage. The next section is open, so nobody has
            # taken it up yet and ``current_approver`` is cleared: its members
            # are read from the stage's eligibility snapshot.
            app.current_approver = None

        after_status = app.status
        after_order = (
            app.current_stage.stage_order
            if app.current_stage_id is not None
            else stage.stage_order
        )
        # Unit 23b (D3): stamp the final approval once, in the same save, so the
        # document can state when the leave was approved and the date can never
        # disagree with the status.
        finalised = after_status == LeaveApplication.Status.APPROVED
        if finalised and app.approved_on is None:
            app.approved_on = timezone.now()
        app.save(
            update_fields=[
                "status",
                "current_stage",
                "current_approver",
                "approved_on",
                "updated_at",
            ]
        )

        if finalised:
            # Unit 25 (D4) + Unit 23b (D8): the ledger deduction and the
            # approved-document record are both business consequences of the
            # final approval, so they are written inside this transaction and a
            # failure in either rolls the approval back. The render itself is
            # enqueued on commit, so the document is a retryable derived
            # artifact rather than part of the atomic unit.
            from leave.services.finalise import finalise_approved_application

            finalise_approved_application(app)

        record_audit(
            actor=actor,
            action=_audit_action(action),
            target_type=AuditEntry.TargetType.APPLICATION,
            target_id=app.pk,
            target_summary=app.reference_number,
            detail=changed_fields(
                {
                    "status": before_status,
                    "current_stage_order": before_order,
                    "decision_version": before_version,
                },
                {
                    "status": after_status,
                    "current_stage_order": after_order,
                    "decision_version": stage.decision_version,
                },
            ),
            reason=comment,
        )

        event = ApprovalEvent(
            kind=(
                APPLICATION_FINALISED
                if after_status == LeaveApplication.Status.APPROVED
                else DECISION_RECORDED
            ),
            application_id=str(app.pk),
            reference_number=app.reference_number or "",
            action=action,
            stage_order=stage.stage_order,
            role_label=stage.role_label,
            approver_id=actor.id,
            approver_name=actor.get_full_name(),
            comment=comment,
            submission_cycle=app.submission_cycle,
        )
        transaction.on_commit(lambda e=event: emit_approval_event(e))

    return app


def _audit_action(action: str) -> str:
    mapping = {
        ApprovalDecision.Action.APPROVE: AuditEntry.Action.APPROVED,
        ApprovalDecision.Action.REJECT: AuditEntry.Action.REJECTED,
        ApprovalDecision.Action.RETURN_FOR_CORRECTION: AuditEntry.Action.CORRECTION_REQUESTED,
    }
    return mapping[action]

# ---------------------------------------------------------------------------
# Approver roles, role assignments, and teams (HR-managed configuration).
#
# Every write here is a configuration change: it runs inside a transaction,
# records one audit entry, and refuses any state that would leave a workflow
# stage or a routing decision unresolvable.
# ---------------------------------------------------------------------------
class RoleActionError(ValueError):
    """Raised when an approver-role write cannot be applied.

    ``field`` is the API field the error belongs to (``"detail"`` when the
    problem is the role's state rather than one submitted value).
    """

    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field
        self.message = message


def role_usage_map(roles) -> dict[int, list[str]]:
    """``_role_usage`` for a whole queryset, in a fixed number of queries.

    The Roles screen renders usage for every role at once, and the naive
    per-role version cost one query per blocker per role — 69 queries to
    serialize six roles, and worse as HR adds more. Collecting each blocker
    kind for all roles at once and assembling the sentences in Python makes the
    list cost three queries no matter how many roles it holds.
    """
    role_ids = {role.pk for role in roles}
    usage: dict[int, list[str]] = {pk: [] for pk in role_ids}
    if not role_ids:
        return usage

    # A section and its members are one blocker from HR's point of view: the
    # workflow uses this role. Grouping by workflow and merging into a single
    # clause avoids telling HR the same workflow is a problem twice.
    section_rows = (
        Section.objects.filter(
            approver_role_id__in=role_ids,
            workflow__is_active=True,
            is_active=True,
        )
        .values("approver_role_id", "workflow_id", "workflow__name")
        .annotate(count=Count("id"))
        .order_by("workflow__name", "workflow_id")
    )
    section_counts: dict[tuple[int, str], int] = {}
    workflow_names: dict[tuple[int, str], str] = {}
    for row in section_rows:
        key = (row["approver_role_id"], row["workflow_id"])
        section_counts[key] = row["count"]
        workflow_names[key] = row["workflow__name"]

    member_rows = (
        SectionMember.objects.filter(
            section__approver_role_id__in=role_ids,
            section__is_active=True,
            section__workflow__is_active=True,
        )
        .values(
            "section__approver_role_id",
            "section__workflow_id",
        )
        .annotate(count=Count("id"))
    )
    member_counts: dict[tuple[int, str], int] = {
        (row["section__approver_role_id"], row["section__workflow_id"]): row["count"]
        for row in member_rows
    }

    for key, section_total in section_counts.items():
        parts = [f"{section_total} section" + ("" if section_total == 1 else "s")]
        members = member_counts.get(key, 0)
        if members:
            parts.append(f"{members} member" + ("" if members == 1 else "s"))
        usage[key[0]].append(
            f"the '{workflow_names[key]}' workflow ({' and '.join(parts)})"
        )

    holders = (
        RoleAssignment.objects.filter(role_id__in=role_ids, user__is_active=True)
        .select_related("user")
        .order_by("user_id")
    )
    for assignment in holders:
        name = assignment.user.get_full_name() or assignment.user.username
        usage[assignment.role_id].append(f"{name}, who holds it institution-wide")

    return usage


def _role_usage(role: ApproverRole) -> list[str]:
    """Human-readable sentences naming everything currently using ``role``.

    Each clause names the specific blocker and its size, so a refused
    deactivation tells HR exactly which workflows, teams, and people to fix
    instead of just saying "in use".
    """
    return role_usage_map([role]).get(role.pk, [])


def ensure_role_not_in_use(role: ApproverRole) -> None:
    """Refuse while an active workflow stage, team member, or holder uses the role."""
    clauses = _role_usage(role)
    if not clauses:
        return
    raise RoleActionError(
        "detail",
        f"This role cannot be deactivated because it is used by "
        f"{', and by '.join(clauses)}. Remove those references first, or "
        "deactivate the workflow or team instead.",
    )


def role_code_from_name(name: object) -> str:
    """Derive a role's stable code from its name, uniquely.

    The code is what a workflow stage keys off and what historical stage
    snapshots quote, so it has to exist and has to be unique — but asking HR to
    type one alongside the name is asking for the same word twice, and for the
    two to disagree. Deriving it removes that class of mistake entirely.

    Uniqueness is checked against the table rather than assumed, because
    slugifying two different names ("Head of Department" and "Head of
    Departments") gives the same code.
    """
    cleaned = (name or "").strip() if isinstance(name, str) else ""
    if not cleaned:
        raise RoleActionError("label", "Enter a role name.")
    base = slugify(cleaned)
    if not base:
        raise RoleActionError(
            "label",
            "The role name must contain a letter or number to form its code.",
        )
    code = base[:50]
    suffix = 2
    while ApproverRole.objects.filter(code=code).exists():
        tail = f"-{suffix}"
        code = f"{base[: 50 - len(tail)]}{tail}"
        suffix += 1
    return code


def create_approver_role(*, actor, data: dict) -> ApproverRole:
    """Create one approver role from its name, and audit it.

    Only the name is HR's to give. ``code`` is derived from it (see
    :func:`role_code_from_name`), and the behavioural fields — history scope,
    cancellation handling, institution-wide eligibility — are left at their
    defaults and changed later through the role's own edit, by somebody who has
    the context to decide them.

    Deriving rather than asking is what keeps a role from existing in two
    incompatible states: a name that says "Vice Chancellor" beside a code that
    says ``vc``, where the label is what every screen shows and the code is what
    every rule reads.
    """
    data = dict(data)
    label = (data.get("label") or "").strip()
    if not label:
        raise RoleActionError("label", "Enter a role name.")
    data["label"] = label
    data["code"] = role_code_from_name(label)
    for field in (
        "history_scope",
        "handles_cancellation",
        "is_institution_wide",
        "is_active",
    ):
        data.pop(field, None)
    with transaction.atomic():
        role = ApproverRole.objects.create(**data)
        record_audit(
            actor=actor,
            action=AuditEntry.Action.CREATED,
            target_type=AuditEntry.TargetType.APPROVER_ROLE,
            target_id=role.pk,
            target_summary=role.label,
            detail={"before": None, "after": _role_snapshot(role)},
        )
    return role


def update_approver_role(*, role: ApproverRole, actor, data: dict) -> ApproverRole:
    """Update a role's editable fields and audit the change.

    ``code`` is immutable once anything references the role, because workflow
    stages, team members, and historical stage snapshots all key off it; HR
    edits ``label``, ``description``, ``history_scope``, and
    ``handles_cancellation`` here. ``is_institution_wide`` is deliberately not
    one of them: a role's scope is decided by where it is held, on the Approvers
    page — it becomes institution-wide the moment its first institution-wide
    holder is assigned, not from a checkbox on this screen.

    ``is_active`` is deliberately *not* handled here: retiring a role runs the
    in-use check, so it has its own action.
    """
    with transaction.atomic():
        role = ApproverRole.objects.select_for_update().get(pk=role.pk)
        before = _role_snapshot(role)
        if "code" in data and data["code"] != before["code"]:
            raise RoleActionError(
                "code",
                "The role code cannot be changed once the role is referenced by a "
                "workflow stage, a team member, or a role assignment. Create a new "
                "role instead and retire this one.",
            )
        data.pop("code", None)
        data.pop("is_active", None)
        if (
            data.get("is_institution_wide", before["is_institution_wide"])
            != before["is_institution_wide"]
        ):
            raise RoleActionError(
                "is_institution_wide",
                "A role's scope is decided on the Approvers page: the role "
                "becomes institution-wide when its first institution-wide holder "
                "is assigned there. It is not toggled from the role itself.",
            )
        data.pop("is_institution_wide", None)
        for field, value in data.items():
            setattr(role, field, value)
        role.save()
        record_audit(
            actor=actor,
            action=AuditEntry.Action.UPDATED,
            target_type=AuditEntry.TargetType.APPROVER_ROLE,
            target_id=role.pk,
            target_summary=role.label,
            detail=changed_fields(before, _role_snapshot(role)),
        )
    return role


def deactivate_approver_role(*, role: ApproverRole, actor) -> ApproverRole:
    """Soft-retire a role, refusing while anything still uses it."""
    if not role.is_active:
        return role
    ensure_role_not_in_use(role)
    with transaction.atomic():
        role = ApproverRole.objects.select_for_update().get(pk=role.pk)
        if not role.is_active:
            return role
        ensure_role_not_in_use(role)
        before = _role_snapshot(role)
        role.is_active = False
        role.save(update_fields=["is_active", "updated_at"])
        record_audit(
            actor=actor,
            action=AuditEntry.Action.CANCELLED,
            target_type=AuditEntry.TargetType.APPROVER_ROLE,
            target_id=role.pk,
            target_summary=role.label,
            detail=changed_fields(before, _role_snapshot(role)),
            reason="Role deactivated by HR.",
        )
    return role


def _role_snapshot(role: ApproverRole) -> dict:
    return {
        "code": role.code,
        "label": role.label,
        "description": role.description,
        "is_active": role.is_active,
        "history_scope": role.history_scope,
        "handles_cancellation": role.handles_cancellation,
        "is_institution_wide": role.is_institution_wide,
    }


def create_role_assignment(*, user: User, role: ApproverRole, actor) -> RoleAssignment:
    """Assign an institution-wide role to a user and audit it.

    The first institution-wide holder is what *makes* a role institution-wide:
    assigning holder number one to a team role on the Approvers page is the
    decision that the role covers every application — not a checkbox on the
    role's own editor (which no longer offers one). The role is promoted in the
    same atomic step as the holding, and the promotion is refused only while the
    role is still held on a team or campus, because a role cannot be held wide
    at a scope *and* institution-wide at once.

    A role has exactly one institution-wide approver: once a holding exists this
    single write is refused for any other person, naming the current holder. A
    role is never assigned to a second approver — changing who holds it is a
    remove first, then a fresh assignment.
    """
    with transaction.atomic():
        role = ApproverRole.objects.select_for_update().get(pk=role.pk)
        role.full_clean(exclude=["code", "label"])
        if not role.is_active:
            raise RoleActionError(
                "role",
                f'"{role.label}" is deactivated. Reactivate it in Roles, or pick '
                "an active role.",
            )
        if not role.is_institution_wide:
            if (
                TeamRoleAssignment.objects.filter(role=role).exists()
                or CampusRoleAssignment.objects.filter(role=role).exists()
            ):
                raise RoleActionError(
                    "role",
                    f'"{role.label}" is already held on a team or campus. Remove '
                    "those holders under Approvers first — a role held wide at a "
                    "team or campus cannot be held institution-wide too.",
                )
            before = _role_snapshot(role)
            role.is_institution_wide = True
            role.save(update_fields=["is_institution_wide", "updated_at"])
            record_audit(
                actor=actor,
                action=AuditEntry.Action.UPDATED,
                target_type=AuditEntry.TargetType.APPROVER_ROLE,
                target_id=role.pk,
                target_summary=role.label,
                detail=changed_fields(before, _role_snapshot(role)),
                reason=(
                    f'"{role.label}" named institution-wide by its first '
                    "institution-wide holder on the Approvers page."
                ),
            )
        if not user.is_active:
            raise RoleActionError(
                "user",
                f"{user.get_full_name() or user.username} is not an active user. "
                "Activate the account before assigning a role.",
            )
        current_holder = (
            RoleAssignment.objects.select_for_update().filter(role=role).first()
        )
        if current_holder is not None and current_holder.user_id != user.pk:
            raise RoleActionError(
                "role",
                f'"{role.label}" is already held institution-wide by '
                f"{current_holder.user.get_full_name() or current_holder.user.username}. "
                "A role has one institution-wide approver; remove that holder under "
                "Approvers first, then assign another.",
            )
        _ensure_single_wide_holding(user, exclude_role=role)
        assignment, created = RoleAssignment.objects.get_or_create(
            user=user, role=role
        )
        if not created:
            raise RoleActionError(
                "user",
                f"{user.get_full_name() or user.username} already holds the "
                f"{role.label} role.",
            )
        record_audit(
            actor=actor,
            action=AuditEntry.Action.CREATED,
            target_type=AuditEntry.TargetType.APPROVER_ROLE,
            target_id=role.pk,
            target_summary=role.label,
            detail=changed_fields(
                {},
                {
                    "user_id": user.pk,
                    "user": user.get_full_name() or user.username,
                    "assignment_id": assignment.pk,
                },
            ),
            reason=(
                f"{user.get_full_name() or user.username} assigned the "
                f"{role.label} role institution-wide."
            ),
        )
    return assignment


def remove_role_assignment(*, assignment: RoleAssignment, actor) -> RoleAssignment:
    """Remove an institution-wide role holding and audit it."""
    with transaction.atomic():
        user = assignment.user
        role = assignment.role
        detail = changed_fields(
            {
                "user_id": user.pk,
                "user": user.get_full_name() or user.username,
                "assignment_id": assignment.pk,
            },
            {},
        )
        assignment.delete()
        record_audit(
            actor=actor,
            action=AuditEntry.Action.CANCELLED,
            target_type=AuditEntry.TargetType.APPROVER_ROLE,
            target_id=role.pk,
            target_summary=role.label,
            detail=detail,
            reason=(
                f"{user.get_full_name() or user.username} no longer holds the "
                f"{role.label} role."
            ),
        )
    return assignment


def create_team_role_assignment(
    *, team: Team, role: ApproverRole, user: User, actor, is_team_manager: bool = False
) -> TeamRoleAssignment:
    """Give a role one team-wide holder, replacing any existing one.

    One holder per role per team is a constraint rather than a default: a team
    whose role has two wide holders would resolve a stage to a person nobody
    can name, and the resolution rule refuses ties anyway. So writing a second
    holder *is* the replacement — HR picks the role and the person in one
    screen, and saving it moves the holding rather than asking for a delete
    first.

    Refuses an institution-wide role (that holding lives under Approvers), a
    retired role, and a holder whose category does not match the team's, and
    audits both the appointment and the replacement.

    ``is_team_manager`` designates the holder as the team's single designated
    manager, clearing the flag from any other holder on the team. When a role
    that already carries the manager flag is re-pointed at a new person, the
    new person inherits it — the designation belongs to the role holding, not
    to the person who used to hold it.
    """
    _require_hr_actor(actor, RoleActionError)
    with transaction.atomic():
        _ensure_wide_role(role, user, "team")
        profile = user.employee_profile
        if profile.category != team.category:
            raise RoleActionError(
                "user",
                f"{user.get_full_name() or user.username} is an "
                f"{profile.get_category_display()} employee, but \"{team.name}\" "
                f"is an {team.get_category_display()} team. A team-wide approver "
                f"must match the team's category.",
            )
        _ensure_single_wide_holding(user, exclude_role=role, exclude_team=team)
        previous = (
            TeamRoleAssignment.objects.select_for_update()
            .filter(team=team, role=role)
            .first()
        )
        # A role that already carries the manager flag keeps it when it is
        # re-pointed: the designation follows the role holding.
        if previous is not None and previous.is_team_manager:
            is_team_manager = True
        if is_team_manager:
            # Enforce "one manager per team" *before* this holding is written,
            # so the partial unique constraint is never momentarily violated:
            # every other holder on the team has the flag cleared first.
            others = TeamRoleAssignment.objects.select_for_update().filter(
                team=team, is_team_manager=True
            )
            if previous is not None:
                others = others.exclude(pk=previous.pk)
            others.update(is_team_manager=False)
        before = None
        if previous is not None:
            if previous.user_id == user.pk:
                raise RoleActionError(
                    "user",
                    f"{user.get_full_name() or user.username} already holds the "
                    f"{role.label} role on {team.name}.",
                )
            before = _team_assignment_snapshot(previous)
            previous.user = user
            previous.is_team_manager = is_team_manager
            previous.save(update_fields=["user", "is_team_manager"])
            assignment = previous
        else:
            assignment = TeamRoleAssignment.objects.create(
                team=team, role=role, user=user, is_team_manager=is_team_manager
            )
        record_audit(
            actor=actor,
            action=(
                AuditEntry.Action.UPDATED
                if before is not None
                else AuditEntry.Action.CREATED
            ),
            target_type=AuditEntry.TargetType.TEAM,
            target_id=team.pk,
            target_summary=team.name,
            detail=changed_fields(
                before or {},
                _team_assignment_snapshot(assignment),
            ),
            reason=(
                f"{user.get_full_name() or user.username} holds {role.label} "
                f"for the {team.name} team."
                + (
                    " Designated as team manager."
                    if assignment.is_team_manager
                    else ""
                )
            ),
        )
    return assignment


def set_team_manager(*, assignment: TeamRoleAssignment, actor) -> TeamRoleAssignment:
    """Designate a team-wide holding as its team's manager.

    Clears the flag from any other holder on the same team, so a team always
    has at most one manager. A no-op when this holding is already the manager.
    """
    _require_hr_actor(actor, RoleActionError)
    with transaction.atomic():
        locked = TeamRoleAssignment.objects.select_for_update().get(pk=assignment.pk)
        if locked.is_team_manager:
            return locked
        before = _team_assignment_snapshot(locked)
        # Clear the flag from the other holders first, so the partial unique
        # constraint ("one manager per team") is never momentarily violated.
        TeamRoleAssignment.objects.select_for_update().filter(
            team_id=locked.team_id, is_team_manager=True
        ).exclude(pk=locked.pk).update(is_team_manager=False)
        locked.is_team_manager = True
        locked.save(update_fields=["is_team_manager"])
        team = locked.team
        record_audit(
            actor=actor,
            action=AuditEntry.Action.UPDATED,
            target_type=AuditEntry.TargetType.TEAM,
            target_id=team.pk,
            target_summary=team.name,
            detail=changed_fields(before, _team_assignment_snapshot(locked)),
            reason=(
                f"{locked.user.get_full_name() or locked.user.username} is the "
                f"team manager for {team.name}."
            ),
        )
    return locked


def clear_team_manager(*, assignment: TeamRoleAssignment, actor) -> TeamRoleAssignment:
    """Remove the manager designation from a team-wide holding.

    A no-op when the holding was not the manager.
    """
    _require_hr_actor(actor, RoleActionError)
    with transaction.atomic():
        locked = TeamRoleAssignment.objects.select_for_update().get(pk=assignment.pk)
        if not locked.is_team_manager:
            return locked
        before = _team_assignment_snapshot(locked)
        locked.is_team_manager = False
        locked.save(update_fields=["is_team_manager"])
        team = locked.team
        record_audit(
            actor=actor,
            action=AuditEntry.Action.UPDATED,
            target_type=AuditEntry.TargetType.TEAM,
            target_id=team.pk,
            target_summary=team.name,
            detail=changed_fields(before, _team_assignment_snapshot(locked)),
            reason=(
                f"{locked.user.get_full_name() or locked.user.username} is no "
                f"longer the team manager for {team.name}."
            ),
        )
    return locked


def remove_team_role_assignment(*, assignment: TeamRoleAssignment, actor) -> None:
    """Drop a team-wide holding and audit it."""
    with transaction.atomic():
        team = assignment.team
        role = assignment.role
        detail = changed_fields(_team_assignment_snapshot(assignment), {})
        assignment.delete()
        record_audit(
            actor=actor,
            action=AuditEntry.Action.CANCELLED,
            target_type=AuditEntry.TargetType.TEAM,
            target_id=team.pk,
            target_summary=team.name,
            detail=detail,
            reason=f"{role.label} no longer has a team-wide holder on {team.name}.",
        )


def create_campus_role_assignment(
    *, campus: Campus, role: ApproverRole, user: User, actor
) -> CampusRoleAssignment:
    """Give a role one campus-wide holder, replacing any existing one.

    Scoped to the campus, which is what makes it apply to every team *at* that
    campus and to no team anywhere else. Same one-holder rule and same
    replacement semantics as the team-wide holding.

    Every team at a campus is an academic team — an administration team is never
    campus-based — so the holder is refused unless they are an Academic
    employee.
    """
    with transaction.atomic():
        _ensure_wide_role(role, user, "campus")
        profile = user.employee_profile
        if profile.category != EmployeeProfile.Category.ACADEMIC:
            raise RoleActionError(
                "user",
                f"{user.get_full_name() or user.username} is an "
                f"{profile.get_category_display()} employee. Every team at a "
                f"campus is an academic team, so a campus-wide approver must be "
                f"an Academic employee.",
            )
        _ensure_single_wide_holding(user, exclude_role=role, exclude_campus=campus)
        previous = (
            CampusRoleAssignment.objects.select_for_update()
            .filter(campus=campus, role=role)
            .first()
        )
        before = None
        if previous is not None:
            if previous.user_id == user.pk:
                raise RoleActionError(
                    "user",
                    f"{user.get_full_name() or user.username} already holds the "
                    f"{role.label} role at {campus.name}.",
                )
            before = _campus_assignment_snapshot(previous)
            previous.user = user
            previous.save(update_fields=["user"])
            assignment = previous
        else:
            assignment = CampusRoleAssignment.objects.create(
                campus=campus, role=role, user=user
            )
        record_audit(
            actor=actor,
            action=(
                AuditEntry.Action.UPDATED
                if before is not None
                else AuditEntry.Action.CREATED
            ),
            target_type=AuditEntry.TargetType.CAMPUS,
            target_id=campus.pk,
            target_summary=campus.name,
            detail=changed_fields(
                before or {},
                _campus_assignment_snapshot(assignment),
            ),
            reason=(
                f"{user.get_full_name() or user.username} holds {role.label} "
                f"at {campus.name}."
            ),
        )
    return assignment


def remove_campus_role_assignment(*, assignment: CampusRoleAssignment, actor) -> None:
    """Drop a campus-wide holding and audit it."""
    with transaction.atomic():
        campus = assignment.campus
        role = assignment.role
        detail = changed_fields(_campus_assignment_snapshot(assignment), {})
        assignment.delete()
        record_audit(
            actor=actor,
            action=AuditEntry.Action.CANCELLED,
            target_type=AuditEntry.TargetType.CAMPUS,
            target_id=campus.pk,
            target_summary=campus.name,
            detail=detail,
            reason=f"{role.label} no longer has a holder at {campus.name}.",
        )


def _ensure_wide_role(role: ApproverRole, user: User, scope: str) -> None:
    """The shared preconditions of a team- or campus-wide holding."""
    scope_label = "team" if scope == "team" else "campus"
    if not role.is_active:
        raise RoleActionError(
            "role",
            f'"{role.label}" is deactivated. Reactivate it in Roles, or pick '
            "an active role.",
        )
    if role.is_institution_wide:
        raise RoleActionError(
            "role",
            f'"{role.label}" is an institution-wide role. Assign its holder '
            "under Approvers, not on a "
            f"{scope_label}.",
        )
    if not user.is_active:
        raise RoleActionError(
            "user",
            f"{user.get_full_name() or user.username} is not an active user. "
            "Activate the account before assigning a role.",
        )
    if getattr(user, "employee_profile", None) is None:
        raise RoleActionError(
            "user",
            f"{user.get_full_name() or user.username} has no employee record, so "
            "there is nothing to hold an approver role with. Complete their "
            "employee record first.",
        )


def _ensure_single_wide_holding(
    user: User,
    *,
    exclude_role: ApproverRole | None = None,
    exclude_team: Team | None = None,
    exclude_campus: Campus | None = None,
) -> None:
    """Refuse a person a second wide approver role, anywhere in the school.

    A wide approver is someone a whole scope falls back to, and HR changes them
    per role per scope; one person covering a role on one team, a role at one
    campus, *and* a role institution-wide means three sections claim the same
    person, and a role written onto a team page is how somebody keeps appearing
    in the other sections' pickers. So a person holds **one** wide approver role,
    at one of the three scopes — which is also the promise the pickers make:
    once assigned, somebody is gone from every other wide-approver section.

    The exclusions name the (scope, role) pair this write is replacing: the same
    role at the same scope is that write's own target (already its holder, or
    about to be), not a second holding, so a save can still re-point a holding
    in place.
    """
    holdings = RoleAssignment.objects.filter(user=user)
    if exclude_role is not None:
        holdings = holdings.exclude(role=exclude_role)
    holding = holdings.select_related("role").first()
    if holding is not None:
        where = f"{holding.role.label} institution-wide"
    else:
        team_holdings = TeamRoleAssignment.objects.filter(user=user)
        if exclude_team is not None and exclude_role is not None:
            team_holdings = team_holdings.exclude(team=exclude_team, role=exclude_role)
        holding = team_holdings.select_related("role", "team").first()
        if holding is not None:
            where = f"{holding.role.label} as a team-wide approver on {holding.team.name}"
        else:
            campus_holdings = CampusRoleAssignment.objects.filter(user=user)
            if exclude_campus is not None and exclude_role is not None:
                campus_holdings = campus_holdings.exclude(
                    campus=exclude_campus, role=exclude_role
                )
            holding = campus_holdings.select_related("role", "campus").first()
            if holding is not None:
                where = f"{holding.role.label} as a campus-wide approver at {holding.campus.name}"
            else:
                where = None
    if where is not None:
        raise RoleActionError(
            "user",
            f"A person may hold only one wide approver role, and "
            f"{user.get_full_name() or user.username} already holds {where}. "
            f"Remove that holding before assigning another one.",
        )


def _team_assignment_snapshot(assignment: TeamRoleAssignment) -> dict:
    return {
        "assignment_id": assignment.pk,
        "role_id": assignment.role_id,
        "role": assignment.role.label,
        "user_id": assignment.user_id,
        "user": assignment.user.get_full_name() or assignment.user.username,
        "is_team_manager": assignment.is_team_manager,
    }


def _campus_assignment_snapshot(assignment: CampusRoleAssignment) -> dict:
    return {
        "assignment_id": assignment.pk,
        "role_id": assignment.role_id,
        "role": assignment.role.label,
        "user_id": assignment.user_id,
        "user": assignment.user.get_full_name() or assignment.user.username,
    }


class CampusActionError(ValueError):
    """Raised when a campus write cannot be applied."""

    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field
        self.message = message


def _campus_snapshot(campus: Campus) -> dict:
    return {
        "name": campus.name,
        "code": campus.code,
        "description": campus.description,
        "is_active": campus.is_active,
    }


def create_campus(*, actor, data: dict) -> Campus:
    """Create a campus and audit it."""
    with transaction.atomic():
        campus = Campus.objects.create(**data)
        record_audit(
            actor=actor,
            action=AuditEntry.Action.CREATED,
            target_type=AuditEntry.TargetType.CAMPUS,
            target_id=campus.pk,
            target_summary=campus.name,
            detail={"before": None, "after": _campus_snapshot(campus)},
        )
    return campus


def update_campus(*, campus: Campus, actor, data: dict) -> Campus:
    """Update a campus and audit the change.

    A campus is PROTECTed from deletion because a team references it, and its
    code is treated like a role's: once referenced, changing it would leave a
    team pointing at a code nobody recognises.
    """
    with transaction.atomic():
        campus = Campus.objects.select_for_update().get(pk=campus.pk)
        before = _campus_snapshot(campus)
        if "code" in data and data["code"] != before["code"]:
            if campus.teams.exists():
                raise CampusActionError(
                    "code",
                    "The campus code cannot be changed once a team uses it. "
                    "Create a new campus instead.",
                )
        for field, value in data.items():
            setattr(campus, field, value)
        campus.save()
        record_audit(
            actor=actor,
            action=AuditEntry.Action.UPDATED,
            target_type=AuditEntry.TargetType.CAMPUS,
            target_id=campus.pk,
            target_summary=campus.name,
            detail=changed_fields(before, _campus_snapshot(campus)),
        )
    return campus


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

    Side-effect free and safe to call at any time. A team is in force from
    creation, so this is a *standing* check rather than a gate before an
    activation: it is how HR finds the step that has lost its approver since the
    chain was written, and reports a chainless team's missing workflow.

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


def create_team(
    *,
    actor,
    data: dict,
    workflow_config: dict | None = None,
    manager: dict | None = None,
) -> Team:
    """Create a team together with the approval chain it routes through.

    ``data`` holds the team's own editable fields. ``workflow_config`` is
    ``{"name", "sections": [{"name", "approver_role", "approver"}]}`` — the
    chain, its ordered sections, and the one person who may act at each step, all
    created as part of the same transaction as the team.

    ``workflow_config`` is optional, and a team created without one is **in
    force but chainless**. That is the two-page configuration HR performs: the
    team's identity first, its approval steps second. Until it owns a chain it
    routes nothing — there is simply nothing to route through — while still
    being a real, inspectable object that :func:`validate_team` can report on.

    When a chain *is* supplied it is created in the same transaction, so a team
    and its chain are never two objects to keep in step. Everything lands
    together or not at all: a half-built team with a chain but no steps is exactly
    the object that used to look configured and then fail at submission.

    ``manager`` is ``{"role": <ApproverRole>, "user": <User>}``, the second page
    of HR's create flow. When given, that team-scoped role is appointed to the
    person as a team-wide holding and flagged the team's manager, in the same
    transaction as the team, through :func:`create_team_role_assignment`.
    Naming the role *and* the person is the whole instruction: the holding is
    what lets the manager act, so "assign the manager" is not a separate object
    to keep in step.

    A team starts **active**: creating it is the act of putting it in force, and
    HR does not confirm that afterwards — so there is no draft state and no
    activation step. It does not route until it owns a chain.
    """
    _require_hr_actor(actor, TeamActionError)
    with transaction.atomic():
        data = dict(data)
        data.setdefault("code", _unique_team_code(data.get("name", "")))
        # Creating a team *is* putting it in force, whatever the caller sent:
        # routing is a separate, validated decision that begins once the team
        # owns a chain.
        data["status"] = Team.Status.ACTIVE

        # The team is written first so its chain's steps can be checked against
        # the team — an approver is only eligible relative to the team they are
        # appointed for, and the membership is on the employee record. The whole
        # thing is one transaction, so a bad section list still leaves nothing
        # behind.
        team = Team(**data)
        _ensure_team_category(team)
        team.save()

        if workflow_config is not None:
            config = dict(workflow_config)
            sections_payload = [
                dict(section, approver=section.get("approver"))
                for section in config.get("sections") or []
            ]
            workflow_name = _unique_workflow_name(
                config.get("name") or f"{data.get('name', '').strip()} workflow"
            )
            workflow = Workflow.objects.create(
                name=workflow_name,
                team=team,
                # Dated like any other chain written against a term, so a team
                # created with its steps is not the one configuration whose
                # window is left open-ended.
                effective_from=timezone.localdate(),
                effective_to=academic_calendar_end(),
            )
            team.workflow = workflow
            team.save(update_fields=["workflow", "updated_at"])

            sections = replace_workflow_sections(workflow, sections_payload)
            _attach_section_approvers(
                team=team,
                workflow=workflow,
                sections=sections,
                config=sections_payload,
                actor=actor,
                place_on_team=True,
            )

        record_audit(
            actor=actor,
            action=AuditEntry.Action.CREATED,
            target_type=AuditEntry.TargetType.TEAM,
            target_id=team.pk,
            target_summary=team.name,
            detail={"before": None, "after": _team_snapshot(team)},
        )
        if team.workflow_id is not None:
            record_audit(
                actor=actor,
                action=AuditEntry.Action.CREATED,
                target_type=AuditEntry.TargetType.WORKFLOW,
                target_id=team.workflow_id,
                target_summary=team.workflow.name,
                detail={
                    "before": None,
                    "after": {
                        "name": team.workflow.name,
                        "created_with_team": team.name,
                        "workflow": _workflow_snapshot(team.workflow),
                    },
                },
                reason=f"Created with the {team.name} team.",
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


def _place_new_team_member(*, team: Team, section: Section, user: User) -> None:
    """Put ``user`` on a team being created, so their appointment can be judged.

    A team is its members' organisational unit and a newly created team has no
    roster, so naming somebody one of its approvers is what places them on it.
    This only ever runs while the team is being created in the same transaction.

    Someone already on a *different* team is refused rather than moved. Silently
    moving them would leave the team they came from with approvers who can no
    longer be eligible, and doing that as a side effect of creating some other
    team is not a change HR should get by accident — it is a deliberate edit to
    their employee record, and the message says so.
    """
    role = section.approver_role
    if role.is_institution_wide:
        # An institution-wide holder approves from outside any team, so there is
        # no membership to establish.
        return

    profile = getattr(user, "employee_profile", None)
    if profile is None:
        # No employee record is a real gap, not a placement problem. Leave it to
        # ensure_team_eligibility to refuse with its own message.
        return
    if profile.team_id == team.pk or profile.team_id is None:
        profile.team = team
        profile.save(update_fields=["team"])
        return

    raise TeamActionError(
        "approver",
        f"{user.get_full_name() or user.username} is on "
        f'"{_team_name(profile)}", so they cannot also be an approver for the '
        f'"{team.name}" team. Move them to "{team.name}" on their employee '
        "record first, or appoint someone already on the team.",
    )


def _attach_section_approvers(
    *,
    team: Team,
    workflow: Workflow,
    sections: list[Section],
    config: list[dict],
    actor=None,
    place_on_team: bool = False,
) -> None:
    """Appoint the requested approver on each newly written section.

    Appointment goes through the same guards as the standalone action
    (:func:`ensure_membership_allowed`) so a chain cannot be created with a
    deactivated account, an approver from outside the team, or a second role for
    somebody who already holds one on it — the rules live in one place, and this
    path cannot grant something the other path would refuse.

    The team is passed in rather than looked up because the chain is written
    *before* the team row exists; the team the approver is checked against is the
    one being created.

    ``place_on_team`` is set only by :func:`create_team`. A team *is* its members'
    organisational unit, and a team being created has no roster yet, so naming
    someone as one of its approvers is what puts them on it — otherwise the one
    request that configures a whole team could never succeed, because every
    approver would be refused for belonging to the very team being built. It is
    deliberately not set when rewriting an existing chain: re-pointing a step must
    never quietly move an employee to another team, which is a separate,
    deliberate change to their employee record.
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
        if place_on_team:
            _place_new_team_member(team=team, section=section, user=user)
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
    *,
    team: Team,
    actor,
    data: dict,
    workflow_config: dict | None = None,
    manager: dict | None = None,
) -> Team:
    """Update a team's editable fields, its steps, and its designated manager.

    ``status`` is not editable here. Teams start in force when HR creates them,
    and the one move left — retirement — goes through :func:`deactivate_team`,
    so it is audited as the distinct event it is rather than being a PATCH that
    quietly took a team out of service.

    ``workflow`` is not editable here: routing a team through one of its chains
    is a decision of its own and goes through :func:`route_team`, so editing a
    team's name can never quietly re-route it.

    ``workflow_config`` replaces the chain's *steps*, not the chain itself: a
    team's chain belongs to it, so the only edit available is the same edit the
    form used to create it. Sections are identified by their (role, name) pair,
    so reordering keeps each step's roster while a role or name change rebuilds
    that step empty. Removing a step an in-flight application is waiting on is
    refused by the ``PROTECT`` on ``ApplicationStage.section_ref``, so an edit
    here cannot rewrite the past.

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

        if workflow_config is not None:
            _replace_team_chain(
                team=team,
                actor=actor,
                config=workflow_config,
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
    """Point a team at one of the chains it owns.

    Routing is a decision about *which* of the team's chains is in force, so it
    is an action rather than a field edit. The workflow named must be one the
    team already owns (:attr:`Workflow.team`), so "route through this chain
    instead" can never become "adopt somebody else's chain" — which would
    strand every application inside the old one at a step nobody staffs.

    The team's manager owns this day-to-day decision, but HR keeps the same
    reach so an installation that has not yet designated a manager can still
    configure its own teams.
    """
    _require_can_manage_team(actor, team, TeamActionError)
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
    _require_can_manage_team(actor, team, WorkflowActionError)
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


def _replace_team_chain(*, team: Team, actor, config: dict) -> None:
    """Write the steps of the chain this team owns.

    A team created without one — page 1 of the team form, saved before its steps
    were known — gets its chain created here, so "save the team again with the
    steps" is the same action whether or not the team already had a chain. A team
    that already has one has it rewritten in place, through
    :func:`replace_workflow_sections`, so section identity, ordering, and the
    ``PROTECT`` guard on a step a live application points at are one
    implementation rather than two that can drift.
    """
    config = dict(config)
    sections_payload = [
        dict(section, approver=section.get("approver"))
        for section in config.get("sections") or []
    ]

    workflow = team.workflow
    created = False
    if workflow is None:
        workflow = Workflow.objects.create(
            name=_unique_workflow_name(
                str(config.get("name") or f"{team.name} workflow").strip()
            ),
            team=team,
            # Dated the same way :func:`create_workflow` dates a chain: in force
            # from today and running to the end of the academic calendar, since
            # a chain written inline by the team form is the same statement about
            # a term as one written on its own screen.
            effective_from=config.get("effective_from") or timezone.localdate(),
            effective_to=(
                config.get("effective_to")
                if config.get("effective_to") is not None
                else academic_calendar_end()
            ),
        )
        team.workflow = workflow
        team.save(update_fields=["workflow"])
        created = True
    elif workflow.team_id != team.pk:
        workflow.team = team
        workflow.save(update_fields=["team"])

    before = {} if created else _workflow_snapshot(workflow)
    try:
        sections = replace_workflow_sections(workflow, sections_payload)
    except StageSequenceError as exc:
        raise TeamActionError(exc.field, exc.message)
    if config.get("name") and not created:
        workflow.name = _unique_workflow_name(
            str(config["name"]).strip(), exclude_pk=workflow.pk
        )
        workflow.save(update_fields=["name"])
    _attach_section_approvers(
        team=team,
        workflow=workflow,
        sections=sections,
        config=sections_payload,
        actor=actor,
    )

    record_audit(
        actor=actor,
        action=AuditEntry.Action.CREATED if created else AuditEntry.Action.UPDATED,
        target_type=AuditEntry.TargetType.WORKFLOW,
        target_id=workflow.pk,
        target_summary=workflow.name,
        detail=changed_fields(
            before, _workflow_snapshot(workflow)
        )
        | {"team": team.name},
        reason=(
            f"Approval chain created with the {team.name} team."
            if created
            else f"Approval steps changed on the {team.name} team."
        ),
    )


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
        if locked.status == Team.Status.DRAFT:
            raise TeamActionError(
                "status",
                f'The {locked.name} team is still a draft, so there is nothing to '
                "retire. Delete it instead.",
            )
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


class WorkflowMemberError(ValueError):
    """Raised when a team-member or workflow-member write cannot be applied.

    ``field`` is the API field the error belongs to, matching
    :class:`TeamActionError` so viewsets can map both the same way.
    """

    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field
        self.message = message


def _member_display_name(user: User) -> str:
    return user.get_full_name() or user.username


def wide_approver_ids_for_team(team: Team | None) -> set[int]:
    """User ids who are wide approvers for ``team``.

    A wide approver staffs a chain without being appointed to its steps: the
    holder of a team-wide role on this team, the holder of a campus-wide role
    at the team's campus, or the holder of an institution-wide role. They are
    the deliberate exception to "one employee sits on one chain per team": a
    team building a second chain reuses its registrar or bursar, it does not
    move them off the first chain.
    """
    if team is None:
        return set()
    ids = set(
        RoleAssignment.objects.filter(
            role__is_institution_wide=True, user__is_active=True
        ).values_list("user_id", flat=True)
    )
    ids.update(
        TeamRoleAssignment.objects.filter(
            team=team, user__is_active=True
        ).values_list("user_id", flat=True)
    )
    if team.campus_id is not None:
        ids.update(
            CampusRoleAssignment.objects.filter(
                campus_id=team.campus_id, user__is_active=True
            ).values_list("user_id", flat=True)
        )
    return ids


def _employee_profile_for(user: User):
    profile = getattr(user, "employee_profile", None)
    if profile is None:
        profile = EmployeeProfile.objects.filter(user=user).select_related("user").first()
    return profile


def add_team_member(*, team: Team, user: User, actor) -> EmployeeProfile:
    """Place an active employee on a team as a normal member.

    Team membership is the eligibility pool for workflow membership and for
    approver eligibility: the employee's :attr:`EmployeeProfile.team` is the
    single record of which team's approval chain their leave routes through.

    Membership is scoped two ways. The team's **category** decides who may
    belong: an academic team takes academic employees, an administration team
    takes administration employees, and a mismatch is refused rather than
    allowed to sit on the roster until routing surprises someone. And a **wide
    approver** — institution-wide, team-wide on this team, or campus-wide at
    this team's campus — is not a normal member: they staff steps from the
    Approvers tab and are kept out of the roster, so being an approver never
    also quietly routes someone's leave as a member.

    Somebody already on a different team is refused rather than moved. Moving
    an employee off another team would leave that team with steps whose
    approvers are no longer members, and it would re-route their leave without
    HR choosing to — a deliberate edit, not a side effect of filling a roster.
    """
    if not user.is_active:
        raise WorkflowMemberError(
            "user",
            f"{_member_display_name(user)} is not an active user. Activate the "
            "account before adding them to a team.",
        )
    profile = _employee_profile_for(user)
    if profile is None:
        raise WorkflowMemberError(
            "user",
            f"{_member_display_name(user)} has no employee record, so there is "
            "nothing to place on a team. Complete their employee record first.",
        )
    if profile.category != team.category:
        raise WorkflowMemberError(
            "user",
            f'{_member_display_name(user)} is an '
            f'{profile.get_category_display()} employee, but "{team.name}" is an '
            f'{team.get_category_display()} team. An '
            f'{team.get_category_display()} team takes only '
            f'{team.get_category_display()} employees.',
        )
    if user.pk in wide_approver_ids_for_team(team):
        raise WorkflowMemberError(
            "user",
            f"{_member_display_name(user)} is a wide approver for this team, so "
            "they serve its steps from the Approvers tab rather than as a normal "
            "member. Remove the holding first if they should sit on the roster.",
        )
    with transaction.atomic():
        locked_profile = EmployeeProfile.objects.select_for_update().get(pk=profile.pk)
        if locked_profile.team_id == team.pk:
            return locked_profile
        if locked_profile.team_id is not None:
            current_name = (
                Team.objects.filter(pk=locked_profile.team_id)
                .values_list("name", flat=True)
                .first()
                or "another team"
            )
            raise WorkflowMemberError(
                "user",
                f'{_member_display_name(user)} is already on "{current_name}". '
                f'Remove them from that team first, or leave them on '
                f'"{current_name}" — one employee belongs to one team.',
            )
        before_team_id = locked_profile.team_id
        locked_profile.team = team
        locked_profile.save(update_fields=["team"])
        record_audit(
            actor=actor,
            action=AuditEntry.Action.UPDATED,
            target_type=AuditEntry.TargetType.EMPLOYEE,
            target_id=locked_profile.user_id,
            target_summary=_member_display_name(locked_profile.user),
            detail=changed_fields(
                {"team_id": before_team_id},
                {"team_id": team.pk, "team": team.name},
            ),
            reason=f"Added to the {team.name} team as a normal member.",
        )
    return locked_profile


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
