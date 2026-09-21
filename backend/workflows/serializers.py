from django.db import transaction
from rest_framework import serializers

from audit.models import AuditEntry
from audit.serializers import AuditedModelSerializer
from leave.models import LeaveApplication, LeaveType
from users.models import User

from .models import APPROVER_ROLE_CODES, Delegation, Reassignment, Workflow, WorkflowStage
from .services import (
    ReassignmentError,
    StageSequenceError,
    is_approver_user,
    normalize_stage_sequence,
    open_request_exists,
    reassign_application,
    validate_workflow_for_activation,
)


class WorkflowStageSerializer(serializers.ModelSerializer):
    """One step in a workflow's approval sequence."""

    class Meta:
        model = WorkflowStage
        fields = ["id", "order", "approver_role"]

    def validate_approver_role(self, value: str) -> str:
        if value not in APPROVER_ROLE_CODES:
            raise serializers.ValidationError("Select a valid approver role.")
        return value

    def validate_order(self, value: int) -> int:
        if value is None or value < 1:
            raise serializers.ValidationError(
                "Stage order must be a positive whole number."
            )
        return value


class WorkflowSerializer(AuditedModelSerializer):
    """HR-facing serializer for approval workflows and their ordered stages."""

    target_type = AuditEntry.TargetType.WORKFLOW

    stages = WorkflowStageSerializer(many=True)
    state = serializers.CharField(read_only=True)

    class Meta:
        model = Workflow
        fields = [
            "id",
            "name",
            "employee_category",
            "department",
            "effective_from",
            "is_active",
            "state",
            "stages",
        ]

    def _effective_is_active(self, attrs: dict) -> bool:
        if "is_active" in attrs:
            return bool(attrs["is_active"])
        if self.instance is not None:
            return bool(self.instance.is_active)
        return True

    def validate(self, attrs: dict) -> dict:
        name = self._value(attrs, "name")
        name = (name or "").strip()
        if not name:
            raise serializers.ValidationError({"name": "Name is required."})
        attrs["name"] = name

        category = self._value(attrs, "employee_category")
        attrs["employee_category"] = (category or "").strip()

        department = self._value(attrs, "department")
        attrs["department"] = (department or "").strip()

        stages = attrs.get("stages")
        if stages is None:
            raise serializers.ValidationError(
                {"stages": "Approval stages are required."}
            )
        try:
            normalized_stages = normalize_stage_sequence(stages)
        except StageSequenceError as exc:
            raise serializers.ValidationError({exc.field: [exc.message]})

        queryset = Workflow.objects.all()
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.filter(name=name).exists():
            raise serializers.ValidationError(
                {"name": "A workflow with this name already exists."}
            )

        effective_from = self._value(attrs, "effective_from")
        if effective_from is not None and self._effective_is_active(attrs):
            self._validate_activation(
                normalized_stages,
                (attrs["employee_category"], attrs["department"]),
            )

        return attrs

    def _validate_activation(
        self, stages: list[dict], scope: tuple[str, str]
    ) -> None:
        workflow_pk = self.instance.pk if self.instance is not None else None
        issues = validate_workflow_for_activation(workflow_pk, scope, stages)
        if not issues:
            return
        field_errors: dict[str, list[str]] = {}
        details: list[str] = []
        for issue in issues:
            if issue.field is None:
                details.append(issue.message)
            else:
                field_errors.setdefault(issue.field, []).append(issue.message)
        errors: dict[str, object] = dict(field_errors)
        if details:
            errors["detail"] = " ".join(details)
        raise serializers.ValidationError(errors)

    def _audit_snapshot(self, instance: Workflow) -> dict:
        return {
            "name": instance.name,
            "employee_category": instance.employee_category,
            "department": instance.department,
            "effective_from": instance.effective_from,
            "is_active": instance.is_active,
            "stages": list(
                instance.stages.order_by("order").values_list(
                    "approver_role", flat=True
                )
            ),
        }

    def _audit_target_summary(self, instance: Workflow) -> str:
        scope = instance.employee_category or "All categories"
        if instance.department:
            scope += f" / {instance.department}"
        return f"{instance.name} ({scope})"

    def create(self, validated_data: dict) -> Workflow:
        stages = validated_data.pop("stages", [])
        with transaction.atomic():
            workflow = Workflow.objects.create(**validated_data)
            self._replace_stages(workflow, stages)
            self._audit_after_create(workflow)
        return workflow

    def update(self, instance, validated_data: dict) -> Workflow:
        stages = validated_data.pop("stages", [])
        before = self._audit_snapshot(instance)
        with transaction.atomic():
            # Bypass the automated audited update so the replacement stages are
            # in place before the "after" snapshot is taken.
            instance = serializers.ModelSerializer.update(self, instance, validated_data)
            self._replace_stages(instance, stages)
            self._audit_after_update(instance, before)
        return instance

    def _replace_stages(self, workflow: Workflow, stages: list[dict]) -> None:
        workflow.stages.all().delete()
        for stage in normalize_stage_sequence(stages):
            WorkflowStage.objects.create(workflow=workflow, **stage)


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
        request = self.context.get("request")
        validated_data["requested_by"] = getattr(request, "user", None)
        return super().create(validated_data)


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
    """Read-only representation of one pending (submitted) leave application."""

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
        }