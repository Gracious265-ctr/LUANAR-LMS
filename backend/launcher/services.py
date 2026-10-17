def can_access_leave(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    return True  # All authenticated users can access leave


def _leave_badge(user) -> dict | None:
    # Minimal: no badge for now; return None as per "absence, not zero"
    return None


def can_access_plans(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    return True  # Every authenticated user may keep personal leave plans


def _plans_badge(user) -> dict | None:
    """Count of plans whose reminder has fired and are still awaiting action.

    Only ``notified`` plans badge: an ``upcoming`` plan is not yet the employee's
    turn to act, and a ``missed`` one is history, so neither is a live nudge.
    """
    from plans.models import LeavePlan, LeavePlanStatus

    count = LeavePlan.objects.filter(
        employee=user, status=LeavePlanStatus.NOTIFIED
    ).count()
    if not count:
        return None
    return {"count": count, "label": "ready to apply"}


def can_access_approvals(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    # HR, superuser, or approver roles can access approvals
    role = getattr(user, "role", None)
    if role in ("hr", "superuser", "approver", "hod", "dean", "registrar", "dvc"):
        return True
    if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return True
    return False


def _approvals_badge(user) -> dict | None:
    # No badge: pending counts are surfaced by the approvals module itself.
    return None


def can_access_org(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    role = getattr(user, "role", None)
    if role in ("hr", "superuser"):
        return True
    if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return True
    return False


def _org_badge(user) -> dict | None:
    return None


def can_access_documents(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    # The documents area is the HR-only leave-document template manager.
    role = getattr(user, "role", None)
    if role == "hr" or role == "superuser":
        return True
    if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return True
    return False


def can_access_hr_admin(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    role = getattr(user, "role", None)
    if role == "hr" or role == "superuser":
        return True
    if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return True
    return False


def _hr_admin_badge(user) -> dict | None:
    return None


def get_launcher_apps(user) -> list[dict]:
    apps = []
    if can_access_leave(user):
        apps.append({"key": "leave", "badge": _leave_badge(user)})
    if can_access_plans(user):
        apps.append({"key": "plans", "badge": _plans_badge(user)})
    if can_access_approvals(user):
        apps.append({"key": "approvals", "badge": _approvals_badge(user)})
    if can_access_org(user):
        apps.append({"key": "org", "badge": _org_badge(user)})
    if can_access_documents(user):
        apps.append({"key": "documents", "badge": None})
    if can_access_hr_admin(user):
        apps.append({"key": "hr-admin", "badge": _hr_admin_badge(user)})
    return apps
