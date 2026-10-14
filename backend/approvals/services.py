def can_access_approvals(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    role = getattr(user, "role", None)
    if role in ("hr", "superuser", "approver", "hod", "dean", "registrar", "dvc"):
        return True
    if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return True
    return False


def pending_stage_count_for(user) -> int:
    try:
        from workflows.approval_views import _pending_count_for_user
        return _pending_count_for_user(user) if callable(_pending_count_for_user) else 0
    except Exception:
        try:
            from workflows import approval_views as av
            return av._pending_count_for_user(user) if hasattr(av, "_pending_count_for_user") else 0
        except Exception:
            return 0
