from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet

from .models import Delegation, Workflow, WorkflowStage
from .services import validate_workflow_for_activation


class WorkflowStageForm(forms.ModelForm):
    """Inline form for one workflow stage."""

    class Meta:
        model = WorkflowStage
        fields = "__all__"

    def clean_order(self):
        order = self.cleaned_data.get("order")
        if order is not None and order < 1:
            raise ValidationError("Stage order must be 1 or greater.")
        return order


class WorkflowStageInlineFormSet(BaseInlineFormSet):
    """Inline formset that rejects repeated approver roles in one workflow."""

    def clean(self):
        super().clean()
        roles = []
        for form in self.forms:
            if not hasattr(form, "cleaned_data") or not form.cleaned_data:
                continue
            data = form.cleaned_data
            if data.get("DELETE"):
                continue
            role = data.get("approver_role")
            if role and role in roles:
                raise ValidationError(
                    "An approver role can appear only once in a workflow."
                )
            if role:
                roles.append(role)


class WorkflowStageInline(admin.TabularInline):
    model = WorkflowStage
    form = WorkflowStageForm
    formset = WorkflowStageInlineFormSet
    extra = 1
    min_num = 1
    validate_min = True
    ordering = ("order",)


class WorkflowAdminForm(forms.ModelForm):
    """Admin form that validates activation/scheduling using the same services."""

    class Meta:
        model = Workflow
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        effective_from = cleaned.get("effective_from")
        if effective_from and cleaned.get("is_active"):
            scope = (
                cleaned.get("employee_category") or "",
                (cleaned.get("department") or "").strip(),
            )
            stages = self.instance.stages.all() if self.instance.pk else []
            issues = validate_workflow_for_activation(
                self.instance.pk, scope, stages
            )
            if issues:
                raise ValidationError(
                    " ".join(issue.message for issue in issues)
                )
        return cleaned


@admin.register(Workflow)
class WorkflowAdmin(admin.ModelAdmin):
    form = WorkflowAdminForm
    list_display = (
        "name",
        "employee_category",
        "department",
        "effective_from",
        "is_active",
        "stage_summary",
    )
    list_filter = ("employee_category", "is_active")
    search_fields = ("name", "department")
    ordering = ("name",)
    inlines = [WorkflowStageInline]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("stages")

    def stage_summary(self, obj):
        roles = [stage.approver_role for stage in obj.stages.all()]
        return " \u2192 ".join(roles) if roles else "—"

    stage_summary.short_description = "Approval stages"

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Delegation)
class DelegationAdmin(admin.ModelAdmin):
    """View-only inspector for delegation requests (decisions are API-driven)."""

    list_display = (
        "approver",
        "delegate",
        "starts_on",
        "ends_on",
        "state",
        "status",
        "requested_by",
        "decided_by",
        "decided_at",
    )
    list_filter = ("status",)
    search_fields = (
        "approver__first_name",
        "approver__last_name",
        "approver__email",
        "delegate__first_name",
        "delegate__last_name",
        "delegate__email",
    )
    raw_id_fields = ("approver", "delegate", "requested_by", "decided_by")
    readonly_fields = (
        "approver",
        "delegate",
        "starts_on",
        "ends_on",
        "requested_by",
        "decision_reason",
        "decided_by",
        "decided_at",
        "status",
        "state",
        "created_at",
        "updated_at",
    )
    ordering = ("-created_at",)

    @admin.display(description="State")
    def state(self, obj):
        return obj.state

    def has_delete_permission(self, request, obj=None):
        return False