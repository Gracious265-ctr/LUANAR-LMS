from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms import BaseInlineFormSet

<<<<<<< HEAD
from audit.admin import AuditedModelAdmin

from .models import Delegation, Reassignment, Workflow, WorkflowStage
from .services import validate_workflow_for_activation
=======
from .models import (
    ApproverRole,
    Campus,
    CampusRoleAssignment,
    Delegation,
    Reassignment,
    RoleAssignment,
    Section,
    SectionMember,
    Team,
    TeamRoleAssignment,
    Workflow,
)
from .services import approver_role_codes_for, ensure_role_not_in_use
>>>>>>> feature/plans-teams


class SectionForm(forms.ModelForm):
    """Inline form for one workflow section.

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
        model = Section
        fields = "__all__"

    def clean_order(self):
        order = self.cleaned_data.get("order")
        if order is not None and order < 1:
            raise ValidationError("Section order must be 1 or greater.")
        return order

    def clean_approver_role(self):
        role = self.cleaned_data.get("approver_role")
        if role is not None and not role.is_active:
            raise ValidationError(
                f'"{role.label}" is deactivated. Reactivate it in Roles, or '
                "pick an active role."
            )
        return role


class SectionInlineFormSet(BaseInlineFormSet):
    """Rejects a workflow whose sections do not have distinct positions.

    ``Section``'s unique constraint on ``(workflow, order)`` would catch this
    too, but as a database error at save time. Validating in the formset names
    the problem where HR can act on it, and does so for the whole form rather
    than failing on whichever row happened to be written first.

    A repeated approver role is deliberately *not* re-checked here (Unit 30). It
    needs no second implementation: ``section_workflow_role_unique`` is a model
    constraint, so Django's own cross-form ``validate_unique`` already reports the
    repeat on the ``approver_role`` field, where HR can act on it. Letting the
    model constraint answer is also what keeps the admin and the API agreeing by
    construction rather than by two code paths kept in step by hand.
    """

    def clean(self):
        super().clean()
        orders = [
            form.cleaned_data.get("order")
            for form in self.forms
            if form.cleaned_data and not form.cleaned_data.get("DELETE")
        ]
        duplicates = {o for o in orders if o is not None and orders.count(o) > 1}
        if duplicates:
            raise ValidationError(
                "Each approval section needs its own position. These numbers are "
                f"used more than once: {', '.join(str(o) for o in sorted(duplicates))}."
            )


class SectionInline(admin.TabularInline):
    """Workflow sections, in approval order.

    A repeated approver role is refused: since Unit 30 a role belongs to exactly
    one stage of a workflow, so that one office cannot sign off twice at two
    points in the same chain. The same role may still be used by a different
    workflow.
    """

    model = Section
    form = SectionForm
    formset = SectionInlineFormSet
    extra = 1
    min_num = 1
    validate_min = True
    ordering = ("order",)


class WorkflowAdminForm(forms.ModelForm):
    """Kept for the section inline; the chain itself is not editable here.

    A chain is created and rewritten with its team, so this form only ever
    renders for the read-only inspector's inlines, which do not validate a
    lifecycle of their own.
    """

    class Meta:
        model = Workflow
        fields = "__all__"


@admin.register(Workflow)
<<<<<<< HEAD
class WorkflowAdmin(AuditedModelAdmin):
=======
class WorkflowAdmin(admin.ModelAdmin):
    """Read-only inspector. A chain is written through its team.

    A chain is created with its team and its steps are rewritten by saving the
    team again, so this page exists to answer "what is this team's chain, and
    when did it last change" — not to be a second place to edit it. Leaving the
    write open here would let a chain be edited apart from the team whose
    applications it governs, which is precisely the mistake the team-owned
    chain rules out everywhere else.
    """

>>>>>>> feature/plans-teams
    form = WorkflowAdminForm
    list_display = (
        "name",
        "owner",
        "effective_from",
        "is_active",
        "section_summary",
    )
    list_filter = ("is_active",)
    search_fields = ("name",)
    ordering = ("name",)
    inlines = [SectionInline]

    def get_queryset(self, request):
        # ``stages__approver_role`` as well: the summary renders role labels, so
        # without it the list page runs one query per stage.
        return super().get_queryset(request).prefetch_related(
            "sections__approver_role"
        )

    def section_summary(self, obj):
        # ``approver_role`` is a related row now, so show its label rather than
        # the default ``__str__`` — the summary reads "Supervisor → HOD → …".
        labels = [section.approver_role.label for section in obj.sections.all()]
        return " \u2192 ".join(labels) if labels else "—"

    section_summary.short_description = "Approval sections"

    @admin.display(description="Team")
    def owner(self, obj):
        team = getattr(obj, "team", None)
        return team.name if team else "—"

    def has_add_permission(self, request):
        # A chain without a team is a chain nothing routes through.
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        # PROTECTed by Team.workflow, and the audit trail is the record of why
        # a chain looked the way it did.
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


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    """Deliberately not a lifecycle editor.

    Switching a team between draft, active and inactive is a *decision* about
    real applications, so it goes through ``workflows.services.activate_team`` /
    ``deactivate_team``: validated, refused when the configuration cannot support
    it, and audited as its own event. An admin form that just wrote ``status``
    would be a way around all three, so the field is read-only here and the
    buttons are the API's actions.
    """

    list_display = (
        "name",
        "code",
        "category",
        "campus",
        "workflow",
        "status",
        "effective_window",
    )
    list_filter = ("status", "category", "campus")
    search_fields = ("name", "code", "description")
    raw_id_fields = ("workflow", "campus")
    ordering = ("name",)
    readonly_fields = ("status", "created_at", "updated_at")

    @admin.display(description="Effective")
    def effective_window(self, obj: Team) -> str:
        if obj.effective_from is None and obj.effective_to is None:
            return "Always"
        start = obj.effective_from.isoformat() if obj.effective_from else "start"
        end = obj.effective_to.isoformat() if obj.effective_to else "open"
        return f"{start} → {end}"

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ("name", "workflow", "order", "approver_role", "member_count", "is_active")
    list_filter = ("is_active", "workflow", "approver_role")
    search_fields = ("name", "workflow__name")
    raw_id_fields = ("workflow",)
    ordering = ("workflow__name", "order")

    @admin.display(description="Members")
    def member_count(self, obj):
        return obj.members.count()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SectionMember)
class SectionMemberAdmin(admin.ModelAdmin):
    list_display = ("section", "user", "created_at")
    list_filter = ("section__workflow",)
    search_fields = (
        "section__name",
        "user__first_name",
        "user__last_name",
        "user__email",
    )
    raw_id_fields = ("section", "user")


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


@admin.register(TeamRoleAssignment)
class TeamRoleAssignmentAdmin(admin.ModelAdmin):
    """Team-wide role holdings.

    One holder per role per team is a model constraint, so the admin is a
    lookup and not a second configuration surface: the pick-a-role,
    pick-a-person form with its replacement-and-audit contract lives on the
    team's own approvers screen. Only non-institution-wide roles belong here,
    and the inline form filter keeps the admin honest about that without
    duplicating the check the API already makes.
    """

    list_display = ("user", "role", "team", "created_at")
    list_filter = ("role", "team")
    search_fields = (
        "user__first_name",
        "user__last_name",
        "user__email",
        "role__label",
        "team__name",
    )
    raw_id_fields = ("user", "team")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "role":
            kwargs["queryset"] = ApproverRole.objects.filter(
                is_active=True, is_institution_wide=False
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(CampusRoleAssignment)
class CampusRoleAssignmentAdmin(admin.ModelAdmin):
    """Campus-wide role holdings, scoped to the campus they resolve at.

    Same one-holder, replace-on-save contract as the team-wide holding, and the
    same reason the API owns that contract: the admin is for looking a holding
    up, not for being the second place it can be written.
    """

    list_display = ("user", "role", "campus", "created_at")
    list_filter = ("role", "campus")
    search_fields = (
        "user__first_name",
        "user__last_name",
        "user__email",
        "role__label",
        "campus__name",
    )
    raw_id_fields = ("user", "campus")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "role":
            kwargs["queryset"] = ApproverRole.objects.filter(
                is_active=True, is_institution_wide=False
            )
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
