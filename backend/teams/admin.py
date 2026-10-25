from django.contrib import admin

from roles.models import ApproverRole

from .models import Team, TeamRoleAssignment


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
        "status",
        "effective_window",
    )
    list_filter = ("status", "category", "campus")
    search_fields = ("name", "code", "description")
    raw_id_fields = ("campus",)
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
