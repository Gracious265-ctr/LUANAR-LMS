"""Plan API serializers (Unit 25).

Write path only: read payloads are built by :mod:`.payloads`. Validation here
is deliberately light — the heavy rules (duration, eligibility, balance with
reservations, single financial year, workflow readiness) run in the plan
service at submission, matching how leave applications validate at submit.
"""

from __future__ import annotations

from datetime import date

from rest_framework import serializers

from .models import LeaveDayPlan, PlanApprovalDecision, PlanSettings


class PlanBlockInputSerializer(serializers.Serializer):
    leave_type_id = serializers.IntegerField(min_value=1)
    start_date = serializers.DateField()
    end_date = serializers.DateField()

    def validate(self, attrs):
        if attrs["end_date"] < attrs["start_date"]:
            raise serializers.ValidationError(
                {"end_date": "The block must not end before it starts."}
            )
        return attrs


class PlanCreateSerializer(serializers.Serializer):
    period_start = serializers.DateField()
    period_end = serializers.DateField()
    blocks = PlanBlockInputSerializer(many=True, allow_empty=False)

    def validate(self, attrs):
        if attrs["period_end"] < attrs["period_start"]:
            raise serializers.ValidationError(
                {"period_end": "The plan period must not end before it starts."}
            )
        if len(attrs["blocks"]) > 30:
            raise serializers.ValidationError(
                {"blocks": "A plan can contain at most 30 blocks."}
            )
        return attrs


class PlanSubmitSerializer(serializers.Serializer):
    pass


class PlanDecisionInputSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=PlanApprovalDecision.Action.choices)
    comment = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=1000,
        trim_whitespace=True,
    )
    stage_version = serializers.IntegerField(min_value=1)


class PlanSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanSettings
        fields = ["confirmation_lead_days"]

    def validate_confirmation_lead_days(self, value):
        if value < 1 or value > 60:
            raise serializers.ValidationError(
                "Must be between 1 and 60 days."
            )
        return value