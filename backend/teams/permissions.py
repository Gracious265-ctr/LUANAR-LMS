from rest_framework import permissions

from roles.permissions import IsHROnly, IsHROrTeamManager, is_hr

__all__ = ["IsHROnly", "IsHROrTeamManager", "is_hr"]
