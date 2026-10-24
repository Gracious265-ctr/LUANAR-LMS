"""In-app notification feed endpoints (refinement unit 08 §3.4).

Every view is scoped to ``request.user`` — a notification belongs to exactly
one recipient, so another user's id can never be read or mutated here; a
foreign ``mark-read`` id simply matches nothing (404), the same ownership
discipline the rest of the project uses for personal data.
"""

from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification
from .serializers import NotificationSerializer
from .services import (
    get_recent_notifications,
    get_unread_count,
    mark_all_read,
    mark_read,
)


class NotificationListView(APIView):
    """``GET /api/v1/notifications/`` — the popover's recent window.

    ``?unread_only=true`` narrows to unread rows (filtered in the query, not
    after the limit, so the window stays full when unread rows exist).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        unread_only = str(request.query_params.get("unread_only", "")).lower() in (
            "true",
            "1",
        )
        notifications = get_recent_notifications(request.user, unread_only=unread_only)
        return Response(NotificationSerializer(notifications, many=True).data)


class UnreadCountView(APIView):
    """``GET /api/v1/notifications/unread-count/`` — the navbar badge."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"count": get_unread_count(request.user)})


class MarkReadView(APIView):
    """``POST /api/v1/notifications/{id}/mark-read/`` — one of the caller's own."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not Notification.objects.filter(pk=pk, recipient=request.user).exists():
            return Response(status=status.HTTP_404_NOT_FOUND)
        mark_read(pk, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MarkAllReadView(APIView):
    """``POST /api/v1/notifications/mark-all-read/`` — clears the caller's badge."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        mark_all_read(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
