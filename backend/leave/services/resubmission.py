<<<<<<< HEAD
"""Resubmission services (Unit 17, sections 2-5).

Implements the employee-side lifecycle for a rejected / correction-required
application: read the edit context, save changes in place, manage documents
(never physically deleting files), and resubmit under the same reference number
back to the same stage and approver.

All services run in one transaction, resolve the application through the owner
check ``application.employee_id == actor.id`` (anything else -> 404), and take
the actor from the authenticated user only. No employee or approver id is ever
read from the request.
"""

from datetime import timedelta

from audit.services import record_event
from django.db import transaction
from django.utils import timezone

from ..diff import compute_changes
from ..models import ApplicationRevision, LeaveApplication, LeaveType, SupportingDocument
from . import documents
from .submission import _acquire_employee_lock, build_rules_snapshot

MAX_REASON_LENGTH = 2000

EDITABLE_STATUSES = (
    LeaveApplication.Status.REJECTED,
    LeaveApplication.Status.CORRECTION_REQUIRED,
)

# The current stage must be in the matching state for a given application status
# before a resubmission is allowed (section 2).
STAGE_STATUS_BY_APPLICATION_STATUS = {
    LeaveApplication.Status.REJECTED: "rejected",
    LeaveApplication.Status.CORRECTION_REQUIRED: "correction_requested",
}

# Ownership/not-found errors come from the Unit 19 document service; re-exported
# here so the resubmission views keep catching one error class per case.
ApplicationNotFoundError = documents.ApplicationNotFoundError
DocumentNotFoundError = documents.DocumentNotFoundError


class NotEditableError(Exception):
    """The application status does not allow editing."""


class NotResubmittableError(Exception):
    """The application status does not allow resubmission."""


class VersionConflictError(Exception):
    """The client's ``row_version`` is stale."""


class WorkflowInconsistentError(Exception):
    """The stage state does not match the application status."""


class ApproverUnavailableError(Exception):
    """The returning approver is not active; carries the HR message."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class InvalidContentError(Exception):
    """Basic shape validation failed; carries ``errors`` list."""

    def __init__(self, errors):
        self.errors = errors
        super().__init__(f"{len(errors)} content error(s)")


class ValidationFailedError(Exception):
    """Full rule validation failed at resubmit; carries the ``errors`` list."""

    def __init__(self, errors):
        self.errors = errors
        super().__init__(f"{len(errors)} validation error(s)")


def get_edit_context(application_id, actor) -> dict:
    """Return the section-6 edit context, or 404 when not the owner."""
    application = (
        LeaveApplication.objects.select_related(
            "current_stage",
            "current_stage__assigned_approver",
        )
        .filter(id=application_id, employee=actor)
        .first()
    )
    if application is None:
        raise ApplicationNotFoundError()
    return _edit_context(application, actor)


def save_changes(
    *,
    application_id,
    actor,
    leave_type_id,
    start_date,
    end_date,
    reason,
    expected_row_version,
) -> dict:
    """Apply the edited content in place; the status stays rejected/correction."""
    with transaction.atomic():
        application = _lock_owned(application_id, actor)
        _guard_editable(application)
        _guard_version(application, expected_row_version)

        _validate_basic_shape(
            leave_type_id=leave_type_id,
            start_date=start_date,
            end_date=end_date,
            reason=reason,
            today=_today(),
        )

        ensure_baseline_revision(application)

        application.leave_type_id = leave_type_id
        application.start_date = start_date
        application.end_date = end_date
        application.reason = (reason or "").strip()
        application.working_days = _recompute_working_days(start_date, end_date, _today())
        application.row_version += 1
        application.save(
            update_fields=[
                "leave_type_id",
                "start_date",
                "end_date",
                "reason",
                "working_days",
                "row_version",
                "updated_at",
            ]
        )

        record_event(
            actor=actor,
            action="leave_application.changes_saved",
            target=application,
            prev_state=application.status,
            new_state=application.status,
            metadata={
                "leave_type_id": application.leave_type_id,
                "start_date": application.start_date.isoformat() if application.start_date else None,
                "end_date": application.end_date.isoformat() if application.end_date else None,
                "row_version": application.row_version,
            },
        )

        return _edit_context(application, actor)


def add_document(*, application_id, actor, file, expected_row_version) -> dict:
    """Upload and attach a new active document, then return the edit context.

    The file validation, storage write, row creation and audit event are all
    handled by the Unit 19 document service (``documents.add_document``); this
    wrapper keeps the resubmission concurrency/baseline orchestration and its
    API/error contract.
    """
    with transaction.atomic():
        application = _lock_owned(application_id, actor)
        _guard_editable(application)
        _guard_version(application, expected_row_version)

        ensure_baseline_revision(application)

        documents.add_document(application_id=application_id, actor=actor, file=file)

        application.row_version += 1
        application.save(update_fields=["row_version", "updated_at"])

        return _edit_context(application, actor)


def replace_document(*, application_id, actor, document_id, file, expected_row_version) -> dict:
    """Retire ``document_id`` and attach its replacement; no file is deleted.

    Delegates to the Unit 19 document service (``documents.replace_document``),
    which keeps the retirement/audit semantics; the resubmission wrapper owns
    the concurrency guard, baseline revision, row-version bump and edit context.
    """
    with transaction.atomic():
        application = _lock_owned(application_id, actor)
        _guard_editable(application)
        _guard_version(application, expected_row_version)

        ensure_baseline_revision(application)

        documents.replace_document(
            application_id=application_id,
            actor=actor,
            document_id=document_id,
            file=file,
        )

        application.row_version += 1
        application.save(update_fields=["row_version", "updated_at"])

        return _edit_context(application, actor)


def remove_document(*, application_id, actor, document_id, expected_row_version) -> dict:
    """Retire ``document_id`` as removed; the file stays in storage history.

    Delegates to the Unit 19 document service (``documents.remove_document``).
    """
    with transaction.atomic():
        application = _lock_owned(application_id, actor)
        _guard_editable(application)
        _guard_version(application, expected_row_version)

        ensure_baseline_revision(application)

        documents.remove_document(
            application_id=application_id,
            actor=actor,
            document_id=document_id,
        )

        application.row_version += 1
        application.save(update_fields=["row_version", "updated_at"])

        return _edit_context(application, actor)


def resubmit(*, application_id, actor, expected_row_version) -> LeaveApplication:
    """Validate and resubmit; returns the updated application on success."""
    from ..validation.pipeline import run_validation
    from workflows.events import ApprovalEvent, emit_approval_event
    from workflows.models import ApplicationStage

    with transaction.atomic():
        application = _lock_owned(application_id, actor)

        if application.status not in EDITABLE_STATUSES:
            raise NotResubmittableError()

        stage = application.current_stage
        expected_stage_status = STAGE_STATUS_BY_APPLICATION_STATUS.get(application.status)
        if (
            stage is None
            or stage.status != expected_stage_status
        ):
            raise WorkflowInconsistentError()

        _guard_version(application, expected_row_version)
        _guard_approver_active(stage)

        _acquire_employee_lock(actor.id)

        result = run_validation(
            user=actor,
            leave_type_id=application.leave_type_id,
            start_date_raw=application.start_date,
            end_date_raw=application.end_date,
            application=application,
            today=_today(),
=======
"""Resubmission service (Unit 21, D9).

``resubmit_application`` is the sole path that returns a rejected or
correction-required application to its configured stage as a fresh pending
approval. It re-validates the current content against the rules effective on
the resubmission date (same reference number), refreshes the immutable rules
snapshot, freezes the new cycle's revision history row, increments
``submission_cycle``, re-opens the returning stage in place (``pending``,
``decision_version + 1``) and moves the routing spine —
``LeaveApplication.current_approver`` — to that stage's **configured**
``assigned_approver`` (deliberately not the rejecting actor; delegations and
reassignments re-apply automatically at query time). The stage chain is never
rebuilt.
"""

from audit.models import AuditEntry
from audit.services import changed_fields, record_audit
from django.db import transaction
from django.db.models import F
from django.utils import timezone


class ResubmissionNotFoundError(Exception):
    """The application does not exist or belongs to another employee."""


class NotResubmittableError(Exception):
    """The application status is not ``rejected``/``correction_required``."""


class WorkflowInconsistentError(Exception):
    """The returning stage is missing or not in the expected decided state."""


def resubmit_application(*, user, application_id):
    """Validate and resubmit ``application_id`` owned by ``user``.

    Raises ``ResubmissionNotFoundError`` (404), ``NotResubmittableError`` (409),
    ``WorkflowInconsistentError`` (409) or ``ValidationFailedError`` (422);
    returns the persisted application on success.
    """
    from ..models import LeaveApplication
    from ..providers import get_provider
    from ..signals import leave_application_submitted
    from ..validation.pipeline import run_validation
    from .submission import (
        ValidationFailedError,
        _acquire_employee_lock,
        build_rules_snapshot,
        record_revision,
    )
    from workflows.models import ApplicationStage

    with transaction.atomic():
        provider = get_provider()
        employee = provider.get_employee_for_user(user)

        app = (
            LeaveApplication.objects.filter(id=application_id, employee=user)
            .select_for_update()
            .first()
        )
        if app is None:
            raise ResubmissionNotFoundError()

        if app.status not in (
            LeaveApplication.Status.REJECTED,
            LeaveApplication.Status.CORRECTION_REQUIRED,
        ):
            raise NotResubmittableError()

        _acquire_employee_lock(employee.id if employee is not None else 0)

        result = run_validation(
            user=user,
            leave_type_id=app.leave_type_id,
            start_date_raw=app.start_date,
            end_date_raw=app.end_date,
            application=app,
>>>>>>> feature/plans-teams
        )
        if not result.valid:
            raise ValidationFailedError(result.errors)

<<<<<<< HEAD
        previous_status = application.status

        application.working_days = result.working_days
        application.calendar_days = result.calendar_days
        application.financial_year_label = result.financial_year
        application.submission_cycle += 1
        application.status = LeaveApplication.Status.PENDING
        application.current_approver_id = stage.assigned_approver_id
        application.rules_snapshot = build_rules_snapshot(result.context)
        application.row_version += 1
        application.save(
=======
        stage = (
            ApplicationStage.objects.select_for_update()
            .filter(pk=app.current_stage_id, application=app)
            .first()
        )
        if stage is None or stage.status not in (
            ApplicationStage.Status.REJECTED,
            ApplicationStage.Status.CORRECTION_REQUESTED,
        ):
            raise WorkflowInconsistentError()

        snapshot = build_rules_snapshot(result.context)

        before_status = app.status
        before_cycle = app.submission_cycle
        before_version = stage.decision_version

        # Reopen the returning stage in place; the chain is kept, not rebuilt.
        stage.status = ApplicationStage.Status.PENDING
        stage.decision_version = F("decision_version") + 1
        stage.save(update_fields=["status", "decision_version", "updated_at"])

        app.working_days = result.working_days
        app.calendar_days = result.calendar_days
        app.financial_year_label = result.financial_year
        app.rules_snapshot = snapshot
        app.submitted_at = timezone.now()
        app.status = LeaveApplication.Status.SUBMITTED
        app.submission_cycle = F("submission_cycle") + 1
        app.current_stage = stage
        app.current_approver = stage.assigned_approver
        app.save(
>>>>>>> feature/plans-teams
            update_fields=[
                "working_days",
                "calendar_days",
                "financial_year_label",
<<<<<<< HEAD
                "submission_cycle",
                "status",
                "current_approver",
                "rules_snapshot",
                "row_version",
                "updated_at",
            ]
        )

        stage.status = ApplicationStage.Status.PENDING
        stage.version += 1
        stage.save(update_fields=["status", "version"])

        revision = create_revision(application, actor)

        record_event(
            actor=actor,
            action="application_resubmitted",
            target=application,
            prev_state=previous_status,
            new_state=application.status,
            metadata={
                "submission_cycle": application.submission_cycle,
                "stage_order": stage.stage_order,
                "revision_id": str(revision.id),
                "reference_number": application.reference_number,
            },
        )

        cycle = application.submission_cycle
        application_id = str(application.id)
        stage_order = stage.stage_order

        transaction.on_commit(
            lambda: emit_approval_event(
                ApprovalEvent(
                    kind="application_resubmitted",
                    application_id=application_id,
                    stage_order=stage_order,
                    action="resubmit",
                    cycle=cycle,
                    occurred_at=timezone.now(),
                    payload={"status": application.status},
                )
            )
        )

        return application


def create_revision(application, actor) -> ApplicationRevision:
    """Write the immutable snapshot for the current ``submission_cycle``.

    ``changes`` is computed against the previous revision (``None`` for
    revision 1). Called by the Unit 14 submit service and by ``resubmit``.
    """
    previous = application.revisions.order_by("revision_number").last()
    current_snapshot = _current_snapshot(application)
    changes = None
    if previous is not None:
        changes = compute_changes(_previous_snapshot(previous), current_snapshot)

    leave_type_name = _leave_type_label(application, application.leave_type_id)
    leave_type, _ = LeaveType.objects.get_or_create(
        id=application.leave_type_id,
        defaults={"name": leave_type_name},
    )
    return ApplicationRevision.objects.create(
        application=application,
        revision_number=application.submission_cycle,
        leave_type=leave_type,
        leave_type_name=leave_type_name,
        start_date=application.start_date,
        end_date=application.end_date,
        working_days=application.working_days,
        reason=application.reason or "",
        documents=_active_documents_payload(application),
        changes=changes,
        created_by=actor,
    )


def ensure_baseline_revision(application) -> ApplicationRevision:
    """Create a revision for the current cycle if none exists yet.

    Applications submitted before Unit 17 have no revision; the first edit or
    document operation writes a baseline from the current content (still the
    last submitted content, since no mutation has happened yet).
    """
    baseline = application.revisions.filter(
        revision_number=application.submission_cycle
    ).first()
    if baseline is not None:
        return baseline
    return create_revision(application, application.employee)


def _edit_context(application, actor) -> dict:
    """Serialize the full section-6 edit-context payload."""
    feedback_decision = (
        application.approval_decisions.filter(
            submission_cycle=application.submission_cycle,
            action__in=(
                "reject",
                "return_for_correction",
            ),
        )
        .order_by("-decided_at", "-id")
        .first()
    )
    current_stage = application.current_stage

    active_documents = list(
        application.documents.filter(status=SupportingDocument.Status.ACTIVE).order_by(
            "uploaded_at", "id"
        )
    )
    retired_documents = list(
        application.documents.filter(
            status=SupportingDocument.Status.RETIRED
        ).order_by("retired_at", "id")
    )
    replaced_names = {
        str(doc.id): doc.replaced_by.file_name
        for doc in retired_documents
        if doc.replaced_by_id is not None
    }

    previous = application.revisions.order_by("revision_number").last()
    if previous is None:
        previous_snapshot = {
            "leave_type": {"id": None, "name": ""},
            "start_date": None,
            "end_date": None,
            "working_days": None,
            "reason": "",
            "documents": [],
        }
    else:
        previous_snapshot = _previous_snapshot(previous)

    return {
        "id": str(application.id),
        "reference": application.reference_number or "",
        "status": application.status,
        "submission_cycle": application.submission_cycle,
        "row_version": application.row_version,
        "can_edit": application.status in EDITABLE_STATUSES,
        "feedback": (
            {
                "action": feedback_decision.action,
                "role_label": feedback_decision.role_label,
                "approver_name": feedback_decision.approver_name,
                "comment": feedback_decision.comment,
                "decided_at": feedback_decision.decided_at.isoformat().replace(
                    "+00:00", "Z"
                )
                if feedback_decision.decided_at
                else None,
            }
            if feedback_decision is not None
            else None
        ),
        "returns_to": _returns_to(current_stage),
        "content": {
            "leave_type_id": application.leave_type_id,
            "leave_type_name": _leave_type_label(
                application, application.leave_type_id
            ),
            "start_date": _iso_date(application.start_date),
            "end_date": _iso_date(application.end_date),
            "working_days": application.working_days,
            "reason": application.reason or "",
        },
        "documents": {
            "active": [
                {
                    "id": str(document.id),
                    "name": document.file_name,
                    "size_bytes": document.file_size,
                    "uploaded_at": _iso(document.uploaded_at),
                }
                for document in active_documents
            ],
            "retired": [
                {
                    "id": str(document.id),
                    "name": document.file_name,
                    "retired_at": _iso(document.retired_at),
                    "retire_reason": document.retire_reason,
                    "replaced_by_name": replaced_names.get(str(document.id)),
                }
                for document in retired_documents
            ],
        },
        "changes_preview": compute_changes(
            previous_snapshot, _current_snapshot(application)
        ),
    }


def _returns_to(stage) -> dict | None:
    if stage is None:
        return None
    approver = stage.assigned_approver
    approver_name = (
        approver.get_full_name() if approver else stage.role_label or ""
    )
    if not approver_name and stage.role_label:
        approver_name = stage.role_label
    return {
        "role_label": stage.role_label,
        "approver_name": approver_name,
    }


def _lock_owned(application_id, actor) -> LeaveApplication:
    application = (
        LeaveApplication.objects.filter(id=application_id, employee=actor)
        .select_for_update()
        .first()
    )
    if application is None:
        raise ApplicationNotFoundError()
    # Relations are loaded after the lock: PostgreSQL rejects FOR UPDATE on the
    # nullable side of an outer join (current_stage / assigned_approver).
    return LeaveApplication.objects.select_related(
        "current_stage", "current_stage__assigned_approver"
    ).get(pk=application.pk)


def _guard_editable(application) -> None:
    if application.status not in EDITABLE_STATUSES:
        raise NotEditableError()


def _guard_version(application, expected_row_version) -> None:
    if int(expected_row_version) != application.row_version:
        raise VersionConflictError()


def _guard_approver_active(stage) -> None:
    approver = stage.assigned_approver
    if approver is None or not approver.is_active:
        raise ApproverUnavailableError(
            "Your approver is currently unavailable. Please contact HR."
        )


def _validate_basic_shape(*, leave_type_id, start_date, end_date, reason, today) -> None:
    from ..providers import get_provider

    errors = []

    if not leave_type_id:
        errors.append(
            {
                "code": "LEAVE_TYPE_REQUIRED",
                "field": "leave_type_id",
                "message": "Select a valid leave type.",
            }
        )
    elif get_provider().get_leave_type_rules(leave_type_id, today) is None:
        errors.append(
            {
                "code": "LEAVE_TYPE_UNAVAILABLE",
                "field": "leave_type_id",
                "message": "The selected leave type is not available.",
            }
        )

    if start_date is None:
        errors.append(
            {
                "code": "START_DATE_REQUIRED",
                "field": "start_date",
                "message": "Start date is required.",
            }
        )
    if end_date is None:
        errors.append(
            {
                "code": "END_DATE_REQUIRED",
                "field": "end_date",
                "message": "End date is required.",
            }
        )
    if (
        start_date is not None
        and end_date is not None
        and end_date < start_date
    ):
        errors.append(
            {
                "code": "END_DATE_BEFORE_START",
                "field": "end_date",
                "message": "End date must be on or after the start date.",
            }
        )

    if reason is not None and len(reason) > MAX_REASON_LENGTH:
        errors.append(
            {
                "code": "REASON_TOO_LONG",
                "field": "reason",
                "message": f"The reason must be at most {MAX_REASON_LENGTH} characters.",
            }
        )

    if errors:
        raise InvalidContentError(errors)


def _recompute_working_days(start_date, end_date, today) -> int | None:
    from ..providers import get_provider
    from ..validation.working_days import count_working_days

    if start_date is None or end_date is None:
        return None
    provider = get_provider()
    holiday_start = min(today + timedelta(days=1), start_date)
    holidays = set(provider.get_public_holidays(holiday_start, end_date))
    return count_working_days(start_date, end_date, holidays)


def _today():
    return timezone.localdate()


def _leave_type_label(application, leave_type_id) -> str:
    leave_type = LeaveType.objects.filter(id=leave_type_id).first()
    if leave_type is not None:
        return leave_type.name
    snapshot = application.rules_snapshot or {}
    leave_type_snapshot = snapshot.get("leave_type") or {}
    return leave_type_snapshot.get("name", "")


def _active_documents_payload(application) -> list[dict]:
    return [
        {
            "document_id": str(document.id),
            "name": document.file_name,
            "size_bytes": document.file_size,
            "content_type": document.content_type,
        }
        for document in application.documents.filter(
            status=SupportingDocument.Status.ACTIVE
        ).order_by("uploaded_at", "id")
    ]


def _retired_documents_payload(application) -> list[dict]:
    return [
        {
            "document_id": str(document.id),
            "name": document.file_name,
            "retire_reason": document.retire_reason,
            "replaced_by_id": (
                str(document.replaced_by_id) if document.replaced_by_id else None
            ),
        }
        for document in application.documents.filter(
            status=SupportingDocument.Status.RETIRED
        ).order_by("retired_at", "id")
    ]


def _previous_snapshot(revision) -> dict:
    return {
        "leave_type": {"id": revision.leave_type_id, "name": revision.leave_type_name},
        "start_date": revision.start_date,
        "end_date": revision.end_date,
        "working_days": revision.working_days,
        "reason": revision.reason or "",
        "documents": revision.documents or [],
    }


def _current_snapshot(application) -> dict:
    return {
        "leave_type": {
            "id": application.leave_type_id,
            "name": _leave_type_label(application, application.leave_type_id),
        },
        "start_date": application.start_date,
        "end_date": application.end_date,
        "working_days": application.working_days,
        "reason": application.reason or "",
        "documents": _active_documents_payload(application),
        "retired": _retired_documents_payload(application),
    }


def _iso(value) -> str | None:
    if not value:
        return None
    return value.isoformat().replace("+00:00", "Z")


def _iso_date(value) -> str | None:
    if not value:
        return None
    if isinstance(value, str):
        return value
    return value.isoformat()
=======
                "rules_snapshot",
                "submitted_at",
                "status",
                "submission_cycle",
                "current_stage",
                "current_approver",
            ]
        )
        app.refresh_from_db()

        record_revision(app, user=user)

        record_audit(
            actor=user,
            action=AuditEntry.Action.APPLICATION_RESUBMITTED,
            target_type=AuditEntry.TargetType.APPLICATION,
            target_id=app.pk,
            target_summary=app.reference_number,
            detail=changed_fields(
                {
                    "status": before_status,
                    "submission_cycle": before_cycle,
                    "decision_version": before_version,
                    "current_approver_id": None,
                },
                {
                    "status": app.status,
                    "submission_cycle": app.submission_cycle,
                    "decision_version": stage.decision_version,
                    "current_approver_id": (
                        stage.assigned_approver_id if stage.assigned_approver_id else None
                    ),
                    "resubmitted_at": app.submitted_at.isoformat(),
                },
            ),
        )

        transaction.on_commit(
            lambda: leave_application_submitted.send(
                sender=LeaveApplication, application=app
            )
        )

        return app
>>>>>>> feature/plans-teams
