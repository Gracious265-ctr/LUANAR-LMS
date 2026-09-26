from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "event_type",
        "email_to",
        "recipient",
        "status",
        "attempts",
        "created_at",
        "sent_at",
    )
    list_filter = ("status", "event_type")
    search_fields = ("email_to", "subject")
    readonly_fields = (
        "event_type",
        "recipient",
        "channel",
        "email_to",
        "subject",
        "body",
        "status",
        "attempts",
        "error",
        "application_id",
        "target_object_id",
        "created_at",
        "sent_at",
    )
