from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet

from .models import (
    ApproverRole,
    Campus,
    Delegation,
    Reassignment,
    RoleAssignment,
    Team,
    TeamMember,
    Workflow,
    WorkflowStage,
)
from .services import (
    approver_role_codes_for,
    ensure_role_not_in_use,
    validate_workflow_for_activation,
)


class WorkflowStageForm(forms.ModelForm):
    """Inline form for one workflow stage.

    ``approver_role`` is chosen by ``code`` rather than by primary key, matching
    the workflow API: a saved workflow reads "hod", and HR picks a role by what it
    is called instead of by an id they have no way to look up.
    """

    approver_role = forms.ModelChoiceField(
        queryset=ApproverRole.objects.all(),
        to_field_name="code",
        label="Approver role",
    )

    class Meta:
        model = WorkflowStage
        fields = "__all__"

    def clean_order(self):
        order = self.cleaned_data.get("order")
        if order is not None and order < 1:
            raise ValidationError("Stage order must be 1 or greater.")
        return order

    def clean_approver_role(self):
        role = self.cleaned_data.get("approver_role")
        if role is not None and not role.is_active:
            raise ValidationError(
                f'"{role.label}" is deactivated. Reactivate it in Roles, or '
                "pick an active role."
            )
        return role


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
        # ``stages__approver_role`` as well: the summary renders role labels, so
        # without it the list page runs one query per stage.
        return super().get_queryset(request).prefetch_related("stages__approver_role")

    def stage_summary(self, obj):
        # ``approver_role`` is a related row now, so show its label rather than
        # the default ``__str__`` — the summary reads "Supervisor → HOD → …".
        roles = [stage.approver_role.label for stage in obj.stages.all()]
        return " \u2192 ".join(roles) if roles else "—"

    stage_summary.short_description = "Approval stages"

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Delegation)
class DelegationAdmin(admin.ModelAdmin):
    """View-only inspector for delegation requests (decisions are API-driven)."""

    list_display = (
        "approver",
        "approver_roles",
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

    @admin.display(description="Approver roles")
    def approver_roles(self, obj):
        """Which positions the delegating approver holds.

        ``User.__str__`` shows the system role ("approver"), which no longer says
        where the person sits in a chain, so HR gets the position from the role
        graph instead.
        """
        codes = approver_role_codes_for(obj.approver)
        return ", ".join(codes) if codes else obj.approver.role

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Reassignment)
class ReassignmentAdmin(admin.ModelAdmin):
    """View-only inspector for reassignments (use the HR API to reassign)."""

    list_display = (
        "application",
        "employee_name",
        "from_approver",
        "to_approver",
        "reason",
        "decided_by",
        "created_at",
    )
    raw_id_fields = ("application", "from_approver", "to_approver", "decided_by")
    readonly_fields = (
        "application",
        "from_approver",
        "to_approver",
        "reason",
        "decided_by",
        "created_at",
    )
    ordering = ("-created_at",)

    @admin.display(description="Employee")
    def employee_name(self, obj):
        return obj.application.employee.get_full_name()

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(ApproverRole)
class ApproverRoleAdmin(admin.ModelAdmin):
    """HR-managed approver roles.

    Never deletable, and deactivated rather than deleted: every workflow stage,
    team membership, and historical stage snapshot points at a role, so a hard
    delete would leave those rows unresolvable. The admin is deliberately a
    *read* surface — creating, renaming, and retiring a role all have service
    methods that record an audit entry and refuse an in-use deactivation, and
    the admin does not go through them.
    """

    list_display = ("label", "code", "history_scope", "handles_cancellation", "is_institution_wide", "is_active")
    list_filter = ("is_active", "history_scope", "handles_cancellation", "is_institution_wide")
    search_fields = ("code", "label", "description")
    ordering = ("label",)
    readonly_fields = ("code", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        """Refuse a deactivation that would break a live workflow or team.

        The same guard the service layer applies, so an admin edit cannot route
        around it. A deactivation that is still in use is rejected with the same
        explanatory message the API returns.
        """
        if change and not obj.is_active:
            ensure_role_not_in_use(obj)
        super().save_model(request, obj, form, change)


@admin.register(Campus)
class CampusAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active", "team_count")
    list_filter = ("is_active",)
    search_fields = ("code", "name")
    ordering = ("name",)

    @admin.display(description="Teams")
    def team_count(self, obj):
        return obj.teams.count()

    def has_delete_permission(self, request, obj=None):
        # PROTECTed by Team.campus; refusing here gives a better message than
        # the database's integrity error.
        return False


class TeamMemberInline(admin.TabularInline):
    model = TeamMember
    extra = 1
    raw_id_fields = ("user",)


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "campus", "workflow", "member_count", "is_active")
    list_filter = ("is_active", "campus")
    search_fields = ("name", "code", "description")
    raw_id_fields = ("workflow", "campus")
    ordering = ("name",)
    inlines = [TeamMemberInline]

    @admin.display(description="Members")
    def member_count(self, obj):
        return obj.memberships.count()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ("team", "user", "role", "created_at")
    list_filter = ("role",)
    search_fields = ("team__name", "user__first_name", "user__last_name", "user__email")
    raw_id_fields = ("team", "user")


@admin.register(RoleAssignment)
class RoleAssignmentAdmin(admin.ModelAdmin):
    """Institution-wide role holdings.

    Only roles flagged ``is_institution_wide`` may appear here; the API enforces
    that, and the inline form filter keeps the admin honest without duplicating
    the check.
    """

    list_display = ("user", "role", "created_at")
    list_filter = ("role",)
    search_fields = ("user__first_name", "user__last_name", "user__email", "role__label")
    raw_id_fields = ("user",)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "role":
            kwargs["queryset"] = ApproverRole.objects.filter(
                is_institution_wide=True
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
