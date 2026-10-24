"""Workflow execution seam: who may act on a chain right now.

The read-only side of a chain that *execution* consults — resolving a pending
stage, the eligibility snapshot, and the delegation that currently covers an
approver. ``approvals.services`` and ``leave`` depend on these few functions and
nothing else in this package, so this module is the narrow interface across the
configuration/execution seam.
"""

from django.db.models import Q
from django.utils import timezone

from approvals.models import ApplicationStage, Delegation


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
