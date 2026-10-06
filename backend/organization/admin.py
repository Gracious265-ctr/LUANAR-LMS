"""Django admin for the organizational tree.

The tree is HR-maintained reference data with no employee-facing screen yet, so
this is the only place it can be edited outside the API. Registered here rather
than in ``workflows.admin`` because it is a separate app with its own models, and
because the ordering below is the one an HR user reads the chart in.
"""

from django.contrib import admin

from .exceptions import OrgUnitCycleError
from .models import ActingAssignment, OrgUnit

#: Ordinary spaces collapse in HTML, so an indent built from them disappears in
#: the admin's list view. A non-breaking space survives rendering.
NBSP = "\u00a0"


class ActingAssignmentInline(admin.TabularInline):
    model = ActingAssignment
    extra = 0
    raw_id_fields = ("acting_user", "role", "created_by")


@admin.register(OrgUnit)
class OrgUnitAdmin(admin.ModelAdmin):
    """One row per node, indented by depth so the chart is readable at a glance."""

    list_display = ("indented_name", "unit_type", "parent", "approver_role", "is_active")
    list_filter = ("unit_type", "is_active")
    search_fields = (
        "name",
        "designated_approver__first_name",
        "designated_approver__last_name",
    )
    raw_id_fields = ("parent", "designated_approver")
    inlines = [ActingAssignmentInline]

    @admin.display(description="Unit", ordering="name")
    def indented_name(self, obj: OrgUnit) -> str:
        """Indent by depth rather than showing a full breadcrumb.

        A breadcrumb repeats the whole path on every row, which makes a chart
        forty units deep unreadable; an indent conveys the same information in a
        fraction of the width and sorts the way the tree looks. Non-breaking
        spaces, because ordinary ones collapse in HTML and the indent vanishes.
        """
        try:
            depth = obj.depth()
        except OrgUnitCycleError:
            # Show the row rather than 500 the whole page, so HR can still find
            # and repair the unit that closes the loop.
            depth = 0
        return f"{NBSP * depth}{obj.name}"


@admin.register(ActingAssignment)
class ActingAssignmentAdmin(admin.ModelAdmin):
    """Actancies, newest period first, with the current state spelled out.

    ``state`` is derived from the dates rather than stored, so it is shown as a
    read-only column instead of being edited here — editing it would only change
    what this page says, not what the resolver does.
    """

    list_display = (
        "org_unit",
        "acting_user",
        "role",
        "start_date",
        "end_date",
        "derived_state",
        "created_by",
    )
    list_filter = ("org_unit", "start_date")
    search_fields = (
        "org_unit__name",
        "acting_user__first_name",
        "acting_user__last_name",
        "role__label",
        "reason",
    )
    raw_id_fields = ("acting_user", "role", "created_by")
    date_hierarchy = "start_date"

    @admin.display(description="State")
    def derived_state(self, obj: ActingAssignment) -> str:
        return obj.state.title()
