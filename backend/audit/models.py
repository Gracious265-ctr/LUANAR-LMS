from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class AuditEvent(models.Model):
    """An immutable, append-only record of a state change in the LMS.

    Used by Unit 14 submission and later units (approvals, reassignments,
    corrections) to write a thin history trail: what changed, by whom, from
    which state to which, with a small metadata payload.
    """

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    action = models.CharField(max_length=100)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    object_id = models.UUIDField(null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")

    prev_state = models.CharField(max_length=50, blank=True, default="")
    new_state = models.CharField(max_length=50, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"AuditEvent({self.action} -> {self.new_state or '—'})"