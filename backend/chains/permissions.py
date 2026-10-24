from rest_framework import permissions

from users.models import User

<<<<<<< HEAD:backend/chains/permissions.py
from roles.services import is_approver_user
=======
from organisation.services import (
    is_approver_user,
    is_team_manager,
    managed_team_ids_for,
)
>>>>>>> features/team-base:backend/workflows/permissions.py


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


class IsTeamManagerOnly(permissions.BasePermission):
    """Team-scoped management writes: the designated manager, and no one else.

    HR creates a team and designates its manager, so the day-to-day of one team —
    its members, its chains, its steps — belongs to that manager rather than to
    HR. These actions therefore refuse HR outright, on top of the team scoping the
    coarse :class:`IsHROrTeamManager` permission applies to the rest of the
    viewsets: the check here is the object-level "…and it is *your* team" half of
    the separation, and it is stricter than the coarse half for exactly the
    operations that follow the handover rather than precede it.
    """

    message = "Only the team manager may perform this action."

    def has_permission(self, request, view) -> bool:
        # HR is admitted nowhere here: the handover means the manager owns the
        # day-to-day of their teams. A caller who manages no team at all is
        # refused here (403) rather than falling through to the scoped queryset
        # and reading as a missing team (404); the object check then narrows a
        # manager to their *own* team.
        user = request.user
        if not user or not user.is_authenticated or not user.is_active:
            return False
        if user.is_superuser:
            return True
        if user.role == User.Role.HR:
            return False
        return bool(managed_team_ids_for(user))

    def _team_of(self, obj):
        if obj is None:
            return None
        workflow = getattr(obj, "workflow", None)
        if workflow is not None and getattr(workflow, "team", None) is not None:
            return workflow.team
        team = getattr(obj, "team", None)
        if team is not None:
            return team
        section = getattr(obj, "section", None)
        if section is not None:
            owning = getattr(section, "workflow", None)
            if owning is not None and getattr(owning, "team", None) is not None:
                return owning.team
        return obj if hasattr(obj, "pk") else None

    def has_object_permission(self, request, view, obj) -> bool:
        user = request.user
        if not user or not user.is_authenticated or not user.is_active:
            return False
        if user.is_superuser:
            return True
        team = self._team_of(obj)
        return bool(team) and is_team_manager(user, team)
