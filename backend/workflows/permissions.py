from rest_framework import permissions

from users.models import User

from .models import APPROVER_ROLE_CODES


class IsApproverRoleOrHR(permissions.BasePermission):
    """Allow delegation-request creation by active approvers and HR."""

    message = "Only an approver or HR can create a delegation request."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and (user.role == User.Role.HR or user.role in APPROVER_ROLE_CODES)
        )