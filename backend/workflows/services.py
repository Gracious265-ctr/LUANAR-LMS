"""Workflow and delegation logic shared by the API serializer, actions, and admin."""

from datetime import date
from dataclasses import dataclass

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.text import slugify

from audit.models import AuditEntry
from audit.services import changed_fields, record_audit
from leave.models import LeaveApplication
from leave.services import date_ranges_overlap
from users.models import User

from .models import (
    ApplicationStage,
    ApplicationStageApprover,
    Campus,
    ApprovalDecision,
    ApproverRole,
    Delegation,
    Reassignment,
    RoleAssignment,
    Section,
    SectionMember,
    Team,
    Workflow,
)
from .policies import is_self_application


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

    A role **may** repeat across sections. That is the point of sections: one
    person can sit at several points in a chain, and two steps can be performed
    by the same position. Only ``order`` has to be unique.

    Returns a list of ``{"name", "approver_role", "order"}``. Raises
    :class:`StageSequenceError` for an empty list, an unknown or inactive
    approver role, a missing/blank name, or a missing/non-positive/duplicate
    order.
    """
    items = list(sections)
    if not items:
        raise StageSequenceError(
            "sections", "At least one approval section is required."
        )

    seen_orders: set[int] = set()
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


def _value_matches(left: str, right: str) -> bool:
    return left == right or not left or not right


def scopes_overlap(a: tuple[str, str], b: tuple[str, str]) -> bool:
    """Two (category, department) scopes overlap when each dimension matches.

    A blank value on either side matches anything (any category / any
    department).
    """
    a_category, a_department = a
    b_category, b_department = b
    return _value_matches(a_category, b_category) and _value_matches(
        a_department, b_department
    )


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


def find_conflicting_workflow(
    workflow_pk: int | None, scope: tuple[str, str]
) -> Workflow | None:
    """The first other workflow applying now or in the future with an overlap.

    A workflow is "applying" when it has an ``effective_from`` date and is
    active. Drafts and inactive workflows never conflict.
    """
    candidates = Workflow.objects.filter(
        effective_from__isnull=False, is_active=True
    )
    if workflow_pk is not None:
        candidates = candidates.exclude(pk=workflow_pk)
    for candidate in candidates:
        if scopes_overlap(scope, candidate.scope):
            return candidate
    return None


def validate_workflow_for_activation(
    workflow_pk: int | None,
    scope: tuple[str, str],
    stages,
) -> list[ActivationIssue]:
    """Authoritative validation for activating or scheduling a workflow."""
    issues: list[ActivationIssue] = []

    missing = missing_approver_roles(stages)
    if missing:
        issues.append(
            ActivationIssue(
                None,
                "These approver roles are deactivated and cannot be used: "
                f"{', '.join(missing)}. Reactivate them in Roles, or replace them.",
            )
        )

    conflict = find_conflicting_workflow(workflow_pk, scope)
    if conflict is not None:
        issues.append(
            ActivationIssue(
                "effective_from",
                f'Activating this workflow conflicts with "{conflict.name}" '
                f"(active since {conflict.effective_from.isoformat()}).",
            )
        )

    return issues


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
    section whose :class:`~workflows.models.ApproverRole` is active, or when they
    hold an institution-wide role:

    * a :class:`~workflows.models.SectionMember` row, or
    * a :class:`~workflows.models.RoleAssignment` row, for an
      institution-wide role.

    Deactivating a role therefore retires the approver status it conferred, and
    ``User.role`` is irrelevant: it records system access, not a place in an
    approval chain.
    """
    if not user or not getattr(user, "is_active", False):
        return False
    user_id = user.pk if hasattr(user, "pk") else user
    if user_id is None:
        return False
    if SectionMember.objects.filter(
        user_id=user_id, section__approver_role__is_active=True
    ).exists():
        return True
    return RoleAssignment.objects.filter(
        user_id=user_id, role__is_active=True
    ).exists()


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
        SectionMember.objects.filter(
            user_id=user_id, section__approver_role__is_active=True
        ).values_list("section__approver_role__code", flat=True)
    )
    codes.update(
        RoleAssignment.objects.filter(
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
        SectionMember.objects.filter(
            user_id=user_id, section__approver_role__is_active=True
        ).values_list("section__approver_role__label", flat=True)
    )
    labels.update(
        RoleAssignment.objects.filter(
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
    An employee who is also an approver is removed from the eligibility snapshot
    of every section they belong to, by the provider, rather than by bypassing
    stages here. So a section the applicant belongs to is still decided — by its
    other members — and a section whose only member is the applicant cannot be
    routed at all, so the submission is refused there (invariants 12.3, 12.7).
    The old "start after the applicant's last stage, never travelling backwards"
    rule is gone: with a set of approvers per section there is nothing to skip.

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
            if not definition.approver_user_ids
        ]
        if unstaffed:
            raise WorkflowAssignmentError(unstaffed)

        # Every definition is guaranteed to carry at least one eligible user:
        # the provider refuses an unsatisfiable section rather than returning a
        # gap, and it has already removed the applicant. So there is no longer a
        # "which stages does the applicant hold" question to answer here — the
        # chain always starts at section one, and self-approval is prevented by
        # the snapshot rather than by skipping stages.
        active_index = 0
        last_index = len(definitions) - 1
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
                status=_initial_stage_status(index, active_index),
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

        first = stages[active_index]
        application.current_stage = first
        application.current_approver = None
        application.save(update_fields=["current_stage", "current_approver", "updated_at"])
        return first


def _initial_stage_status(index: int, active_index: int) -> str:
    """The status a freshly materialised stage starts in."""
    if index < active_index:
        return ApplicationStage.Status.SKIPPED
    if index == active_index:
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


class ApprovalValidationError(ValueError):
    """Invalid action or comment; carries a dict of field errors."""

    def __init__(self, errors: dict):
        self.errors = errors
        super().__init__(str(errors))


def _next_activatable_stage(application, decided_stage):
    """The next stage to activate after ``decided_stage`` was approved.

    The chain is contiguous and nothing is ever bypassed, so this is simply the
    next stage by order. It is still looked up under a row lock and its
    eligibility re-checked, because a stage with no one able to act is a chain
    that cannot finish and must be reported rather than activated as a dead end.

    Raises ``ApprovalValidationError`` when the chain simply ends (a pre-existing
    malformed chain) and :class:`SelfApprovalBlockedError` when the next stage has
    no eligible approver — which can only happen on a chain materialised before
    sections, where the applicant used to be skipped forward over.
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

    candidate = remaining[0]
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


def create_approver_role(*, actor, data: dict) -> ApproverRole:
    """Create one approver role and audit it."""
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
    edits ``label``, ``description``, ``history_scope``,
    ``handles_cancellation``, and ``is_institution_wide`` freely.

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
    """Assign an institution-wide role to a user and audit it."""
    with transaction.atomic():
        role.full_clean(exclude=["code", "label"])
        if not role.is_active:
            raise RoleActionError(
                "role",
                f'"{role.label}" is deactivated. Reactivate it in Roles, or pick '
                "an active role.",
            )
        if not role.is_institution_wide:
            raise RoleActionError(
                "role",
                f'"{role.label}" is a team role, not an institution-wide role. '
                "Add this person to the team that uses it instead, or mark the "
                "role institution-wide first.",
            )
        if not user.is_active:
            raise RoleActionError(
                "user",
                f"{user.get_full_name() or user.username} is not an active user. "
                "Activate the account before assigning a role.",
            )
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


class TeamActionError(ValueError):
    """Raised when a team or team-member write cannot be applied."""

    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field
        self.message = message


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


def create_team(*, actor, data: dict) -> Team:
    """Create a team and audit it."""
    with transaction.atomic():
        data = dict(data)
        data.setdefault("code", _unique_team_code(data.get("name", "")))
        team = Team.objects.create(**data)
        record_audit(
            actor=actor,
            action=AuditEntry.Action.CREATED,
            target_type=AuditEntry.TargetType.TEAM,
            target_id=team.pk,
            target_summary=team.name,
            detail={"before": None, "after": _team_snapshot(team)},
        )
    return team


def update_team(*, team: Team, actor, data: dict) -> Team:
    """Update a team's editable fields and audit the change."""
    with transaction.atomic():
        team = Team.objects.select_for_update().get(pk=team.pk)
        before = _team_snapshot(team)
        for field, value in data.items():
            setattr(team, field, value)
        team.save()
        record_audit(
            actor=actor,
            action=AuditEntry.Action.UPDATED,
            target_type=AuditEntry.TargetType.TEAM,
            target_id=team.pk,
            target_summary=team.name,
            detail=changed_fields(before, _team_snapshot(team)),
        )
    return team


def _team_snapshot(team: Team) -> dict:
    return {
        "name": team.name,
        "code": team.code,
        "description": team.description,
        "campus_id": team.campus_id,
        "campus": team.campus.name if team.campus_id else "",
        "workflow_id": team.workflow_id,
        "is_active": team.is_active,
    }


def add_section_member(
    *, section: Section, user: User, actor
) -> SectionMember:
    """Add one person to a section and audit it.

    A section may hold any number of people and the same person may belong to
    several sections, so the only uniqueness rule left is "not twice in the same
    section". Unlike the old team membership there is deliberately **no**
    one-holder-per-role rule and no role argument: the role belongs to the
    section, and more than one person sharing it is the whole point.
    """
    with transaction.atomic():
        if not section.is_active:
            raise TeamActionError(
                "section",
                f'The "{section.name}" section is inactive. Activate it before '
                "adding members.",
            )
        if not user.is_active:
            raise TeamActionError(
                "user",
                f"{user.get_full_name() or user.username} is not an active user. "
                "Activate the account before adding them to a section.",
            )
        if not section.approver_role.is_active:
            raise TeamActionError(
                "section",
                f'"{section.approver_role.label}" is deactivated. Reactivate it in '
                "Roles before adding members to this section.",
            )
        if SectionMember.objects.filter(section=section, user=user).exists():
            raise TeamActionError(
                "user",
                f"{user.get_full_name() or user.username} is already a member of "
                f'the "{section.name}" section.',
            )
        membership = SectionMember(section=section, user=user)
        membership.full_clean()
        membership.save()
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
                    "member_user_id": user.pk,
                    "member": user.get_full_name() or user.username,
                    "section": section.name,
                    "role": section.approver_role.label,
                },
            ),
            reason=(
                f"{user.get_full_name() or user.username} added to the "
                f"{section.name} section as {section.approver_role.label}."
            ),
        )
    return membership


def remove_section_member(*, membership: SectionMember, actor) -> SectionMember:
    """Remove one section membership and audit it."""
    with transaction.atomic():
        section = membership.section
        user = membership.user
        role = section.approver_role
        detail = changed_fields(
            {
                "member_user_id": user.pk,
                "member": user.get_full_name() or user.username,
                "section": section.name,
                "role": role.label,
            },
            {},
        )
        membership.delete()
        record_audit(
            actor=actor,
            action=AuditEntry.Action.CANCELLED,
            target_type=AuditEntry.TargetType.WORKFLOW,
            target_id=section.workflow_id,
            target_summary=f"{section.workflow.name} / {section.name}",
            detail=detail,
            reason=(
                f"{user.get_full_name() or user.username} removed from the "
                f"{section.name} section."
            ),
        )
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
