"""HR-facing audit and finalized-leave serializers (Unit 11 port).

Reads :class:`audit.models.AuditEvent` (Units 14-19 already write this trail)
rather than a separate audit model. ``AuditedModelSerializer`` gives the HR
configuration serializers one shared way to record their own create/update
actions; custom serializers/services call the hooks/explicitly where they own
their transaction boundary.
"""

from django.db import transaction
from rest_framework import serializers

from .models import AuditEvent
from .services import current_actor, events_for_target, record_config_change, target_summary


class AuditEventSerializer(serializers.ModelSerializer):
    """Read-only HR-facing serializer for one immutable audit-log entry."""

    actor_name = serializers.SerializerMethodField()
    target_type = serializers.SerializerMethodField()
    target_id = serializers.SerializerMethodField()
    target_summary = serializers.SerializerMethodField()
    detail = serializers.SerializerMethodField()
    reason = serializers.SerializerMethodField()

    class Meta:
        model = AuditEvent
        fields = [
            "id",
            "actor",
            "actor_name",
            "action",
            "target_type",
            "target_id",
            "target_summary",
            "detail",
            "reason",
            "prev_state",
            "new_state",
            "created_at",
        ]
        read_only_fields = fields

    def get_actor_name(self, obj: AuditEvent) -> str:
        return obj.actor.get_full_name() if obj.actor else ""

    def get_target_type(self, obj: AuditEvent) -> str:
        return obj.content_type.model if obj.content_type else ""

    def get_target_id(self, obj: AuditEvent) -> str:
        return obj.object_id or ""

    def get_target_summary(self, obj: AuditEvent) -> str:
        summary = (obj.metadata or {}).get("summary")
        if summary:
            return str(summary)
        content_object = obj.content_object
        if content_object is not None:
            return target_summary(content_object)
        return ""

    def get_detail(self, obj: AuditEvent) -> dict:
        metadata = obj.metadata or {}
        return {
            "before": metadata.get("before"),
            "after": metadata.get("after"),
        }

    def get_reason(self, obj: AuditEvent) -> str:
        return str((obj.metadata or {}).get("reason", ""))


class AuditedModelSerializer(serializers.ModelSerializer):
    """ModelSerializer that records an audit event on create/update.

    Subclasses declare ``audit_prefix`` (action-code namespace, e.g.
    ``"employee"``) and ``audit_fields`` (the model attrs snapshotted for the
    before/after diff), and optionally override ``_audit_snapshot`` (e.g. for
    nested user columns or derived stage lists). Serializers that override
    ``create``/``update`` for their own transaction boundaries call the
    ``_audit_after_create`` / ``_audit_after_update`` hooks directly.
    """

    audit_prefix: str = ""
    audit_fields: list[str] = []

    # -- Auditing -----------------------------------------------------------

    def _audit_snapshot(self, instance) -> dict:
        return {field: getattr(instance, field) for field in self.audit_fields}

    def _audit_summary(self, instance) -> str:
        return target_summary(instance)

    def _record_audit(self, instance, *, action: str, before: dict | None) -> None:
        actor = current_actor(self)
        if actor is None:
            return
        record_config_change(
            actor=actor,
            action=f"{self.audit_prefix}.{action}",
            target=instance,
            summary=self._audit_summary(instance),
            before=before,
            after=self._audit_snapshot(instance),
        )

    def _audit_after_create(self, instance) -> None:
        self._record_audit(instance, action="created", before=None)

    def _audit_after_update(self, instance, before: dict) -> None:
        self._record_audit(instance, action="updated", before=before)

    # -- Default create/update ---------------------------------------------

    def create(self, validated_data: dict):
        with transaction.atomic():
            instance = super().create(validated_data)
            self._audit_after_create(instance)
        return instance

    def update(self, instance, validated_data: dict):
        with transaction.atomic():
            before = self._audit_snapshot(instance)
            instance = super().update(instance, validated_data)
            self._audit_after_update(instance, before)
        return instance


class HRLeaveApplicationListSerializer(serializers.Serializer):
    """HR organization-wide row for a submitted (finalized) application."""

    def to_representation(self, instance) -> dict:
        from workflows.serializers import PendingApplicationSerializer

        return PendingApplicationSerializer(instance=instance).data


class HRLeaveApplicationSerializer(serializers.Serializer):
    """HR read of one submitted application with its history roll-up.

    Reuses the pending-application field resolution plus the existing
    supporting-document and reassignment serializer shapes, and appends the
    application's audit timeline (oldest first) — all read from
    :class:`AuditEvent`.
    """

    def to_representation(self, instance) -> dict:
        # Imported lazily to avoid a serializer import cycle (audit ↔ workflow).
        from leave.serializers import SupportingDocumentSerializer
        from workflows.serializers import (
            PendingApplicationSerializer,
            ReassignmentSerializer,
        )

        data = PendingApplicationSerializer(instance=instance).data
        data["documents"] = SupportingDocumentSerializer(
            instance.documents.order_by("uploaded_at"), many=True
        ).data
        data["reassignments"] = ReassignmentSerializer(
            instance.reassignments.all(), many=True
        ).data
        data["audit_entries"] = AuditEventSerializer(
            events_for_target(instance), many=True
        ).data
        return data