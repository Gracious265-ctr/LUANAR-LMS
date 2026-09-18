"""Workflow and delegation logic shared by the API serializer, actions, and admin."""

from datetime import date
from dataclasses import dataclass

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from leave.services import date_ranges_overlap
from users.models import User

from .models import APPROVER_ROLE_CODES, Delegation, Workflow


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

    Returns a list of ``{"approver_role": role, "order": i + 1}`` payloads.
    Raises :class:`StageSequenceError` for an empty list, an unknown approver
    role, a repeated approver role, or a missing/non-positive/duplicate order.
    """
    items = list(stages)
    if not items:
        raise StageSequenceError(
            "stages", "At least one approval stage is required."
        )

    seen_roles: set[str] = set()
    seen_orders: set[int] = set()
    normalized: list[dict] = []

    for index, item in enumerate(items):
        role = item.get("approver_role") if isinstance(item, dict) else None
        if role not in APPROVER_ROLE_CODES:
            raise StageSequenceError(
                "approver_role", "Select a valid approver role.", index
            )
        if role in seen_roles:
            raise StageSequenceError(
                "stages", "An approver role can appear only once in a workflow.", index
            )
        seen_roles.add(role)

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

        normalized.append({"approver_role": role, "order": index + 1})

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


def _stage_role(stage) -> str | None:
    if isinstance(stage, dict):
        return stage.get("approver_role")
    return getattr(stage, "approver_role", None)


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
    """Stage roles with no active user holding that role."""
    missing: list[str] = []
    for stage in stages:
        role = _stage_role(stage)
        if not role or role in missing:
            continue
        if not User.objects.filter(role=role, is_active=True).exists():
            missing.append(role)
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
        labels = ", ".join(dict(User.Role.choices)[role] for role in missing)
        issues.append(
            ActivationIssue(None, f"No active user exists for: {labels}.")
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
    """True when ``user`` may act as an approver or delegate."""
    return bool(
        user
        and getattr(user, "is_active", False)
        and getattr(user, "role", None) in APPROVER_ROLE_CODES
    )


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
    today = timezone.localdate()
    return (
        Delegation.objects.filter(
            approver=approver_user,
            status=Delegation.Status.APPROVED,
            starts_on__lte=today,
        )
        .filter(Q(ends_on__isnull=True) | Q(ends_on__gte=today))
        .order_by("-starts_on")
        .first()
    )


def require_decision_reason(decision_reason: object) -> str:
    """Trim and require an HR decision reason; raises ``DelegationActionError``."""
    reason = (decision_reason or "").strip()
    if not reason:
        raise DelegationActionError(
            "decision_reason", "A decision reason is required."
        )
    return reason


def approve_delegation(delegation: Delegation, actor, data: dict) -> Delegation:
    """Approve a requested delegation with a concrete delegate and reason."""
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
    conflict = find_conflicting_delegation(
        delegation.pk, delegation.approver_id, delegation.starts_on, delegation.ends_on
    )
    if conflict is not None:
        raise DelegationActionError(
            "detail",
            f"This period overlaps an approved delegation for "
            f"{delegation.approver.get_full_name()} delegated to "
            f"{conflict.delegate.get_full_name()} "
            f"({conflict.starts_on.isoformat()} to "
            f"{(conflict.ends_on or 'open-ended')}).",
        )
    with transaction.atomic():
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
    return delegation


def reject_delegation(delegation: Delegation, actor, data: dict) -> Delegation:
    """Reject a requested delegation with a mandatory reason."""
    if delegation.status != Delegation.Status.REQUESTED:
        raise DelegationActionError(
            "detail", "Only a requested delegation can be rejected."
        )
    reason = require_decision_reason(data.get("decision_reason"))
    with transaction.atomic():
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
    return delegation


def cancel_delegation(delegation: Delegation, actor, data: dict) -> Delegation:
    """Cancel a scheduled or active approved delegation."""
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
    return delegation
