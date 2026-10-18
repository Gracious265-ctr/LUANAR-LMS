"""Reusable organisation authorisation primitives shared with the workflow API.

The team-management delegation needs two building blocks used across several
viewsets:

* a coarse "is this person HR, or a team manager at all?" check for actions that
  are not tied to one team (listing approver roles, creating a role), and
* a strict "HR only" check for the actions HR keeps to itself even on a viewset
  a manager may otherwise use (retiring a role, assigning wide holders).

Both are deliberately *class-level* checks. The object-level scoping — "…and it
is **your** team" — lives in :mod:`workflows.policies`, which knows how to
resolve a ``Team``/``Workflow``/``Section`` to the team it belongs to.
"""

from rest_framework import permissions

from users.models import User

from .services import managed_team_ids_for


def _is_hr(user) -> bool:
    return bool(
        user
        and user.is_authenticated
        and (user.role == User.Role.HR or user.is_superuser)
    )


def _is_active(user) -> bool:
    return bool(user and user.is_authenticated and user.is_active)


class IsHROrTeamManager(permissions.BasePermission):
    """Allow any authenticated, active HR user or team manager.

    This admits a team manager for actions that are not scoped to a single team
    (such as reading or creating approver roles). Where the action *is* scoped to
    a team, pair it with the object-level check in ``workflows.policies`` so a
    manager can only reach their own team.
    """

    message = "Only HR or a team manager may perform this action."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not _is_active(user):
            return False
        if _is_hr(user):
            return True
        return bool(managed_team_ids_for(user))


class IsHROnly(permissions.BasePermission):
    """Restrict an action to HR on a viewset a manager may otherwise use."""

    message = "Only HR may perform this action."

    def has_permission(self, request, view) -> bool:
        return _is_hr(request.user) and _is_active(request.user)
