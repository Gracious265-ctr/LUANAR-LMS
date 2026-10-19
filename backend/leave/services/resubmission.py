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
    from approvals.models import ApplicationStage

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
        )
        if not result.valid:
            raise ValidationFailedError(result.errors)

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
            update_fields=[
                "working_days",
                "calendar_days",
                "financial_year_label",
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