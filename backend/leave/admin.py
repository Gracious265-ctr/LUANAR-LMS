from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError

from .models import (
    FinancialYear,
    GradeEntitlement,
    LeaveRule,
    LeaveType,
    PublicHoliday,
)
from .services import find_overlapping_financial_year, find_overlapping_rule


class GradeEntitlementAdminForm(forms.ModelForm):
    """Admin form that enforces the no-overlap rule as a field error."""

    class Meta:
        model = GradeEntitlement
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        grade_start = cleaned.get("grade_start")
        grade_end = cleaned.get("grade_end")
        leave_type = cleaned.get("leave_type")
        if grade_start and grade_end:
            overlapping = find_overlapping_rule(
                grade_start,
                grade_end,
                leave_type=leave_type,
                exclude_pk=self.instance.pk,
            )
            if overlapping is not None:
                raise ValidationError(
                    {
                        "grade_start": (
                            "This grade range overlaps the existing rule "
                            f"{overlapping.grade_start}–{overlapping.grade_end} "
                            f"(effective {overlapping.effective_from.isoformat()})."
                        )
                    }
                )
        return cleaned


@admin.register(GradeEntitlement)
class GradeEntitlementAdmin(admin.ModelAdmin):
    form = GradeEntitlementAdminForm
    list_display = ("grade_start", "grade_end", "days", "leave_type", "effective_from")
    search_fields = ("grade_start", "grade_end", "leave_type__name")
    list_filter = ("leave_type", "effective_from")
    ordering = ("-effective_from", "grade_start", "grade_end")

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "code")
    ordering = ("name",)


@admin.register(LeaveRule)
class LeaveRuleAdmin(admin.ModelAdmin):
    list_display = (
        "leave_type",
        "max_duration_days",
        "min_notice_days",
        "requires_supporting_document",
        "consumes_annual_entitlement",
        "effective_from",
    )
    search_fields = ("leave_type__name", "leave_type__code", "eligibility")
    list_filter = ("leave_type", "effective_from", "requires_supporting_document")
    ordering = ("-effective_from", "leave_type")


class FinancialYearAdminForm(forms.ModelForm):
    """Admin form that enforces the no-overlap rule as a field error."""

    class Meta:
        model = FinancialYear
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        start_date = cleaned.get("start_date")
        end_date = cleaned.get("end_date")
        if start_date and end_date:
            overlapping = find_overlapping_financial_year(
                start_date, end_date, exclude_pk=self.instance.pk
            )
            if overlapping is not None:
                raise ValidationError(
                    {
                        "start_date": (
                            "This period overlaps the existing financial year "
                            f"{overlapping.start_date.isoformat()} – "
                            f"{overlapping.end_date.isoformat()}."
                        )
                    }
                )
        return cleaned


@admin.register(FinancialYear)
class FinancialYearAdmin(admin.ModelAdmin):
    form = FinancialYearAdminForm
    list_display = ("start_date", "end_date", "is_active")
    list_filter = ("is_active",)
    ordering = ("-start_date",)

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if obj.is_active:
            FinancialYear.objects.filter(is_active=True).exclude(pk=obj.pk).update(
                is_active=False
            )
        super().save_model(request, obj, form, change)


class PublicHolidayAdminForm(forms.ModelForm):
    """Admin form that enforces the unique-date rule as a field error."""

    class Meta:
        model = PublicHoliday
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        holiday_date = cleaned.get("date")
        if holiday_date:
            queryset = PublicHoliday.objects.all()
            if self.instance.pk is not None:
                queryset = queryset.exclude(pk=self.instance.pk)
            if queryset.filter(date=holiday_date).exists():
                raise ValidationError(
                    {
                        "date": "A public holiday on this date already exists."
                    }
                )
        return cleaned


@admin.register(PublicHoliday)
class PublicHolidayAdmin(admin.ModelAdmin):
    form = PublicHolidayAdminForm
    list_display = ("name", "date")
    search_fields = ("name",)
    list_filter = ("date",)
    ordering = ("date",)

    def has_delete_permission(self, request, obj=None):
        return False
