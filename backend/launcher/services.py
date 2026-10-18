"""Thin aggregator behind ``GET /api/v1/apps/launcher/``.

Each module owns whether a user may open it (``can_access_*``) and how many
things are waiting on them (the badge). The launcher only assembles the modules
a user can reach into the small payload the frontend merges against its static
registry; it holds no access rules of its own.
"""

from approvals.services import can_access_approvals, pending_stage_count_for
from organisation.services import can_access_org


def can_access_leave(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    return True


def _leave_badge(user) -> dict | None:
    return None


def _approvals_badge(user) -> dict | None:
    count = pending_stage_count_for(user)
    if count:
        return {"count": count, "label": "pending", "tone": "amber"}
    return None


def _org_badge(user) -> dict | None:
    return None


def can_access_documents(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    return True


def can_access_hr_admin(user) -> bool:
    if not (
        user
        and getattr(user, "is_authenticated", False)
        and getattr(user, "is_active", False)
    ):
        return False
    return getattr(user, "role", None) == "hr" or bool(
        getattr(user, "is_superuser", False)
    )


def _hr_admin_badge(user) -> dict | None:
    return None


def get_launcher_apps(user) -> list[dict]:
    apps = []
    if can_access_leave(user):
        apps.append({"key": "leave", "badge": _leave_badge(user)})
    if can_access_approvals(user):
        apps.append({"key": "approvals", "badge": _approvals_badge(user)})
    if can_access_org(user):
        apps.append({"key": "organisation", "badge": _org_badge(user)})
    if can_access_documents(user):
        apps.append({"key": "documents", "badge": None})
    if can_access_hr_admin(user):
        apps.append({"key": "hr-admin", "badge": _hr_admin_badge(user)})
    return apps
