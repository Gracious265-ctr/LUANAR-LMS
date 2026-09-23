"""Input serializers for the Unit 17 resubmission API (explicit whitelists)."""

from rest_framework import serializers


class SaveChangesSerializer(serializers.Serializer):
    """``PATCH /api/applications/{id}/resubmission/`` body.

    ``row_version`` is the optimistic-concurrency token the client last saw;
    the service raises a 409 when it no longer matches.
    """

    leave_type_id = serializers.IntegerField()
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    reason = serializers.CharField(allow_blank=True)
    row_version = serializers.IntegerField(min_value=1)


class RowVersionSerializer(serializers.Serializer):
    """Minimal body used by document operations and the resubmit action."""

    row_version = serializers.IntegerField(min_value=1)


class DocumentRowVersionSerializer(serializers.Serializer):
    """``row_version`` carried as a form field on multipart uploads."""

    row_version = serializers.IntegerField(min_value=1)