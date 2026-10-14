<<<<<<< HEAD
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
=======
from django.db import transaction
from rest_framework import serializers

from audit.models import AuditEntry

from .services import (
    SYSTEM_ACTOR_NAME,
    actor_display_name,
    changed_fields,
    current_actor,
    record_audit,
)

__all__ = [
    "AuditedModelSerializer",
    "AuditEntrySerializer",
    "FinalizedApplicationListSerializer",
    "HRLeaveApplicationSerializer",
    "SYSTEM_ACTOR_NAME",
]


class AuditedModelSerializer(serializers.ModelSerializer):
    """ModelSerializer that records an audit entry on create/update.

    Subclasses declare ``target_type`` (the audit ``target_type`` code) and
    ``audit_fields`` (the fields snapshotted for the before/after values), and
    optionally override ``_audit_snapshot`` (e.g. to include nested user or
    stage columns) and ``_audit_target_summary``. Serializers that override
>>>>>>> feature/plans-teams
    ``create``/``update`` for their own transaction boundaries call the
    ``_audit_after_create`` / ``_audit_after_update`` hooks directly.
    """

<<<<<<< HEAD
    audit_prefix: str = ""
    audit_fields: list[str] = []

=======
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

>>>>>>> feature/plans-teams
    # -- Auditing -----------------------------------------------------------

    def _audit_snapshot(self, instance) -> dict:
        return {field: getattr(instance, field) for field in self.audit_fields}

<<<<<<< HEAD
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
=======
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
>>>>>>> feature/plans-teams

    # -- Default create/update ---------------------------------------------

    def create(self, validated_data: dict):
        with transaction.atomic():
            instance = super().create(validated_data)
            self._audit_after_create(instance)
        return instance

    def update(self, instance, validated_data: dict):
<<<<<<< HEAD
        with transaction.atomic():
            before = self._audit_snapshot(instance)
=======
        before = self._audit_snapshot(instance)
        with transaction.atomic():
>>>>>>> feature/plans-teams
            instance = super().update(instance, validated_data)
            self._audit_after_update(instance, before)
        return instance


<<<<<<< HEAD
class HRLeaveApplicationListSerializer(serializers.Serializer):
    """HR organization-wide row for a submitted (finalized) application."""
=======
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
        return actor_display_name(obj.actor)


class FinalizedApplicationListSerializer(serializers.Serializer):
    """Light list representation of finalized applications.

    Deliberately excludes the history roll-up (documents/reassignments/audit
    entries); only the row shape is serialized. Accepts a ``leave_type_names``
    mapping in the serializer context so the whole page resolves leave-type
    names in one query instead of one per row.
    """
>>>>>>> feature/plans-teams

    def to_representation(self, instance) -> dict:
        from workflows.serializers import PendingApplicationSerializer

<<<<<<< HEAD
        return PendingApplicationSerializer(instance=instance).data
=======
        return PendingApplicationSerializer(
            instance=instance, context=self.context
        ).data
>>>>>>> feature/plans-teams


class HRLeaveApplicationSerializer(serializers.Serializer):
    """HR read of one submitted application with its history roll-up.

    Reuses the pending-application field resolution plus the existing
    supporting-document and reassignment serializer shapes, and appends the
<<<<<<< HEAD
    application's audit timeline (oldest first) — all read from
    :class:`AuditEvent`.
=======
    application's audit timeline (oldest first).
>>>>>>> feature/plans-teams
    """

    def to_representation(self, instance) -> dict:
        # Imported lazily to avoid a serializer import cycle (audit ↔ workflow).
        from leave.serializers import SupportingDocumentSerializer
        from workflows.serializers import (
            PendingApplicationSerializer,
            ReassignmentSerializer,
        )

        data = PendingApplicationSerializer(instance=instance).data
<<<<<<< HEAD
        data["documents"] = SupportingDocumentSerializer(
            instance.documents.order_by("uploaded_at"), many=True
        ).data
        data["reassignments"] = ReassignmentSerializer(
            instance.reassignments.all(), many=True
        ).data
        data["audit_entries"] = AuditEventSerializer(
            events_for_target(instance), many=True
=======
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
>>>>>>> feature/plans-teams
        ).data
        return data