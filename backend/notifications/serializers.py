from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    recipient_username = serializers.CharField(
        source="recipient.username", read_only=True
    )

    class Meta:
        model = Notification
        fields = [
            "id",
            "event_type",
            "recipient",
            "recipient_username",
            "channel",
            "email_to",
            "subject",
            "status",
            "attempts",
            "error",
            "application_id",
            "target_object_id",
            "created_at",
            "sent_at",
        ]
        read_only_fields = fields