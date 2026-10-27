from rest_framework import permissions

from .models import User


class IsHRRole(permissions.BasePermission):
    """Allow an authenticated HR user, or the bootstrap superuser.

    The superuser is the account a deployment starts with, created with
    ``createsuperuser``; it is not a ``User.Role`` value but every other HR
    gate in the project treats it as one (``roles.permissions.is_hr``, the
    Teams and Approvers pages, the launcher). Gating on the role alone made the
    bootstrap administrator open a page whose own data requests then 403'd —
    the Approvers page showed "Unable to load employees" because this class
    refused ``/api/v1/employees/``.
    """

    message = "You do not have permission to perform this action."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (
                getattr(user, "role", None) == User.Role.HR
                or user.is_superuser
            )
        )


class IsSuperUser(permissions.BasePermission):
    """Allow access only to an authenticated Django superuser.

    The superuser is the bootstrap administrator: the one account a deployment
    starts with, created with ``createsuperuser`` and outside the product. It is
    deliberately not a ``User.Role`` value, because it is not a place in the
    leave process — it is the account that can hand out HR access in the first
    place. Gating on ``is_superuser`` keeps that capability from being granted
    through the employee directory, which only ever creates normal employees.
    """

    message = "Only an administrator may perform this action."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.is_superuser)
