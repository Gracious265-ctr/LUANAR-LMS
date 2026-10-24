"""Serializers for the calendar configuration rows (§3.7).

Creates and updates are audited through ``AuditedModelSerializer`` exactly like
the other HR-configuration serializers, so each write lands one append-only
``AuditEntry`` in the same transaction as the row it changed.
"""

from rest_framework import serializers

from audit.models import AuditEntry
from audit.serializers import AuditedModelSerializer

from .models import WEEKDAY_FIELDS, CalendarEvent, Holiday, WorkingDayPattern

__all__ = [
    "CalendarEventSerializer",
    "HolidaySerializer",
    "WorkingDayPatternSerializer",
]


class WorkingDayPatternSerializer(AuditedModelSerializer):
    """The seven weekday flags; saved as the single institution-wide row."""

    target_type = AuditEntry.TargetType.WORKING_DAY_PATTERN
    audit_fields = list(WEEKDAY_FIELDS)

    class Meta:
        model = WorkingDayPattern
        fields = list(WEEKDAY_FIELDS)

    def validate(self, attrs: dict) -> dict:
        if not any(self._value(attrs, field) for field in WEEKDAY_FIELDS):
            raise serializers.ValidationError(
                "At least one weekday must be a working day."
            )
        return attrs


class HolidaySerializer(AuditedModelSerializer):
    """HR-facing serializer for public/institutional holidays (§3.5)."""

    target_type = AuditEntry.TargetType.PUBLIC_HOLIDAY
    audit_fields = [
        "name",
        "date",
        "is_recurring",
        "observed_shift",
        "financial_year_id",
    ]

    class Meta:
        model = Holiday
        fields = [
            "id",
            "name",
            "date",
            "is_recurring",
            "observed_shift",
            "financial_year",
        ]

    def validate(self, attrs: dict) -> dict:
        name = (self._value(attrs, "name") or "").strip()
        if not name:
            raise serializers.ValidationError({"name": "Name is required."})
        attrs["name"] = name

        holiday_date = self._value(attrs, "date")
        if holiday_date is None:
            raise serializers.ValidationError({"date": "Date is required."})

        financial_year = self._value(attrs, "financial_year")
        queryset = Holiday.objects.all()
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.filter(date=holiday_date, financial_year=financial_year).exists():
            raise serializers.ValidationError(
                {
                    "date": (
                        "A holiday on this date already exists for the selected "
                        "financial year."
                    )
                }
            )

        return attrs


class CalendarEventSerializer(AuditedModelSerializer):
    """HR-facing serializer for institutional calendar events (§3.6)."""

    target_type = AuditEntry.TargetType.CALENDAR_EVENT
    audit_fields = [
        "title",
        "start_date",
        "end_date",
        "description",
        "affects_leave_calculation",
    ]

    class Meta:
        model = CalendarEvent
        fields = [
            "id",
            "title",
            "start_date",
            "end_date",
            "description",
            "affects_leave_calculation",
        ]

    def validate(self, attrs: dict) -> dict:
        title = (self._value(attrs, "title") or "").strip()
        if not title:
            raise serializers.ValidationError({"title": "Title is required."})
        attrs["title"] = title

        start_date = self._value(attrs, "start_date")
        end_date = self._value(attrs, "end_date")
        if start_date is None:
            raise serializers.ValidationError({"start_date": "Start date is required."})
        if end_date is None:
            raise serializers.ValidationError({"end_date": "End date is required."})
        if end_date < start_date:
            raise serializers.ValidationError(
                {"end_date": "End date must not be before start date."}
            )

        return attrs
