"""Approvals execution, delegation, reassignment and access helpers.

This module centralises approval-chain execution (decisions, transitions, skips),
delegation lifecycle and reassignment, plus the access/badge helpers used by the
launcher and approvals desk.
"""

from datetime import date

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from audit.models import AuditEntry
from audit.services import changed_fields, record_audit
from leave.models import LeaveApplication
from leave.services import date_ranges_overlap
from users.models import User

from approvals.models import (
    ApplicationStage,
    ApplicationStageApprover,
    ApprovalDecision,
    Delegation,
    Reassignment,
)
from workflows.policies import is_self_application
from organisation.services import is_approver_user
from workflows.services import (
    WorkflowAssignmentError,
    _active_delegation_for_id,
    _current_stage,
    acting_approver_ids,
    eligible_approver_ids,
    user_may_act,
)


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
    from workflows.providers import WorkflowConfigError, get_workflow_provider

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
    from workflows.events import (
        APPLICATION_FINALISED,
        DECISION_RECORDED,
        ApprovalEvent,
        emit_approval_event,
    )
    if action not in ApprovalDecision.Action.values:
        raise ApprovalValidationError({"action": "Must be approve or reject."})

    comment = (comment or "").strip()
    if len(comment) > 1000:
        raise ApprovalValidationError({"comment": "Must be at most 1000 characters."})
    if action == ApprovalDecision.Action.REJECT and not comment:
        raise ApprovalValidationError(
            {"comment": "A comment is required when rejecting."}
        )

    from workflows.policies import get_decision_authority as _authority

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
    }
    return mapping[action]



def can_access_approvals(user) -> bool:
    """Whether ``user`` may use the approvals desk.

    Approver status is :func:`is_approver_user`; HR is admitted explicitly so it
    keeps the oversight access it has always had without needing a role assignment.
    """
    if not (
        user
        and getattr(user, "is_authenticated", False)
        and getattr(user, "is_active", False)
    ):
        return False
    return is_approver_user(user) or getattr(user, "role", None) == "hr"


def pending_stage_count_for(user) -> int:
    """How many submitted applications are currently waiting on ``user``.

    The same query the approvals desk uses for its pending list, so the launcher
    badge and the queue can never disagree.
    """
    from leave.models import LeaveApplication

    if not can_access_approvals(user) or not is_approver_user(user):
        return 0
    return (
        LeaveApplication.objects.filter(status=LeaveApplication.Status.SUBMITTED)
        .filter(acting_approver_predicate(user))
        .count()
    )
