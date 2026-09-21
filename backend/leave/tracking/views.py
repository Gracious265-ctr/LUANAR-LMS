"""Views for employee application tracking (Unit 15).

- ``GET /api/v1/leave-applications/{id}/tracking/`` — read-only, owner-only.
  Returns 200 with the Section 1 payload, 404 for a missing or unowned
  application (never 403), 409 ``application_not_submitted`` for drafts,
  401 when unauthenticated, and 405 for any other method.
"""

from leave.tracking.serializers import WorkflowTrackingSerializer
from leave.tracking.services import (
    ApplicationNotFoundError,
    ApplicationNotSubmittedError,
    get_application_tracking,
)
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView


class ApplicationTrackingView(APIView):
    """Read-only workflow tracking for the caller's submitted application."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        try:
            payload = get_application_tracking(
                user=request.user, application_id=pk
            )
        except ApplicationNotFoundError:
            return Response(
                {"detail": "The application does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except ApplicationNotSubmittedError:
            return Response(
                {
                    "code": "application_not_submitted",
                    "detail": "This application has not been submitted yet.",
                },
                status=status.HTTP_409_CONFLICT,
            )

        serializer = WorkflowTrackingSerializer(payload)
        return Response(serializer.data, status=status.HTTP_200_OK)