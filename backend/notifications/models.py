"""Queryable outbound notification records (Unit 22).

Every "send" creates one :class:`Notification` row per recipient and enqueues
its delivery through django-q2, so HR can audit what was sent to whom and see
delivery failures without touching server logs.
"""

from django.db import models
from django.conf import settings


class Notification(models.Model):
    class Channel(models.TextChoices):
        EMAIL = "email", "Email"

    class Status(models.TextChoices):
        ENQUEUED = "enqueued", "Enqueued"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    event_type = models.CharField(max_length=60)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    channel = models.CharField(
        max_length=10, choices=Channel.choices, default=Channel.EMAIL
    )
    email_to = models.EmailField()
    subject = models.CharField(max_length=255)
    body = models.TextField()
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.ENQUEUED
    )
    attempts = models.PositiveSmallIntegerField(default=0)
    error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    # Correlation for queries/audit.
    application_id = models.UUIDField(null=True, blank=True)
    target_object_id = models.UUIDField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"])]

    def __str__(self) -> str:
        return f"{self.event_type} → {self.email_to} ({self.status})"