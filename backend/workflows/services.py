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
    Campus,
    ApprovalDecision,
    ApproverRole,
    Delegation,
    Reassignment,
    RoleAssignment,
    Team,
    TeamMember,
    Workflow,
    WorkflowStage,
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


def normalize_stage_sequence(stages: list[dict]) -> list[dict]:
    """Validate and renumber a workflow's stage list in submission order.

    A stage names its approver role by ``code`` (``"hod"``) — that is the wire
    contract — or by primary key for convenience. Either way the value is
    resolved against :class:`~workflows.models.ApproverRole`, and the normalized
    payload carries the role's *code* so the sequence round-trips through the API
    without leaking database ids into saved forms.

    Returns a list of ``{"approver_role": code, "order": i + 1}``. Raises
    :class:`StageSequenceError` for an empty list, an unknown or inactive
    approver role, a repeated approver role, or a missing/non-positive/duplicate
    order.
    """
    items = list(stages)
    if not items:
        raise StageSequenceError(
            "stages", "At least one approval stage is required."
        )

    seen_roles: set[int] = set()
    seen_orders: set[int] = set()
    normalized: list[dict] = []

    for index, item in enumerate(items):
        role = _stage_role(item)
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
        if role.pk in seen_roles:
            raise StageSequenceError(
                "stages", "An approver role can appear only once in a workflow.", index
            )
        seen_roles.add(role.pk)

        order = item.get("order")
        if not isinstance(order, int) or isinstance(order, bool) or order < 1:
            raise StageSequenceError(
                "order", "Stage order must be a positive whole number.", index
            )
        if order in seen_orders:
            raise StageSequenceError(
                "order", "Stage order numbers must be unique within a workflow.", index
            )
        seen_orders.add(order)

        normalized.append({"approver_role": role.code, "order": index + 1})

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


def _stage_role(stage) -> int | str | ApproverRole | None:
    """The approver role a stage payload names, whether dict or model.

    Returns an :class:`ApproverRole`, its primary key, or its code, as named.
    ``None`` means the payload named nothing usable. The ambiguity is harmless
    because :func:`normalize_stage_sequence` only ever needs to resolve the
    value against a role, and the choice of code-vs-pk is an input detail.
    """
    if isinstance(stage, dict):
        value = stage.get("approver_role")
    elif isinstance(getattr(stage, "approver_role", None), ApproverRole):
        return stage.approver_role
    else:
        value = getattr(stage, "approver_role_id", None)
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


def missing_approver_roles(stages) -> list[str]:
    """Labels of stage roles that cannot currently be used, in stage order.

    Activation is a configuration check, so the only thing it can know about
    holder availability without an applicant is whether the *role itself* is
    usable. A role that has been deactivated is reported; whether a given team
    actually has somebody holding each active role is resolved per applicant at
    submission time (invariant 12.7 still blocks that submission).
    """
    missing: list[str] = []
    seen: set[int] = set()
    for stage in stages:
        role = _stage_role(stage)
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
    role-name check. A person is an approver when they hold an active
    :class:`~workflows.models.ApproverRole` in at least one of the two places a
    role can be held:

    * a :class:`~workflows.models.TeamMember` row on a team, or
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
    if TeamMember.objects.filter(
        user_id=user_id, role__is_active=True
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
        TeamMember.objects.filter(user_id=user_id, role__is_active=True).values_list(
            "role__code", flat=True
        )
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
        TeamMember.objects.filter(user_id=user_id, role__is_active=True).values_list(
            "role__label", flat=True
        )
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


def responsible_approver_id(application) -> int | None:
    """The configured approver who must act now (Unit 21 spine, D2).

    ``LeaveApplication.current_approver`` is authoritative; the current stage's
    ``assigned_approver`` is a defensive fallback for rows where the spine has
    not been materialised.
    """
    if application.current_approver_id is not None:
        return application.current_approver_id
    if application.current_stage_id is None:
        return None
    return (
        ApplicationStage.objects.filter(pk=application.current_stage_id)
        .values_list("assigned_approver_id", flat=True)
        .first()
    )


def acting_approver_id(application) -> int | None:
    """The user entitled to act on the pending application right now (D3).

    The responsible approver acts unless an active delegation names a delegate,
    in which case the delegate acts. Single-level only: a delegate's own active
    delegation is never cascaded.
    """
    responsible_id = responsible_approver_id(application)
    if responsible_id is None:
        return None
    delegation = _active_delegation_for_id(responsible_id)
    if delegation is not None and delegation.delegate_id is not None:
        return delegation.delegate_id
    return responsible_id


def acting_approver_predicate(user) -> Q:
    """Query predicate selecting applications the user must act on now.

    The user acts on applications currently held by them — except those they
    have delegated away while an active delegation covers them — and on the
    applications of every approver whose active delegation currently names the
    user as delegate. Empty expected when ``user`` is not an approver.
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
    own = Q(current_approver=user) & ~Q(
        current_approver__in=list(delegated_approver_ids)
    )
    acting = Q(current_approver__in=list(received_approver_ids))
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


def applicant_stage_positions(application: LeaveApplication, definitions) -> list[int]:
    """The positions in ``definitions`` whose approver is the applicant.

    An employee may hold more than one approver role, so this is a list: the
    application's path has to clear the applicant's *last* one.
    """
    return [
        index
        for index, definition in enumerate(definitions)
        if is_self_approver(definition.approver_user_id, application)
    ]


def select_activatable_stage_index(application: LeaveApplication, definitions) -> int:
    """Index of the first stage in ``definitions`` that may be activated.

    An employee who is also an approver must never be the approver of record
    for their own leave. A role resolves to exactly one approver (the lowest-id
    active user holding it), so a self-match cannot be replaced by another
    candidate within the stage.

    The applicant's stages are removed from the path, and so is everything before
    them: the application starts at the first stage *after* the applicant's last
    one and never travels backwards down the queue. Given
    ``supervisor -> HOD -> Registrar``:

    * a supervisor's application starts at the HOD;
    * the HOD's own application starts at the Registrar, never at the
      Supervisor, because the Supervisor sits below the applicant;
    * a Registrar's application has no stage after them, so it is not routed at
      all (:class:`SelfApprovalBlockedError`).

    Bypassed stages are materialised as ``skipped`` so the chain stays contiguous
    and the snapshot keeps recording the workflow as HR configured it
    (invariant 12.5).

    Returns the index of the first activatable stage.
    Raises :class:`SelfApprovalBlockedError` when the applicant holds the last
    stage, so the caller refuses the operation rather than routing an application
    that nobody can sign off.
    """
    if not definitions:
        return 0
    positions = applicant_stage_positions(application, definitions)
    if not positions:
        return 0
    start = positions[-1] + 1
    if start >= len(definitions):
        held = ", ".join(
            definitions[index].role_label for index in positions
        )
        if len(positions) == len(definitions):
            raise SelfApprovalBlockedError(
                [
                    "This approval workflow resolves every stage to the applicant "
                    f"themself ({held}). An approver cannot approve their own "
                    "leave application, and a mandatory stage cannot be skipped. "
                    "Human Resources must appoint another active holder of one of "
                    "these roles, or correct the workflow configuration."
                ]
            )
        raise SelfApprovalBlockedError(
            [
                f"The applicant is the approver for the {held} stage, which is "
                "the last stage of this workflow, so there is no later approver "
                "to take the application. An approver cannot approve their own "
                "leave application, and a mandatory stage cannot be skipped. "
                "Human Resources must appoint the applicant to a different "
                "approver role, or change the workflow's final stage, before this "
                "application can be submitted."
            ]
        )
    return start


def record_skipped_stages_audit(
    application: LeaveApplication,
    skipped_stages,
    activated_stage=None,
    actor=None,
) -> None:
    """Audit the stages bypassed because they would resolve to the applicant.

    ``actor`` is ``None`` when the skip happens automatically while routing, so
    the entry identifies the acting user as the system rather than a person; it
    is the deciding approver when the chain advances past a match.
    """
    if not skipped_stages:
        return
    skipped = list(skipped_stages)
    applicant_orders = {
        stage.stage_order
        for stage in skipped
        if is_self_approver(stage.assigned_approver_id, application)
    }
    applicant_labels = ", ".join(
        stage.role_label
        for stage in skipped
        if stage.stage_order in applicant_orders
    )
    routed_to = (
        activated_stage.role_label if activated_stage is not None else None
    )
    record_audit(
        actor=actor,
        action=AuditEntry.Action.STAGE_SKIPPED,
        target_type=AuditEntry.TargetType.APPLICATION,
        target_id=application.pk,
        target_summary=application.reference_number,
        detail={
            "reason": "applicant_is_the_approver",
            "applicant_stage_orders": sorted(applicant_orders),
            "skipped_stages": [
                {
                    "order": stage.stage_order,
                    "role": stage.role,
                    "role_label": stage.role_label,
                    "assigned_approver_id": stage.assigned_approver_id,
                    "skip_reason": (
                        "applicant_is_approver"
                        if stage.stage_order in applicant_orders
                        else "before_applicant_stage"
                    ),
                }
                for stage in skipped
            ],
            "activated_stage_order": (
                activated_stage.stage_order if activated_stage is not None else None
            ),
            "activated_role_label": routed_to,
        },
        reason=(
            f"The applicant is the approver for the {applicant_labels} stage, so "
            "the application starts after it"
            + (f" at the {routed_to} stage." if routed_to else ".")
            + " Stages at or below the applicant are bypassed."
        ),
    )


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
    reason is supplied. On success, records a :class:`Reassignment` history row
    and atomically moves ``LeaveApplication.current_approver``.
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
    """Materialise the configured stage chain for ``application`` (Unit 16).

    Runs idempotently: if the current submission cycle already has stages, the
    existing live stage is returned unchanged. Otherwise the workflow provider's
    stage definitions are validated and bulk-created with exactly one ``pending``
    stage, and ``application.current_stage`` is pointed at it.

    An employee who is also an approver is never assigned their own
    application: any leading stage resolving to the applicant is materialised
    as ``skipped`` and the first stage with a different approver is activated
    instead (see :func:`select_activatable_stage_index`). When no such stage
    exists the submission is refused, because a mandatory stage cannot be
    skipped (invariant 12.3).

    Raises :class:`WorkflowAssignmentError` (responsibility of the caller to map
    to a submisable ``ValidationFailedError``-style failure) when the provider
    yields no/ill-formed stages or a stage cannot be resolved to an active user.
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
            raise WorkflowAssignmentError(["No workflow stages configured."])
        orders = [definition.order for definition in definitions]
        if sorted(orders) != list(range(1, len(definitions) + 1)):
            raise WorkflowAssignmentError(["Workflow stages must be ordered 1..N."])

        approvers = []
        for definition in definitions:
            if definition.approver_user_id is None:
                raise WorkflowAssignmentError(
                    [f"No active user for the {definition.role_label} stage."]
                )
            try:
                approvers.append(User.objects.get(pk=definition.approver_user_id))
            except User.DoesNotExist:
                raise WorkflowAssignmentError(
                    [f"No active user for the {definition.role_label} stage."]
                )

        try:
            active_index = select_activatable_stage_index(application, definitions)
        except SelfApprovalBlockedError as exc:
            raise WorkflowAssignmentError(exc.messages)

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
                assigned_approver=approver,
                status=_initial_stage_status(index, active_index),
                is_final=index == last_index,
            )
            for index, (definition, approver) in enumerate(
                zip(definitions, approvers)
            )
        ]

        ApplicationStage.objects.bulk_create(stages)
        record_skipped_stages_audit(
            application, stages[:active_index], activated_stage=stages[active_index]
        )
        first = stages[active_index]
        application.current_stage = first
        application.current_approver = first.assigned_approver
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
    """The stage to activate after ``decided_stage`` was approved.

    Walks forward through the remaining chain and returns
    ``(next_stage, skipped_stages)``. A stage whose approver is the applicant is
    bypassed and returned in ``skipped_stages`` so the caller can mark and audit
    it; the walk continues in case a later stage has a valid approver.

    Raises ``ApprovalValidationError`` when the chain simply ends (a pre-existing
    malformed chain) and :class:`SelfApprovalBlockedError` when stages remain but
    every one of them resolves to the applicant — there is then nobody who may
    act, and a mandatory stage cannot be dropped (invariant 12.3).
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

    skipped = []
    for candidate in remaining:
        if (
            candidate.status == ApplicationStage.Status.SKIPPED
            or is_self_approver(candidate.assigned_approver_id, application)
        ):
            skipped.append(candidate)
            continue
        return candidate, skipped

    raise SelfApprovalBlockedError(
        [
            "This application cannot be advanced: every remaining approval "
            "stage ("
            + ", ".join(stage.role_label for stage in remaining)
            + ") resolves to the applicant themself, so no approver is left to "
            "sign it off. An approver cannot approve their own leave "
            "application, and a mandatory stage cannot be skipped. Human "
            "Resources must appoint the applicant to a different approver role, "
            "or change the workflow, before this application can be decided. "
            "Reassigning the current approver will not help, because the "
            "blocked stage is a later one that reassignment does not reach."
        ]
    )


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
        skipped_stages = []
        if action == ApprovalDecision.Action.APPROVE:
            stage.status = ApplicationStage.Status.APPROVED
            if stage.is_final:
                app.status = LeaveApplication.Status.APPROVED
            else:
                next_stage, skipped_stages = _next_activatable_stage(app, stage)
                next_stage.status = ApplicationStage.Status.PENDING
        elif action == ApprovalDecision.Action.REJECT:
            stage.status = ApplicationStage.Status.REJECTED
            app.status = LeaveApplication.Status.REJECTED
        else:
            stage.status = ApplicationStage.Status.CORRECTION_REQUESTED
            app.status = LeaveApplication.Status.CORRECTION_REQUIRED

        # Persist the decided stage first so a single ``pending`` stage always
        # exists at any one moment (enforced by the partial unique constraint).
        stage.save(update_fields=["status", "decision_version", "updated_at"])
        if skipped_stages:
            for skipped in skipped_stages:
                skipped.status = ApplicationStage.Status.SKIPPED
            ApplicationStage.objects.bulk_update(skipped_stages, ["status"])
            record_skipped_stages_audit(
                app, skipped_stages, activated_stage=next_stage, actor=actor
            )
        if next_stage is not None:
            next_stage.save(update_fields=["status", "decision_version", "updated_at"])
            app.current_stage = next_stage
            # Unit 21 (D2): the spine follows the stage — the next approver is
            # the configured approver of the freshly-activated stage.
            app.current_approver = next_stage.assigned_approver

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

    stage_counts = (
        WorkflowStage.objects.filter(
            approver_role_id__in=role_ids, workflow__is_active=True
        )
        .values("approver_role_id", "workflow_id", "workflow__name")
        .annotate(count=Count("id"))
        .order_by("workflow__name")
    )
    for row in stage_counts:
        count = row["count"]
        noun = "stage" if count == 1 else "stages"
        usage[row["approver_role_id"]].append(
            f"the '{row['workflow__name']}' workflow ({count} {noun})"
        )

    member_counts = (
        TeamMember.objects.filter(role_id__in=role_ids, team__is_active=True)
        .values("role_id", "team_id", "team__name")
        .annotate(count=Count("id"))
        .order_by("team__name")
    )
    for row in member_counts:
        count = row["count"]
        noun = "member" if count == 1 else "members"
        usage[row["role_id"]].append(
            f"the '{row['team__name']}' team ({count} {noun})"
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


def add_team_member(*, team: Team, user: User, role: ApproverRole, actor) -> TeamMember:
    """Add one person to a team in one role, refusing unusable configurations."""
    with transaction.atomic():
        if team.workflow_id is None:
            raise TeamActionError(
                "team",
                f'The "{team.name}" team has no workflow yet. Set one on the team '
                "before adding members.",
            )
        if not team.is_active:
            raise TeamActionError(
                "team",
                f'The "{team.name}" team is inactive. Activate it before adding '
                "members.",
            )
        if not user.is_active:
            raise TeamActionError(
                "user",
                f"{user.get_full_name() or user.username} is not an active user. "
                "Activate the account before adding them to a team.",
            )
        if not role.is_active:
            raise TeamActionError(
                "role",
                f'"{role.label}" is deactivated. Reactivate it in Roles, or pick '
                "an active role.",
            )
        if TeamMember.objects.filter(team=team, user=user).exists():
            raise TeamActionError(
                "user",
                f"{user.get_full_name() or user.username} is already a member of "
                f'the "{team.name}" team. Remove them from their current role '
                "first.",
            )
        if TeamMember.objects.filter(team=team, role=role).exists():
            holder = TeamMember.objects.filter(team=team, role=role).first()
            name = holder.user.get_full_name() or holder.user.username
            raise TeamActionError(
                "role",
                f'"{role.label}" is already held on the "{team.name}" team by '
                f"{name}. A team has one member per role; create a second role if "
                "two people are needed.",
            )
        membership = TeamMember(team=team, user=user, role=role)
        # Full clean last: it catches the fields the checks above cannot (a role
        # the team's workflow does not use, say), and by now the uniqueness rules
        # have already produced a message that names the blocker.
        membership.full_clean()
        membership.save()
        record_audit(
            actor=actor,
            action=AuditEntry.Action.CREATED,
            target_type=AuditEntry.TargetType.TEAM,
            target_id=team.pk,
            target_summary=team.name,
            detail=changed_fields(
                {},
                {
                    "member_user_id": user.pk,
                    "member": user.get_full_name() or user.username,
                    "member_role": role.label,
                },
            ),
            reason=f"{user.get_full_name() or user.username} added as {role.label}.",
        )
    return membership


def remove_team_member(*, membership: TeamMember, actor) -> TeamMember:
    """Remove one team membership and audit it."""
    with transaction.atomic():
        team = membership.team
        user = membership.user
        role = membership.role
        detail = changed_fields(
            {
                "member_user_id": user.pk,
                "member": user.get_full_name() or user.username,
                "member_role": role.label,
            },
            {},
        )
        membership.delete()
        record_audit(
            actor=actor,
            action=AuditEntry.Action.CANCELLED,
            target_type=AuditEntry.TargetType.TEAM,
            target_id=team.pk,
            target_summary=team.name,
            detail=detail,
            reason=f"{user.get_full_name() or user.username} removed from {role.label}.",
        )
    return membership


def team_stage_roles(team: Team) -> list[ApproverRole]:
    """The roles the team's workflow actually asks for, in stage order.

    The role picker is driven by this rather than by the full role list, so HR
    can only assign a member a role that will route applications.
    """
    if team.workflow_id is None:
        return []
    role_ids = list(
        team.workflow.stages.order_by("order")
        .values_list("approver_role", flat=True)
        .distinct()
    )
    if not role_ids:
        return []
    # Re-fetch as rows (callers need ``code``/``label``, not ids) while keeping
    # the stage order the ``values_list`` above established.
    by_id = {
        role.pk: role
        for role in ApproverRole.objects.filter(pk__in=role_ids).select_related()
    }
    return [by_id[role_id] for role_id in role_ids if role_id in by_id]
