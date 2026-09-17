from rest_framework import permissions


class IsOwner(permissions.BasePermission):
    """Object-level permission: only the employee who owns the application can access it."""

    def has_object_permission(self, request, view, obj):
        if hasattr(obj, "employee"):
            return obj.employee == request.user
        if hasattr(obj, "application"):
            return obj.application.employee == request.user
        return False
