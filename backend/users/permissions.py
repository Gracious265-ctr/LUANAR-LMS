from rest_framework import permissions

from .models import User


class IsHRRole(permissions.BasePermission):
    """Allow access only to authenticated users with the HR role."""

    message = "You do not have permission to perform this action."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and getattr(user, "role", None) == User.Role.HR
        )
