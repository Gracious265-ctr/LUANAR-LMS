"""Approvals execution serializers: delegations and reassignments."""

from django.db import IntegrityError, transaction
from rest_framework import serializers

from audit.models import AuditEntry
from audit.services import changed_fields, record_audit
from leave.models import LeaveApplication
from leave_types.models import LeaveType
from users.models import User

from roles.services import approver_role_codes_for, is_approver_user

from .models import Delegation, Reassignment
from .services import (
    ReassignmentError,
    acting_approver_identity,
    delegation_summary,
    open_request_exists,
    reassign_application,
)


def _record_delegation_created_audit(delegation: Delegation) -> None:
    """Audit a delegation request the moment it exists.

    The other three delegation actions are audited by
    ``workflows.services._record_delegation_audit``; creation is a serializer
    concern, so it is recorded here in the same transaction. Without it a
    request would appear in the trail only once HR decided on it, and a request
    that was never decided would leave no trace at all.
    """
    if delegation.requested_by_id is None:
        return
    record_audit(
        actor=delegation.requested_by,
        action=AuditEntry.Action.CREATED,
        target_type=AuditEntry.TargetType.DELEGATION,
        target_id=delegation.pk,
        target_summary=delegation_summary(delegation),
        detail=changed_fields(
            {},
            {
                "status": delegation.status,
                "delegate_id": delegation.delegate_id,
                "starts_on": delegation.starts_on,
                "ends_on": delegation.ends_on,
            },
        ),
        reason=delegation.request_reason,
    )


class DelegationSerializer(serializers.ModelSerializer):
    """HR/approver-facing serializer for delegation requests."""

    approver = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False
    )
    delegate = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False, allow_null=True
    )
    approver_name = serializers.SerializerMethodField()
    approver_role = serializers.SerializerMethodField()
    delegate_name = serializers.SerializerMethodField()
    requested_by_name = serializers.SerializerMethodField()
    state = serializers.CharField(read_only=True)

    class Meta:
        model = Delegation
        fields = [
            "id",
            "approver",
            "approver_name",
            "approver_role",
            "delegate",
            "delegate_name",
            "starts_on",
            "ends_on",
            "request_reason",
            "requested_by",
            "requested_by_name",
            "decision_reason",
            "decided_by",
            "decided_at",
            "status",
            "state",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "requested_by",
            "decision_reason",
            "decided_by",
            "decided_at",
            "status",
            "created_at",
            "updated_at",
        ]

    def get_approver_name(self, obj: Delegation) -> str:
        return obj.approver.get_full_name()

    def get_approver_role(self, obj: Delegation) -> str:
        """The approver's primary role code, from the role graph.

        ``User.role`` is only employee/approver/hr, so it cannot name the
        position somebody approves in. The first active holding supplies the
        label, falling back to the system role for HR and for a user whose
        holdings have all been removed.
        """
        codes = [
            code for code in approver_role_codes_for(obj.approver)
        ]
        if codes:
            return codes[0]
        return obj.approver.role

    def get_delegate_name(self, obj: Delegation) -> str:
        return obj.delegate.get_full_name() if obj.delegate else ""

    def get_requested_by_name(self, obj: Delegation) -> str:
        return obj.requested_by.get_full_name()

    def validate(self, attrs: dict) -> dict:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        is_hr = getattr(user, "role", None) == User.Role.HR

        if is_hr:
            approver = attrs.get("approver")
            if approver is None:
                raise serializers.ValidationError(
                    {"approver": "Select the approver this delegation is for."}
                )
            if not is_approver_user(approver):
                raise serializers.ValidationError(
                    {"approver": "Select an active user with an approver role."}
                )
        else:
            approver = user
            attrs["approver"] = approver

        delegate = attrs.get("delegate")
        if delegate is not None:
            if not is_approver_user(delegate):
                raise serializers.ValidationError(
                    {"delegate": "Select an active user with an approver role."}
                )
            if delegate.pk == approver.pk:
                raise serializers.ValidationError(
                    {"delegate": "The delegate must be a different person from the approver."}
                )

        starts_on = attrs.get("starts_on")
        ends_on = attrs.get("ends_on")
        if starts_on is not None and ends_on is not None and ends_on < starts_on:
            raise serializers.ValidationError(
                {"ends_on": "End date must be on or after the start date."}
            )

        if approver is not None and open_request_exists(approver.pk):
            raise serializers.ValidationError(
                {"approver": "This approver already has an open delegation request."}
            )

        return attrs

    def create(self, validated_data: dict) -> Delegation:
        from notifications.delegations import DELEGATION_REQUESTED, notify_delegation

        request = self.context.get("request")
        validated_data["requested_by"] = getattr(request, "user", None)
        try:
            # The nested atomic block is a savepoint: a lost race against
            # ``one_open_request_per_approver`` rolls back cleanly instead of
            # poisoning the outer transaction, so the friendly 400 survives.
            with transaction.atomic():
                delegation = super().create(validated_data)
                _record_delegation_created_audit(delegation)
                notify_delegation(delegation.pk, DELEGATION_REQUESTED)
        except IntegrityError:
            raise serializers.ValidationError(
                {"approver": "This approver already has an open delegation request."}
            )
        return delegation


class DelegationActionSerializer(serializers.Serializer):
    """Payload for the HR approve / reject / cancel delegation actions."""

    decision_reason = serializers.CharField(required=False, allow_blank=True)
    delegate = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False, allow_null=True
    )

    def validate_decision_reason(self, value: str) -> str:
        return (value or "").strip()


class ReassignmentSerializer(serializers.ModelSerializer):
    """HR-facing serializer for emergency reassignment records."""

    application = serializers.PrimaryKeyRelatedField(
        queryset=LeaveApplication.objects.all()
    )
    to_approver = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    reference_number = serializers.SerializerMethodField()
    employee = serializers.SerializerMethodField()
    employee_name = serializers.SerializerMethodField()
    from_approver = serializers.PrimaryKeyRelatedField(read_only=True)
    from_approver_name = serializers.SerializerMethodField()
    to_approver_name = serializers.SerializerMethodField()
    decided_by = serializers.PrimaryKeyRelatedField(read_only=True)
    decided_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Reassignment
        fields = [
            "id",
            "application",
            "reference_number",
            "employee",
            "employee_name",
            "from_approver",
            "from_approver_name",
            "to_approver",
            "to_approver_name",
            "reason",
            "decided_by",
            "decided_by_name",
            "created_at",
        ]
        read_only_fields = [
            "created_at",
        ]

    def get_reference_number(self, obj: Reassignment) -> str:
        return obj.application.reference_number or ""

    def get_employee(self, obj: Reassignment) -> int:
        return obj.application.employee_id

    def get_employee_name(self, obj: Reassignment) -> str:
        return obj.application.employee.get_full_name()

    def get_from_approver_name(self, obj: Reassignment) -> str:
        return obj.from_approver.get_full_name() if obj.from_approver else ""

    def get_to_approver_name(self, obj: Reassignment) -> str:
        return obj.to_approver.get_full_name()

    def get_decided_by_name(self, obj: Reassignment) -> str:
        return obj.decided_by.get_full_name()

    def validate_reason(self, value: str) -> str:
        return (value or "").strip()

    def create(self, validated_data: dict) -> Reassignment:
        request = self.context.get("request")
        try:
            return reassign_application(
                application=validated_data["application"],
                to_approver=validated_data["to_approver"],
                actor=getattr(request, "user", None),
                reason=validated_data.get("reason", ""),
            )
        except ReassignmentError as exc:
            raise serializers.ValidationError({exc.field: [exc.message]})


class PendingApplicationSerializer(serializers.Serializer):
    """Read-only representation of one pending (submitted) leave application.

    Reports both the *responsible* approver (the ``current_approver`` spine) and
    the *acting* approver (Unit 21 routing: the active delegate when one covers
    them). HR has to see the difference, because reassigning an application to
    an approver who is themselves away moves the spine without changing who
    actually acts — the queue would otherwise read as a successful intervention
    that quietly did nothing.
    """

    def to_representation(self, instance: LeaveApplication) -> dict:
        leave_type_name = ""
        if instance.leave_type_id:
            names = self.context.get("leave_type_names")
            if names is not None:
                leave_type_name = names.get(instance.leave_type_id, "")
            else:
                leave_type = LeaveType.objects.filter(
                    pk=instance.leave_type_id
                ).first()
                if leave_type is not None:
                    leave_type_name = leave_type.name
        current = instance.current_approver
        acting_id, acting_name = self._acting_approver(instance)
        if current is None:
            is_delegated = acting_id is not None
        else:
            is_delegated = acting_id is not None and acting_id != current.pk
        return {
            "id": instance.id,
            "reference_number": instance.reference_number or "",
            "employee": instance.employee_id,
            "employee_name": instance.employee.get_full_name(),
            "leave_type_name": leave_type_name,
            "start_date": instance.start_date,
            "end_date": instance.end_date,
            "calculated_days": instance.calculated_days,
            "reason": instance.reason,
            "submitted_at": instance.submitted_at,
            "current_approver": current.pk if current else None,
            "current_approver_name": current.get_full_name() if current else "",
            "acting_approver": acting_id,
            "acting_approver_name": acting_name,
            "is_delegated": is_delegated,
        }

    def _acting_approver(
        self, instance: LeaveApplication
    ) -> tuple[int | None, str]:
        """``(acting_approver_id, acting_approver_name)`` for one application.

        Prefers the page-level map the intervention queue resolves in bulk, so a
        whole page costs one delegation query plus one user query instead of two
        per row, and falls back to resolving this one application directly.
        """
        resolved = self.context.get("acting_approver_map")
        if resolved is not None and instance.pk in resolved:
            return resolved[instance.pk]
        return acting_approver_identity(instance)


