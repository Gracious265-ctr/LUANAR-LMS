"""In-app notification feed serializers (refinement unit 08).

Read-only: rows are written by :mod:`notifications.services` at the moment a
real event happens and are only ever mutated (read) through the dedicated
endpoints, never through a serializer write.
"""

from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "event_type", "message", "link", "is_read", "created_at"]
