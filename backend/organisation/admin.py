from django.contrib import admin

from .models import (
    ApproverRole,
    Campus,
    CampusRoleAssignment,
    RoleAssignment,
    Team,
    TeamRoleAssignment,
)
from .services import ensure_role_not_in_use

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

    A team is in force the moment HR creates it, so there is no "put into force"
    for the admin to perform. The one move that still takes a team out of
    service — retirement — goes through ``workflows.services.deactivate_team``,
    audited as its own event. An admin form that just wrote ``status`` would be
    a way around that, so the field is read-only here and the button is the
    API's action.
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
