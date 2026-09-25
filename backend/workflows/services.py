"""Workflow and delegation logic shared by the API serializer, actions, and admin."""

from datetime import date
from dataclasses import dataclass

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from audit.models import AuditEntry
from audit.services import changed_fields, record_audit
from leave.models import LeaveApplication
from leave.services import date_ranges_overlap
from users.models import User

from .models import (
    APPROVER_ROLE_CODES,
    ApplicationStage,
    ApprovalDecision,
    Delegation,
    Reassignment,
    Workflow,
)


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


def _delegation_summary(delegation: Delegation) -> str:
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
        target_summary=_delegation_summary(delegation),
        detail=changed_fields(before, after),
        reason=reason,
    )


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
        delegation = Delegation.objects.select_for_update().get(pk=delegation.pk)
        if delegation.status != Delegation.Status.REQUESTED:
            raise DelegationActionError(
                "detail", "Only a requested delegation can be approved."
            )
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
        _record_delegation_audit(
            delegation,
            action=AuditEntry.Action.REJECTED,
            reason=reason,
            before={"status": Delegation.Status.REQUESTED, "delegate_id": None},
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
        _record_delegation_audit(
            delegation,
            action=AuditEntry.Action.CANCELLED,
            reason=reason,
            before={"status": Delegation.Status.APPROVED},
        )
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
    if to_approver.pk == application.employee_id:
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
    return reassignment


def assign_workflow(application):
    """Materialise the configured stage chain for ``application`` (Unit 16).

    Runs idempotently: if the current submission cycle already has stages, the
    existing live stage is returned unchanged. Otherwise the workflow provider's
    stage definitions are validated and bulk-created with exactly one ``pending``
    stage (the first), and ``application.current_stage`` is pointed at it.

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

        stages = []
        for index, definition in enumerate(definitions):
            if definition.approver_user_id is None:
                raise WorkflowAssignmentError(
                    [f"No active user for the {definition.role_label} stage."]
                )
            try:
                approver = User.objects.get(pk=definition.approver_user_id)
            except User.DoesNotExist:
                raise WorkflowAssignmentError(
                    [f"No active user for the {definition.role_label} stage."]
                )
            stages.append(
                ApplicationStage(
                    application=application,
                    submission_cycle=cycle,
                    stage_order=definition.order,
                    role=definition.role,
                    role_label=definition.role_label,
                    assigned_approver=approver,
                    status=(
                        ApplicationStage.Status.PENDING
                        if index == 0
                        else ApplicationStage.Status.WAITING
                    ),
                    is_final=index == len(definitions) - 1,
                )
            )

        ApplicationStage.objects.bulk_create(stages)
        first = stages[0]
        application.current_stage = first
        application.current_approver = first.assigned_approver
        application.save(update_fields=["current_stage", "current_approver", "updated_at"])
        return first


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
        if action == ApprovalDecision.Action.APPROVE:
            stage.status = ApplicationStage.Status.APPROVED
            if stage.is_final:
                app.status = LeaveApplication.Status.APPROVED
            else:
                next_stage = (
                    ApplicationStage.objects.select_for_update()
                    .filter(
                        application=app,
                        submission_cycle=app.workflow_chain_cycle,
                        stage_order=stage.stage_order + 1,
                    )
                    .first()
                )
                if next_stage is None:
                    raise ApprovalValidationError({"action": "Workflow chain is incomplete."})
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
        app.save(
            update_fields=["status", "current_stage", "current_approver", "updated_at"]
        )

        if after_status == LeaveApplication.Status.APPROVED:
            # Unit 25 (D4): the annual-balance deduction is transactional
            # business state, so it is written inside this transaction and a
            # failure rolls the approval back. The approved-document half stays
            # deferred to Unit 23b; only ``record_deduction`` is wired here.
            from leave.services.finalise import record_deduction

            record_deduction(app)

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
