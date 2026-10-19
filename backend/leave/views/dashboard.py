"""The Leave app dashboard endpoint (Unit 3)."""

from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from ..services.dashboard import get_dashboard_data


class LeaveDashboardView(APIView):
    """``GET /api/v1/leave/dashboard/`` — the signed-in employee's own leave.

    Everything is scoped to ``request.user`` inside the service, so this view
    needs no object-level permission: there is no other employee's data to
    reach. Authentication is the whole guard.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(get_dashboard_data(request.user))
