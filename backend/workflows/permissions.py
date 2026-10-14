from rest_framework import permissions

from users.models import User

from .services import is_approver_user


class IsApproverRoleOrHR(permissions.BasePermission):
    """Allow delegation-request creation by active approvers and HR.

    HR is admitted explicitly rather than through :func:`is_approver_user`: HR
    does not hold an approver role, but does need to raise a delegation on
    somebody else's behalf, which is a documented part of the delegation flow.
    """

    message = "Only an approver or HR can create a delegation request."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and (user.role == User.Role.HR or is_approver_user(user))
        )
