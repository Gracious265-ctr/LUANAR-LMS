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
