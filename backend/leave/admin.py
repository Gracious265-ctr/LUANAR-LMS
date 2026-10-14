from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError

from audit.admin import AuditedModelAdmin

from .models import (
    FinancialYear,
    GradeEntitlement,
    LeaveRule,
    LeaveType,
    PublicHoliday,
)
from .services import (
    find_annual_leave_type,
    find_overlapping_financial_year,
    find_overlapping_rule,
    is_annual_leave_identity,
    is_annual_leave_type,
    provision_annual_leave,
)


class GradeEntitlementAdminForm(forms.ModelForm):
    """Admin form that enforces the no-overlap rule as a field error."""

    class Meta:
        model = GradeEntitlement
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # An entitlement is an annual-leave entitlement, so the type is settled
        # by provisioning rather than picked. Kept visible and read-only because
        # the column is what tells an admin which type a band actually grants.
        self.fields["leave_type"].disabled = True
        self.fields["leave_type"].required = False
        self.fields["leave_type"].help_text = (
            "Annual leave, provisioned automatically when you save this band."
        )

    def clean(self):
        cleaned = super().clean()
        grade_start = cleaned.get("grade_start")
        grade_end = cleaned.get("grade_end")
        if grade_start and grade_end:
            # The field is disabled, so on a change ``cleaned_data`` reports the
            # band's own type. On an add it is empty, and the band will be
            # annual, so overlap must be checked against the annual type.
            leave_type = cleaned.get("leave_type") or find_annual_leave_type()
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
class GradeEntitlementAdmin(AuditedModelAdmin):
    form = GradeEntitlementAdminForm
    list_display = ("grade_start", "grade_end", "days", "leave_type", "effective_from")
    search_fields = ("grade_start", "grade_end", "leave_type__name")
    list_filter = ("leave_type", "effective_from")
    ordering = ("-effective_from", "grade_start", "grade_end")

    def save_model(self, request, obj, form, change):
        from django.db import transaction

        # Same provisioning the API performs, so annual leave and its first rule
        # exist whichever surface HR used. Inside the transaction as the save is,
        # so a half-provisioned band is never committed.
        with transaction.atomic():
            obj.leave_type = provision_annual_leave(
                effective_from=obj.effective_from,
                days=obj.days,
                actor=getattr(request, "user", None),
            )
            super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        return False


class LeaveTypeAdminForm(forms.ModelForm):
    """Admin form that keeps annual leave out of the leave-type registry.

    The same two guards the API applies, phrased for the admin: annual leave
    cannot be created here because an entitlement provisions it, and it cannot
    be edited because an entitlement is what an admin edits.
    """

    class Meta:
        model = LeaveType
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()

        if self.instance.pk is not None and is_annual_leave_type(self.instance):
            raise ValidationError(
                "Annual leave is created and maintained from Entitlements. "
                "Edit the entitlement for a grade range instead."
            )

        if self.instance.pk is None:
            name = cleaned.get("name") or ""
            code = cleaned.get("code") or ""
            if is_annual_leave_identity(name, code):
                raise ValidationError(
                    f'"{name}" is reserved for annual leave, which is created '
                    "automatically when you add an entitlement."
                )
        return cleaned


@admin.register(LeaveType)
<<<<<<< HEAD
class LeaveTypeAdmin(AuditedModelAdmin):
    list_display = ("name", "code")
=======
class LeaveTypeAdmin(admin.ModelAdmin):
    form = LeaveTypeAdminForm
    list_display = ("name", "code", "is_active")
    list_filter = ("is_active",)
>>>>>>> feature/plans-teams
    search_fields = ("name", "code")
    ordering = ("name",)


@admin.register(LeaveRule)
class LeaveRuleAdmin(AuditedModelAdmin):
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
class FinancialYearAdmin(AuditedModelAdmin):
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
class PublicHolidayAdmin(AuditedModelAdmin):
    form = PublicHolidayAdminForm
    list_display = ("name", "date")
    search_fields = ("name",)
    list_filter = ("date",)
    ordering = ("date",)

    def has_delete_permission(self, request, obj=None):
        return False
