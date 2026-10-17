"""Serializers for Leave Plans (refinement unit 04).

A plan is authored by its owner and read-only to the rest of the world, so these
serializers never need to expose a workflow: there is nothing for anyone else to
decide. The write serializer validates plannable types and a sane date range; the
read serializer flattens the UUIDs into a stable shape the client can render.
"""

from __future__ import annotations

from rest_framework import serializers

from leave.models import FinancialYear, LeaveType

from .models import LeavePlan


class LeavePlanSerializer(serializers.ModelSerializer):
    """Read serializer for a single plan (owner or team-calendar row)."""

    employee_name = serializers.SerializerMethodField()
    leave_type_name = serializers.CharField(source="leave_type.name", read_only=True)
    leave_type_id = serializers.PrimaryKeyRelatedField(
        source="leave_type", read_only=True
    )
    financial_year_label = serializers.SerializerMethodField()

    class Meta:
        model = LeavePlan
        fields = [
            "id",
            "employee_name",
            "leave_type_id",
            "leave_type_name",
            "financial_year_label",
            "planned_start_date",
            "planned_end_date",
            "notes",
            "status",
            "notified_at",
            "follow_up_sent_at",
            "converted_application",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_employee_name(self, obj) -> str:
        return obj.employee.get_full_name() or obj.employee.username

    def get_financial_year_label(self, obj) -> str:
        from leave.services import financial_year_label

        return financial_year_label(obj.financial_year)


class LeavePlanWriteSerializer(serializers.ModelSerializer):
    """Create/update serializer for an owner's own plan."""

    employee = serializers.PrimaryKeyRelatedField(read_only=True)
    leave_type = serializers.PrimaryKeyRelatedField(queryset=LeaveType.objects.all())
    # Optional: the covering financial year is derived from the dates, falling
    # back to the active year, so the client never has to know which one it is.
    financial_year = serializers.PrimaryKeyRelatedField(
        queryset=FinancialYear.objects.all(), required=False
    )

    class Meta:
        model = LeavePlan
        fields = [
            "id",
            "employee",
            "leave_type",
            "financial_year",
            "planned_start_date",
            "planned_end_date",
            "notes",
            "status",
            "converted_application",
        ]
        read_only_fields = [
            "id",
            "employee",
            "status",
            "converted_application",
        ]

    def validate(self, attrs):
        start = attrs.get(
            "planned_start_date",
            getattr(self.instance, "planned_start_date", None),
        )
        end = attrs.get(
            "planned_end_date", getattr(self.instance, "planned_end_date", None)
        )
        if start and end and end < start:
            raise serializers.ValidationError(
                {"planned_end_date": "The end date cannot be before the start date."}
            )

        leave_type = attrs.get("leave_type", getattr(self.instance, "leave_type", None))
        if leave_type is not None and not leave_type.plannable:
            raise serializers.ValidationError(
                {
                    "leave_type": f"{leave_type.name} cannot be planned. "
                    "Choose a leave type that allows planning."
                }
            )

        if start is not None and end is not None:
            covering = FinancialYear.objects.filter(
                start_date__lte=start, end_date__gte=end
            ).order_by("-start_date").first()
            if covering is not None:
                attrs["financial_year"] = covering
        return attrs


class PlanScopeSerializer(serializers.Serializer):
    """One calendar scope token the requester may select."""

    id = serializers.CharField(source="token")
    label = serializers.CharField()


class PlanApplicationSerializer(serializers.Serializer):
    """Response body of ``POST /plans/{id}/apply/``."""

    application_id = serializers.UUIDField()
