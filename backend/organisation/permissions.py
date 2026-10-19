"""Reusable organisation authorisation primitives shared with the workflow API.

Two building blocks the team-management delegation needs across several
viewsets:

* a coarse "is this person HR, or a team manager at all?" check, used by the
  viewsets a manager may otherwise use (teams, workflows, section members),
  and
* a strict "HR only" check for the actions HR keeps to itself even on a
  viewset a manager may otherwise use (creating a team, editing its identity or
  lifecycle).

Both are deliberately *class-level* checks. The object-level scoping — "…and it
is **your** team" — is applied by each viewset's ``get_queryset``, which filters
a manager to the teams they manage, so a manager can neither read nor write
another team's configuration.
"""

from rest_framework import permissions

from users.models import User


def is_hr(user) -> bool:
    """Whether ``user`` administers the whole organisational tree.

    HR is the role; a superuser is the bootstrap administrator and is treated
    the same, so an installation is never locked out of its own teams.
    """
    return bool(
        user
        and user.is_authenticated
        and (user.role == User.Role.HR or user.is_superuser)
    )


def _is_active(user) -> bool:
    return bool(user and user.is_authenticated and user.is_active)


class IsHROrTeamManager(permissions.BasePermission):
    """Allow HR, a superuser, or any designated team manager.

    This admits a manager to the viewset as a whole; the per-team scoping that
    keeps them on their *own* team is the viewset queryset's job, not this
    class's.
    """

    message = "Only HR or a team manager may perform this action."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not _is_active(user):
            return False
        if is_hr(user):
            return True
        from organisation.services import managed_team_ids_for

        return bool(managed_team_ids_for(user))


class IsHROnly(permissions.BasePermission):
    """Restrict an action to HR on a viewset a manager may otherwise use."""

    message = "Only HR may perform this action."

    def has_permission(self, request, view) -> bool:
        return _is_active(request.user) and is_hr(request.user)
