"""Views for leave validation and submission (Unit 14).

- ``POST /api/v1/leave/validate/`` — stateless, persists nothing, always 200.
- ``POST /api/v1/leave-applications/{id}/submit/`` — 200 on success, 422 on
  validation failure, 409 on already-submitted / not-submittable, 404 for a
  missing or unowned application.
"""

from decimal import Decimal

from leave.models import LeaveApplication
from leave.serializers.validation import ValidateLeaveSerializer
from leave.services.submission import (
    AlreadySubmittedError,
    ApplicationNotFoundError,
    ApplicationNotSubmittableError,
    ValidationFailedError,
    submit_application,
)
from leave.validation.pipeline import run_validation
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView


class LeaveValidateView(APIView):
    """Stateless validation for live feedback from the application form."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ValidateLeaveSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        draft_id = data.get("draft_id")
        application = None
        if draft_id is not None:
            application = (
                LeaveApplication.objects.filter(
                    id=draft_id, employee=request.user
                ).first()
            )
            if application is None:
                return Response(
                    {"detail": "The draft does not exist or does not belong to you."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        result = run_validation(
            user=request.user,
            leave_type_id=data["leave_type_id"],
            start_date_raw=data["start_date"],
            end_date_raw=data["end_date"],
            application=application,
        )
        return Response(validation_payload(result))


class LeaveApplicationSubmitView(APIView):
    """Submit a draft owned by the authenticated user through the pipeline."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            app = submit_application(user=request.user, application_id=pk)
        except ApplicationNotFoundError:
            return Response(
                {"detail": "The application does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except AlreadySubmittedError as err:
            return Response(
                {
                    "code": "ALREADY_SUBMITTED",
                    "reference_number": err.reference_number,
                },
                status=status.HTTP_409_CONFLICT,
            )
        except ApplicationNotSubmittableError:
            return Response(
                {"code": "APPLICATION_NOT_SUBMITTABLE"},
                status=status.HTTP_409_CONFLICT,
            )
        except ValidationFailedError as err:
            return Response(
                {
                    "code": "VALIDATION_FAILED",
                    "errors": [_issue_payload(i) for i in err.errors],
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        return Response(submit_payload(app), status=status.HTTP_200_OK)


def validation_payload(result) -> dict:
    """Serialize a ``ValidationResult`` for both endpoints."""
    return {
        "valid": result.valid,
        "working_days": result.working_days,
        "calendar_days": result.calendar_days,
        "financial_year": result.financial_year,
        "available_balance": _number(result.available_balance),
        "balance_after_if_approved": _number(result.balance_after_if_approved),
        "errors": [_issue_payload(i) for i in result.errors],
        "warnings": [],
        "skipped_checks": result.skipped_checks,
    }


def submit_payload(app) -> dict:
    """Serialize a successfully submitted application (Section 3.9 payload)."""
    leave_type_id = app.leave_type_id
    leave_type = {"id": leave_type_id}
    if app.rules_snapshot and app.rules_snapshot.get("leave_type"):
        leave_type = app.rules_snapshot["leave_type"]
    payload = {
        "id": str(app.id),
        "reference_number": app.reference_number,
        "status": app.status,
        "submitted_at": app.submitted_at.isoformat() if app.submitted_at else None,
        "working_days": app.working_days,
        "calendar_days": app.calendar_days,
        "leave_type": leave_type,
        "start_date": app.start_date.isoformat() if app.start_date else None,
        "end_date": app.end_date.isoformat() if app.end_date else None,
    }
    return payload


def _issue_payload(issue) -> dict:
    return {
        "code": issue.code,
        "field": issue.field,
        "message": issue.message,
        "detail": issue.detail,
    }


def _number(value) -> str | None:
    """Render a Decimal (or None) as a plain string for the JSON payload."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, int):
        return str(Decimal(value))
    return str(value)