"""Serializers for the leave validation and submission endpoints (Unit 14)."""

from rest_framework import serializers


class ValidateLeaveSerializer(serializers.Serializer):
    """Input for the stateless ``POST /api/leave/validate/`` endpoint.

    ``draft_id`` is optional and must belong to the caller (enforced by the
    view as a 404). Any ``employee_id`` sent by the client is deliberately not
    a field, so it is ignored (D10/12.1).
    """

    leave_type_id = serializers.IntegerField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    draft_id = serializers.UUIDField(required=False)
    application_id = serializers.UUIDField(required=False)