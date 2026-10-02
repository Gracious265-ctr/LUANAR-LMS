from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import EmployeeProfile, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin for the custom user model with role visibility."""

    list_display = [
        "username",
        "email",
        "first_name",
        "last_name",
        "role",
        "is_active",
    ]
    list_filter = ["role", "is_active", "is_staff", "is_superuser"]
    fieldsets = BaseUserAdmin.fieldsets + (("Role", {"fields": ("role",)}),)
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("Role", {"fields": ("role",)}),
    )

    def save_model(self, request, obj, form, change):
        """Keep the login name in step with the email.

        The product signs people in by email, and resolves it through the
        ``username`` column, so an account whose username and email disagree —
        as one made from the stock admin form can — would be created here and
        then unable to log in. Syncing the two is what makes an admin-created HR
        account usable without a second, hidden step.
        """
        if obj.email:
            obj.username = obj.email
        super().save_model(request, obj, form, change)


@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):
    """Admin for HR-managed employee records."""

    list_display = [
        "user",
        "designation",
        "department",
        "category",
        "grade",
        "active",
    ]
    list_filter = ["category", "department", "user__is_active"]
    search_fields = [
        "user__username",
        "user__email",
        "user__first_name",
        "user__last_name",
        "designation",
        "department",
        "grade",
    ]
    autocomplete_fields = ["user"]

    @admin.display(boolean=True, description="Active")
    def active(self, obj: EmployeeProfile) -> bool:
        return obj.user.is_active
