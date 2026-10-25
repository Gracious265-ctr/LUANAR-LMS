from rest_framework import permissions

from users.models import User

from roles.services import is_approver_user


class IsApprover(permissions.BasePermission):
    def has_permission(self, request, view) -> bool:
        user = request.user
        if not getattr(user, "is_authenticated", False):
            return False
        return bool(is_approver_user(user))


from roles.permissions import IsHROnly, IsHROrTeamManager, is_hr

__all__ = ["IsApprover", "IsHROnly", "IsHROrTeamManager", "is_hr"]


class IsApproverRoleOrHR(permissions.BasePermission):
    message = "Only approvers or HR may perform this action."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not getattr(user, "is_authenticated", False) or not user.is_active:
            return False
        if user.role == User.Role.HR or user.is_superuser:
            return True
        return bool(is_approver_user(user))
