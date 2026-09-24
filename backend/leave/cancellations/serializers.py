"""Input serializers for the Unit 18 cancellation API.

Output payloads are built by the views (mirroring the Unit 16 review pattern);
these serializers validate what the client may send. **Unknown fields are
refused** (section 3.8): a client-supplied employee/approver id would otherwise
be silently ignored by DRF.
"""

from rest_framework import serializers


class RejectsUnknownFields:
    """Mixin that 400s on any field not declared on the serializer."""

    def validate(self, attrs):
        unknown = set(self.initial_data or {}) - set(self.fields)
        if unknown:
            raise serializers.ValidationError(
                {field: ["This field is not allowed."] for field in sorted(unknown)}
            )
        return attrs


class SubmitCancellationSerializer(RejectsUnknownFields, serializers.Serializer):
    """Body for ``POST /api/applications/{id}/cancel/``."""

    reason = serializers.CharField()
    confirm = serializers.BooleanField()
    expected_action = serializers.ChoiceField(choices=["withdraw", "request"])


class CancellationDecisionSerializer(RejectsUnknownFields, serializers.Serializer):
    """Body for ``POST /api/approvals/cancellations/{request_id}/decision/``."""

    decision = serializers.ChoiceField(choices=["approve", "reject"])
    comment = serializers.CharField(required=False, allow_blank=True)
    stage_version = serializers.IntegerField(min_value=1)