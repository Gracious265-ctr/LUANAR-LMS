from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class ImmutableAuditQuerySet(models.QuerySet):
    """QuerySet where bulk writes on the append-only table are impossible."""

    def update(self, *args, **kwargs):
        raise RuntimeError("Audit events are immutable.")

    def delete(self):
        raise RuntimeError("Audit events are immutable.")


class AuditEventManager(models.Manager):
    """Manager that makes bulk writes on an append-only table impossible."""

    def get_queryset(self):
        return ImmutableAuditQuerySet(self.model, using=self._db)

    def update(self, *args, **kwargs):
        raise RuntimeError("Audit events are immutable.")

    def delete(self):
        raise RuntimeError("Audit events are immutable.")


class AuditEvent(models.Model):
    """An immutable, append-only record of a state change in the LMS.

    Used by Unit 14 submission and later units (approvals, reassignments,
    corrections) to write a thin history trail: what changed, by whom, from
    which state to which, with a small metadata payload. Rows are never
    updated or deleted through the ORM (Unit 24); a parent row's database
    cascade still removes an event when the parent genuinely goes away.
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
    object_id = models.CharField(max_length=100, null=True, blank=True)
    content_object = GenericForeignKey("content_type", "object_id")

    prev_state = models.CharField(max_length=50, blank=True, default="")
    new_state = models.CharField(max_length=50, blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = AuditEventManager()

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["content_type", "object_id"], name="audit_target_idx"),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("Audit events are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("Audit events are immutable.")

    def __str__(self) -> str:
        return f"AuditEvent({self.action} -> {self.new_state or '—'})"