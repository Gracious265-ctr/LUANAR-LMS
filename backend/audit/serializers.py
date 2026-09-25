from django.db import transaction
from rest_framework import serializers

from audit.models import AuditEntry

from .services import changed_fields, current_actor, record_audit

#: Displayed in place of a person when an entry has no human actor.
SYSTEM_ACTOR_NAME = "System"


class AuditedModelSerializer(serializers.ModelSerializer):
    """ModelSerializer that records an audit entry on create/update.

    Subclasses declare ``target_type`` (the audit ``target_type`` code) and
    ``audit_fields`` (the fields snapshotted for the before/after values), and
    optionally override ``_audit_snapshot`` (e.g. to include nested user or
    stage columns) and ``_audit_target_summary``. Serializers that override
    ``create``/``update`` for their own transaction boundaries call the
    ``_audit_after_create`` / ``_audit_after_update`` hooks directly.
    """

    target_type = AuditEntry.TargetType.RECORD
    audit_fields: list[str] = []

    def _value(self, attrs: dict, field: str):
        """The submitted value for ``field``, falling back to the instance value.

        Required so PATCH validates against the fully-merged state of a
        partial update rather than treating absent keys as missing fields.
        """
        if field in attrs:
            return attrs[field]
        return getattr(self.instance, field, None)

    # -- Auditing -----------------------------------------------------------

    def _audit_snapshot(self, instance) -> dict:
        return {field: getattr(instance, field) for field in self.audit_fields}

    def _audit_target_summary(self, instance) -> str:
        return str(instance)

    def _record_audit(
        self, instance, *, action: str, before: dict | None, after: dict
    ) -> None:
        actor = current_actor(self)
        if actor is None:
            return
        detail = {"before": None, "after": after}
        if before is not None:
            detail = changed_fields(before, after)
        record_audit(
            actor=actor,
            action=action,
            target_type=self.target_type,
            target_id=instance.pk,
            target_summary=self._audit_target_summary(instance),
            detail=detail,
        )

    def _audit_after_create(self, instance) -> None:
        self._record_audit(
            instance,
            action=AuditEntry.Action.CREATED,
            before=None,
            after=self._audit_snapshot(instance),
        )

    def _audit_after_update(self, instance, before: dict) -> None:
        self._record_audit(
            instance,
            action=AuditEntry.Action.UPDATED,
            before=before,
            after=self._audit_snapshot(instance),
        )

    # -- Default create/update ---------------------------------------------

    def create(self, validated_data: dict):
        with transaction.atomic():
            instance = super().create(validated_data)
            self._audit_after_create(instance)
        return instance

    def update(self, instance, validated_data: dict):
        before = self._audit_snapshot(instance)
        with transaction.atomic():
            instance = super().update(instance, validated_data)
            self._audit_after_update(instance, before)
        return instance


class AuditEntrySerializer(serializers.ModelSerializer):
    """Read-only HR-facing serializer for audit-log entries."""

    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = AuditEntry
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
            "created_at",
        ]
        read_only_fields = fields

    def get_actor_name(self, obj: AuditEntry) -> str:
        """The human actor's name, or ``System`` for a system-generated entry.

        A null ``actor`` means the action was performed by the system rather
        than a person (Unit 23b's background document render), which HR should
        be able to read as such rather than see a blank cell.
        """
        if obj.actor_id is None:
            return SYSTEM_ACTOR_NAME
        return obj.actor.get_full_name()


class FinalizedApplicationListSerializer(serializers.Serializer):
    """Light list representation of finalized applications.

    Deliberately excludes the history roll-up (documents/reassignments/audit
    entries); only the row shape is serialized. Accepts a ``leave_type_names``
    mapping in the serializer context so the whole page resolves leave-type
    names in one query instead of one per row.
    """

    def to_representation(self, instance) -> dict:
        from workflows.serializers import PendingApplicationSerializer

        return PendingApplicationSerializer(
            instance=instance, context=self.context
        ).data


class HRLeaveApplicationSerializer(serializers.Serializer):
    """HR read of one submitted application with its history roll-up.

    Reuses the pending-application field resolution plus the existing
    supporting-document and reassignment serializer shapes, and appends the
    application's audit timeline (oldest first).
    """

    def to_representation(self, instance) -> dict:
        # Imported lazily to avoid a serializer import cycle (audit ↔ workflow).
        from leave.serializers import SupportingDocumentSerializer
        from workflows.serializers import (
            PendingApplicationSerializer,
            ReassignmentSerializer,
        )

        data = PendingApplicationSerializer(instance=instance).data
        # Unit 23b: the audit view gates the approved-document affordance on the
        # status, and an approved document exists only for an approved leave.
        data["status"] = instance.status
        data["documents"] = SupportingDocumentSerializer(
            instance.documents.all(), many=True
        ).data
        data["reassignments"] = ReassignmentSerializer(
            instance.reassignments.order_by("-created_at"), many=True
        ).data
        data["audit_entries"] = AuditEntrySerializer(
            AuditEntry.objects.filter(
                target_type=AuditEntry.TargetType.APPLICATION,
                target_id=str(instance.pk),
            ).order_by("created_at"),
            many=True,
        ).data
        return data