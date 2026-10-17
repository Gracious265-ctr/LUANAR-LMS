"""Submission service (Unit 14, Section 3.8).

``submit_application`` is the only path that turns a draft into a submitted
application. It runs entirely in one transaction, re-validates with the draft
attached inside a per-employee advisory lock (so two concurrent overlapping
submissions cannot both pass), snapshots the evaluated rules, assigns the
reference number, freezes the per-cycle revision history row, writes an audit
record and fires a signal on commit.

Submission never touches balance data: there are no ledger writes and no
changes to any balance field.
"""

from audit.models import AuditEntry
from audit.services import changed_fields, record_audit
from django.db import connection, transaction
from django.utils import timezone


class ApplicationNotFoundError(Exception):
    """The application does not exist or belongs to another employee."""


class AlreadySubmittedError(Exception):
    """The application was already submitted; carries its reference."""

    def __init__(self, reference_number: str | None):
        self.reference_number = reference_number
        super().__init__(reference_number)


class ApplicationNotSubmittableError(Exception):
    """The application is not in ``draft`` status and cannot be submitted."""


class ValidationFailedError(Exception):
    """The re-validation failed; carries the full error list.

    ``str()`` spells the issues out rather than counting them. This exception is
    raised from a service and ends up in logs and in a 422 body; a bare
    "1 validation error(s)" names neither the rule that fired nor what to do
    about it, and the one thing an applicant or support officer reads is this
    string.
    """

    def __init__(self, errors):
        self.errors = errors
        super().__init__(
            "; ".join(f"{getattr(issue, 'message', issue)}" for issue in errors)
            or "validation failed"
        )


def submit_application(*, user, application_id):
    """Validate and submit the draft owned by ``user``.

    Raises ``ApplicationNotFoundError`` (404), ``AlreadySubmittedError`` (409),
    ``ApplicationNotSubmittableErrorError`` (409), or ``ValidationFailedError``
    (422); returns the persisted application on success.
    """
    from ..models import LeaveApplication
    from ..providers import get_provider
    from ..signals import leave_application_submitted
    from ..validation.pipeline import run_validation
    from ..validation.types import ValidationIssue
    from .references import next_reference
    from .workflow_gate import WorkflowUnavailableError, check_workflow_ready

    with transaction.atomic():
        provider = get_provider()
        employee = provider.get_employee_for_user(user)

        app = (
            LeaveApplication.objects.filter(id=application_id, employee=user)
            .select_for_update()
            .first()
        )
        if app is None:
            raise ApplicationNotFoundError()

        if app.status == LeaveApplication.Status.SUBMITTED:
            raise AlreadySubmittedError(app.reference_number)
        if app.status != LeaveApplication.Status.DRAFT:
            raise ApplicationNotSubmittableError()

        _acquire_employee_lock(employee.id if employee is not None else 0)

        result = run_validation(
            user=user,
            leave_type_id=app.leave_type_id,
            start_date_raw=app.start_date,
            end_date_raw=app.end_date,
            application=app,
        )
        if not result.valid:
            raise ValidationFailedError(result.errors)

        try:
            check_workflow_ready(app)
        except WorkflowUnavailableError as exc:
            raise ValidationFailedError(
                [
                    ValidationIssue(
                        code="workflow_unavailable",
                        field="—",
                        message=message,
                    )
                    for message in exc.messages
                ]
            )

        snapshot = build_rules_snapshot(result.context)

        app.working_days = result.working_days
        app.calendar_days = result.calendar_days
        app.financial_year_label = result.financial_year
        app.rules_snapshot = snapshot
        app.submitted_at = timezone.now()
        app.status = LeaveApplication.Status.SUBMITTED
        if app.reference_number is None:
            app.reference_number = next_reference(result.financial_year)

        app.save(
            update_fields=[
                "working_days",
                "calendar_days",
                "financial_year_label",
                "rules_snapshot",
                "submitted_at",
                "status",
                "reference_number",
            ]
        )

        try:
            from workflows.services import WorkflowAssignmentError, assign_workflow

            assign_workflow(app)
        except WorkflowAssignmentError as exc:
            raise ValidationFailedError(
                [
                    ValidationIssue(
                        code="workflow_unavailable",
                        field="—",
                        message=message,
                    )
                    for message in exc.messages
                ]
            )

        record_revision(app, user=user)

        record_audit(
            actor=user,
            action=AuditEntry.Action.SUBMITTED,
            target_type=AuditEntry.TargetType.APPLICATION,
            target_id=app.pk,
            target_summary=app.reference_number,
            detail=changed_fields(
                {
                    "status": LeaveApplication.Status.DRAFT,
                    "reference_number": None,
                    "working_days": None,
                },
                {
                    "status": LeaveApplication.Status.SUBMITTED,
                    "reference_number": app.reference_number,
                    "working_days": app.working_days,
                },
            ),
        )

        transaction.on_commit(
            lambda: leave_application_submitted.send(
                sender=LeaveApplication, application=app
            )
        )

        return app


def _acquire_employee_lock(employee_id: int) -> None:
    """Take the per-employee advisory lock for the current transaction.

    Serializes concurrent submission validation for one employee so two
    overlapping submissions cannot both pass the overlap check. The lock
    releases automatically at transaction end.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtext('leave_submit'), %s)",
            [employee_id],
        )


def build_rules_snapshot(ctx) -> dict:
    """Project the evaluated context into the immutable ``rules_snapshot``.

    Historical integrity (invariant 12.5): later configuration changes must
    never alter this record, so every value the submission depended on is
    stored here.
    """
    rules = ctx.leave_type
    fy = ctx.financial_year
    snapshot = {
        "validator_version": "1",
        "leave_type": {
            "id": rules.id,
            "code": rules.code,
            "name": rules.name,
            "is_active": rules.is_active,
            "deducts_annual_balance": rules.deducts_annual_balance,
            "max_duration": rules.max_duration,
            "max_duration_unit": rules.max_duration_unit,
            "min_notice": rules.min_notice,
            "min_notice_unit": rules.min_notice_unit,
            "requires_document": rules.requires_document,
            "eligibility": [
                {"type": rule.type, "params": rule.params}
                for rule in rules.eligibility
            ],
            "effective_from": rules.effective_from.isoformat(),
        },
        "financial_year": {
            "label": fy.label,
            "start": fy.start.isoformat(),
            "end": fy.end.isoformat(),
        },
        "holidays": _holidays_in_range(ctx),
        "working_days": ctx.working_days,
        "calendar_days": ctx.calendar_days,
        "available_balance": (
            str(ctx.available_balance)
            if ctx.available_balance is not None
            else None
        ),
        "balance_after_if_approved": (
            str(ctx.balance_after_if_approved)
            if ctx.balance_after_if_approved is not None
            else None
        ),
        "eligibility_outcome": {
            "result": "eligible",
            "rules": [
                {"type": rule.type, "params": rule.params}
                for rule in rules.eligibility
            ],
        },
    }
    return snapshot


def _holidays_in_range(ctx) -> list[str]:
    if ctx.start_date is None or ctx.end_date is None:
        return []
    return sorted(
        day.isoformat()
        for day in ctx.holidays
        if ctx.start_date <= day <= ctx.end_date
    )


def _revision_documents(app) -> list[dict]:
    """The active supporting documents as a JSON-safe list (Unit 24 D7).

    Retired rows are excluded because only active documents are shown to the
    approver; the retired row itself is kept so the audit trail can resolve it.
    Ordered deterministically so the cycle-over-cycle diff is stable.
    """
    from ..models import SupportingDocument

    return [
        {
            "id": str(document.id),
            "file_name": document.file_name,
            "content_type": document.content_type,
            "file_size": document.file_size,
            "uploaded_at": document.uploaded_at.isoformat(),
        }
        for document in app.documents.filter(
            status=SupportingDocument.Status.ACTIVE
        ).order_by("uploaded_at", "id")
    ]


def _revision_fields(app) -> dict:
    """The approver-facing projection frozen for one submission cycle.

    The leave-type identity is read from the just-written ``rules_snapshot``
    rather than the live ``LeaveType`` registry, so the revision keeps the name
    the approver saw even after HR later renames the leave type.
    """
    snapshot = app.rules_snapshot or {}
    leave_type = snapshot.get("leave_type") or {}
    return {
        "leave_type_id": leave_type.get("id") or app.leave_type_id,
        "leave_type_name": leave_type.get("name") or "",
        "start_date": app.start_date.isoformat() if app.start_date else None,
        "end_date": app.end_date.isoformat() if app.end_date else None,
        "working_days": app.working_days,
        "reason": app.reason,
        "documents": _revision_documents(app),
    }


def _revision_fields_from_row(revision) -> dict:
    """The same projection rebuilt from a stored revision row, for diffing."""
    return {
        "leave_type_id": revision.leave_type_id,
        "leave_type_name": revision.leave_type_name,
        "start_date": revision.start_date.isoformat() if revision.start_date else None,
        "end_date": revision.end_date.isoformat() if revision.end_date else None,
        "working_days": revision.working_days,
        "reason": revision.reason,
        "documents": revision.documents or [],
    }


def record_revision(app, *, user) -> None:
    """Write the append-only per-cycle history row for ``app`` (Unit 24 D6/D7).

    ``revision_number`` is the application's ``submission_cycle``, so every
    submission and resubmission freezes the exact state the approver sees.
    ``changes`` diffs this cycle against the previous cycle's row and is
    ``None`` on first submission. Must be called inside the same transaction
    that writes the snapshot and the audit entry, so a failure leaves no
    application change, no snapshot, and no phantom revision.
    """
    from ..models import ApplicationRevision

    after = _revision_fields(app)
    previous = (
        ApplicationRevision.objects.filter(application=app)
        .order_by("-revision_number")
        .first()
    )
    ApplicationRevision.objects.create(
        application=app,
        revision_number=app.submission_cycle,
        leave_type_id=after["leave_type_id"],
        leave_type_name=after["leave_type_name"],
        start_date=app.start_date,
        end_date=app.end_date,
        working_days=app.working_days,
        reason=app.reason,
        documents=after["documents"],
        changes=(
            None
            if previous is None
            else changed_fields(_revision_fields_from_row(previous), after)
        ),
        created_by=user,
    )