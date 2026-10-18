from django.contrib import admin

from approvals.models import Delegation, Reassignment
from organisation.services import approver_role_codes_for


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
