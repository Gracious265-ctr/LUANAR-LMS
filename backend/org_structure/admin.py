from django.contrib import admin

from .models import OrgUnit


@admin.register(OrgUnit)
class OrgUnitAdmin(admin.ModelAdmin):
    list_display = ("name", "unit_type", "parent", "has_teams", "designated_approver")
    list_filter = ("unit_type", "has_teams")
    search_fields = ("name", "external_id")
    raw_id_fields = ("designated_approver",)
