"""Submission service (Unit 14, Section 3.8).

``submit_application`` is the only path that turns a draft into a submitted
application. It runs entirely in one transaction, re-validates with the draft
attached inside a per-employee advisory lock (so two concurrent overlapping
submissions cannot both pass), snapshots the evaluated rules, assigns the
reference number, writes an audit record and fires a signal on commit.

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
    """The re-validation failed; carries the full error list."""

    def __init__(self, errors):
        self.errors = errors
        super().__init__(f"{len(errors)} validation error(s)")


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
    from .references import next_reference
    from .workflow_gate import check_workflow_ready

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

        if not check_workflow_ready(app):
            raise ApplicationNotSubmittableError()

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
                    {
                        "code": "workflow_unavailable",
                        "message": message,
                        "field": "—",
                    }
                    for message in exc.messages
                ]
            )

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