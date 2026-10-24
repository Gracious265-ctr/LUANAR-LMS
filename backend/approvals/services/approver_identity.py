"""Read-only resolution of who is responsible for, and may act on, a stage.

Display and queue-building helpers: the person who has taken up a pending stage,
the single user entitled to act now, and the query predicate that selects the
applications a user may act on. A delegation moves these answers, so the helpers
here read the *active* cover an approver is under — the Unit 21 routing boundary
that execution follows.

Authorisation itself stays in :func:`workflows.services.user_may_act`; nothing
here is a permission check.
"""

from django.db.models import Q
from django.utils import timezone

from approvals.models import ApplicationStageApprover, Delegation
from users.models import User
from chains.services import (
    _active_delegation_for_id,
    _current_stage,
    acting_approver_ids,
    eligible_approver_ids,
)


def active_delegation_for(approver_user) -> Delegation | None:
    """The delegation currently covering ``approver_user``, or ``None``.

    This is the Unit 21 routing boundary: pending approvals assigned to an
    approver move to the delegate while such a delegation is active, and fall
    back to the original approver when none is active (ended or cancelled).
    """
    return _active_delegation_for_id(approver_user.pk)


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
