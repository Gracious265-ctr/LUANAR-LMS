from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from leave_types.models import LeaveType
from leave_types.services import (
    AnnualLeaveLifecycleError,
    deactivate_leave_type,
    is_annual_leave_identity,
    is_annual_leave_type,
    reactivate_leave_type,
)


class LeaveTypeAdminForm(forms.ModelForm):
    """Same two guards the API applies, phrased for the admin.

    Annual leave cannot be *created* here because an entitlement provisions it.
    It *can* be edited, because its rules have no other home now that the Leave
    Rules screens are retired — its name, its short code and ``is_active`` are
    read-only on the ModelAdmin below, which is what keeps the identity of the
    row an entitlement points at from moving.
    """

    class Meta:
        model = LeaveType
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()

        if self.instance.pk is not None:
            return cleaned

        name = cleaned.get("name") or ""
        code = cleaned.get("code") or ""
        if is_annual_leave_identity(name, code):
            raise ValidationError(
                f'"{name}" is reserved for annual leave, which is created '
                "automatically when you add an entitlement."
            )
        return cleaned


@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    """Admin mirror of the Leave Configuration app.

    The list shows the rules HR actually edits; the action row offers the
    deactivate/reactivate pair rather than a delete action, because a referenced
    type must never be hard-deleted (§1.5).
    """

    form = LeaveTypeAdminForm

    list_display = (
        "name",
        "code",
        "branch_scope",
        "eligible_gender",
        "notice_days",
        "max_duration_days",
        "is_active",
        "plannable",
        "requires_institutional_registrar_approval",
        "updated_at",
    )
    list_filter = (
        "is_active",
        "branch_scope",
        "eligible_gender",
        "plannable",
        "consumes_annual_entitlement",
        "requires_institutional_registrar_approval",
    )
    search_fields = ("name", "code")
    readonly_fields = ("id", "created_at", "updated_at")
    actions = ["deactivate_types", "reactivate_types"]

    @admin.action(description="Deactivate selected leave types")
    def deactivate_types(self, request, queryset):
        for leave_type in queryset:
            try:
                deactivate_leave_type(leave_type, request.user)
            except AnnualLeaveLifecycleError as error:
                self.message_user(request, str(error), level=messages.WARNING)

    @admin.action(description="Reactivate selected leave types")
    def reactivate_types(self, request, queryset):
        for leave_type in queryset:
            reactivate_leave_type(leave_type, request.user)

    def get_readonly_fields(self, request, obj=None):
        # ``is_active`` moves through the audited lifecycle actions above, so
        # the raw checkbox is read-only here rather than silently bypassing it.
        readonly = (*super().get_readonly_fields(request, obj), "is_active")
        # The annual type is found by name and code — an entitlement and the
        # balance ledger both resolve through them — so its identity is fixed
        # while its rules stay editable like any other type's.
        if obj is not None and is_annual_leave_type(obj):
            return (*readonly, "name", "code")
        return readonly
