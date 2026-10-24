"""Minimal admin for calendar configuration (HR-facing, view/edit light).

The app is configured in code; the API is the canonical write path for all
writes gated by the calendar access policy. The admin here mirrors the three
rows for convenience and to prevent accidental deletes — FinancialYear is owned
by leave but viewable; WorkingDayPattern/Event/Holiday are owned here.
"""

from django import forms
from django.contrib import admin

from .models import CalendarEvent, Holiday, WorkingDayPattern
from .serializers import WorkingDayPatternSerializer


class HolidayAdminForm(forms.ModelForm):
    class Meta:
        model = Holiday
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        # Keep a lightweight mirror of the serializer's uniqueness check for admin.
        holiday_date = cleaned.get("date")
        financial_year = cleaned.get("financial_year")
        if holiday_date is not None:
            queryset = Holiday.objects.all()
            if self.instance.pk is not None:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.filter(date=holiday_date, financial_year=financial_year).exists():
                from django.core.exceptions import ValidationError

                raise ValidationError(
                    {
                        "date": "A holiday on this date already exists for the selected financial year."
                    }
                )
        return cleaned


class WorkingDayPatternAdminForm(forms.ModelForm):
    class Meta:
        model = WorkingDayPattern
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        # Reuse the serializer's "at least one weekday" rule.
        data = {
            field: cleaned.get(field)
            for field in WorkingDayPatternSerializer.audit_fields
        }
        ser = WorkingDayPatternSerializer(
            instance=self.instance, data=data, partial=True
        )
        ser.is_valid(raise_exception=True)
        return cleaned


class CalendarEventAdminForm(forms.ModelForm):
    class Meta:
        model = CalendarEvent
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        start_date = cleaned.get("start_date")
        end_date = cleaned.get("end_date")
        if start_date and end_date and end_date < start_date:
            from django.core.exceptions import ValidationError

            raise ValidationError({"end_date": "End date must not be before start date."})
        return cleaned


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    form = HolidayAdminForm
    list_display = (
        "name",
        "date",
        "is_recurring",
        "observed_shift",
        "financial_year",
    )
    list_filter = ("is_recurring", "observed_shift", "financial_year")
    search_fields = ("name",)
    ordering = ("-date",)


@admin.register(WorkingDayPattern)
class WorkingDayPatternAdmin(admin.ModelAdmin):
    form = WorkingDayPatternAdminForm
    list_display = (
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    )


@admin.register(CalendarEvent)
class CalendarEventAdmin(admin.ModelAdmin):
    form = CalendarEventAdminForm
    list_display = ("title", "start_date", "end_date", "affects_leave_calculation")
    list_filter = ("affects_leave_calculation",)
    search_fields = ("title",)
    ordering = ("-start_date",)


# FinancialYear is managed by leave; show a read-only listing here without
# creating a second admin site for the same model (would conflict). Instead,
# users can use leave admin; this module may expose via another app if needed.
# Intentionally not re-registering to avoid ModelAdminAlreadyRegistered.
pass
