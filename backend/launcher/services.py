def can_access_leave(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    return True  # All authenticated users can access leave


def _leave_badge(user) -> dict | None:
    # Minimal: no badge for now; return None as per "absence, not zero"
    return None


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
    # Reuse existing pending count if available
    try:
        from workflows import approval_views  # type: ignore
    except Exception:
        try:
            from approvals import services as approval_services  # type: ignore

            count = approval_services.pending_stage_count_for(user) if hasattr(approval_services, "pending_stage_count_for") else 0
        except Exception:
            count = 0
    else:
        # Try to get count from approval_views logic if exposed
        try:
            from workflows import approval_views as av

            count = av._pending_count_for_user(user) if hasattr(av, "_pending_count_for_user") else 0
        except Exception:
            count = 0
    if count:
        return {"count": count, "label": "pending", "tone": "amber"}
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
    return True


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
    if can_access_approvals(user):
        apps.append({"key": "approvals", "badge": _approvals_badge(user)})
    if can_access_org(user):
        apps.append({"key": "org", "badge": _org_badge(user)})
    if can_access_documents(user):
        apps.append({"key": "documents", "badge": None})
    if can_access_hr_admin(user):
        apps.append({"key": "hr-admin", "badge": _hr_admin_badge(user)})
    return apps
