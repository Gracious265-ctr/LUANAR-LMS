"""HR-facing notification queries (Unit 22, depth 1).

``GET /api/v1/notifications/?status=failed`` lists delivery failures so HR can
see what could not be sent without digging through worker logs. Filtering is
read-only; notifications are never mutated through the API.
"""

from rest_framework import generics, permissions

from users.permissions import IsHRRole

from .models import Notification
from .serializers import NotificationSerializer


class NotificationListView(generics.ListAPIView):
    """List notification records; HR-only, optionally filtered by ``status``."""

    permission_classes = [permissions.IsAuthenticated, IsHRRole]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        queryset = Notification.objects.select_related("recipient").all()
        status = self.request.query_params.get("status")
        if status in (Notification.Status.SENT, Notification.Status.FAILED):
            queryset = queryset.filter(status=status)
        return queryset