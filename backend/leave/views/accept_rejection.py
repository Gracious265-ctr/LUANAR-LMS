"""Accept-rejection endpoint.

``POST /api/v1/leave-applications/{id}/accept-rejection/`` closes a rejection
the employee has decided not to contest. The application stays ``rejected``;
the acceptance is recorded on the row and audited, and the edit/resubmit paths
refuse from then on.

Returns 404 for a missing or unowned application, 409 when the application is
not rejected, and 200 otherwise (including an already-accepted rejection, which
is idempotent).
"""

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from leave.services.resubmission import (
    NotAcceptableError,
    ResubmissionNotFoundError,
    accept_rejection,
)


class LeaveApplicationAcceptRejectionView(APIView):
    """Accept a rejection on the signed-in employee's own application."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            app = accept_rejection(user=request.user, application_id=pk)
        except ResubmissionNotFoundError:
            return Response(
                {"detail": "The application does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except NotAcceptableError:
            return Response(
                {"code": "NOT_REJECTED"},
                status=status.HTTP_409_CONFLICT,
            )

        accepted_at = app.rejection_accepted_at
        return Response(
            {
                "id": str(app.id),
                "status": app.status,
                "rejection_accepted_at": (
                    accepted_at.isoformat().replace("+00:00", "Z")
                    if accepted_at is not None
                    else None
                ),
            },
            status=status.HTTP_200_OK,
        )
