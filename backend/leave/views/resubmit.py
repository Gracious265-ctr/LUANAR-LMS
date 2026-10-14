"""Resubmission endpoint (Unit 21, D9).

``POST /api/v1/leave-applications/{id}/resubmit/`` — 200 on success with the
submit-style payload, 404 for a missing or unowned application, 409 when the
status is not resubmittable or the workflow is inconsistent, 422 when the
re-validation fails.
"""

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .validation import _issue_payload, submit_payload


class LeaveApplicationResubmitView(APIView):
    """Resubmit a rejected / correction-required application (owner only)."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        from leave.services.resubmission import (
            NotResubmittableError,
            ResubmissionNotFoundError,
            WorkflowInconsistentError,
            resubmit_application,
        )
        from leave.services.submission import ValidationFailedError

        try:
            app = resubmit_application(user=request.user, application_id=pk)
        except ResubmissionNotFoundError:
            return Response(
                {"detail": "The application does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except NotResubmittableError:
            return Response(
                {"code": "NOT_RESUBMITTABLE"},
                status=status.HTTP_409_CONFLICT,
            )
        except WorkflowInconsistentError:
            return Response(
                {"code": "WORKFLOW_INCONSISTENT"},
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