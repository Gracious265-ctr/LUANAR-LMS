"""Delegation lifecycle: requests, decisions, and the cover they provide.

A delegation hands one approver's pending stages to a named delegate for a
period. This module owns resolving a valid delegate, detecting overlapping
periods, and the approve/reject/cancel decisions HR takes on a request — all
serialised through an approver-scoped lock so two decisions for the same approver
cannot interleave.

Reading *which* delegation currently covers an approver (the routing boundary
that execution consults) lives beside the identity helpers in
:mod:`approvals.services.approver_identity`.
"""

from datetime import date

from django.db import transaction
from django.utils import timezone

from approvals.models import Delegation
from audit.models import AuditEntry
from audit.services import changed_fields, record_audit
from leave.services import date_ranges_overlap
from roles.services import is_approver_user
from users.models import User


class DelegationActionError(ValueError):
    """Raised when a delegation decision cannot be applied.

    ``field`` is the API field the error belongs to (``"decision_reason"``,
    ``"delegate"``, or ``"detail"``).
    """

    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field
        self.message = message


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
