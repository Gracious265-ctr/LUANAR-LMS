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
    if getattr(user, "is_superuser", False):
        return True
    role = getattr(user, "role", None)
    if role == "hr":
        return True
    from roles.services import is_approver_user

    return is_approver_user(user)


def _approvals_badge(user) -> dict | None:
    # No badge: pending counts are surfaced by the approvals module itself.
    return None


def can_access_org(user) -> bool:
    """Whether ``user`` may open the launcher's **Teams** module.

    That module is the organisational side of leave — teams, approver roles,
    campuses and their chains — and the launcher card that admits to it carries
    the ``teams`` key.

    HR and staff administer the whole tree. A designated team manager is also
    let in, and for one reason: their team lives inside this module. A manager
    is an ordinary account — not HR, not staff — so without this the launcher
    offered them no way to reach the roster and approval chains they are the
    only people who may configure. Granting the module rather than a separate
    "team" app keeps one place to go and one set of pages to protect.
    """
    if not getattr(user, "is_authenticated", False):
        return False
    role = getattr(user, "role", None)
    if role in ("hr", "superuser"):
        return True
    if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return True
    # Imported lazily: ``organisation`` imports the launcher's siblings, and the
    # rule itself lives with the team it is about rather than being copied here.
    from roles.services import managed_team_ids_for

    return bool(managed_team_ids_for(user))


def _org_badge(user) -> dict | None:
    return None


def can_access_documents(user) -> bool:
    """Documents is every employee's own filing cabinet, scoped on read.

    The card and the module are for everyone: an employee sees only their own
    documents, a team manager also sees their teams', and HR sees the
    institution. Who may read which row is decided by
    ``documents.access.visible_employee_ids`` at the list endpoints, not here —
    this gate answers "may open the module at all", which is exactly
    "is signed in".
    """
    return bool(getattr(user, "is_authenticated", False))


def can_access_leave_types(user) -> bool:
    """Leave Configuration is an HR surface (spec 4.6).

    Delegates to ``leave_types.services.can_access_leave_types`` rather than
    restating the rule: the launcher card, the ``/leave-config`` page gate and
    the viewset permission are three views of one decision, and a copy of the
    rule here is a copy that can drift.
    """
    from leave_types.services import can_access_leave_types as gate

    return gate(user)


def can_access_calendar(user) -> bool:
    """Calendar configuration is an HR surface (refinement unit 07 §2).

    Delegates to ``calendar_app.services.can_access_calendar`` for the same
    reason ``can_access_leave_types`` delegates: the launcher card, the page
    gate and the viewset permission must be one decision, not three copies.
    """
    from calendar_app.services import can_access_calendar as gate

    return gate(user)


def get_launcher_apps(user) -> list[dict]:
    """The launcher cards ``user`` may open, as ``{"key", "badge"}`` dicts.

    ``key`` is a contract with the frontend: it is looked up in
    ``frontend/lib/apps-registry.ts``, and a key the registry does not know is
    dropped from the grid without a trace. The names below are therefore the
    *current* module names, not their pre-restructure app names — ``teams``, not
    ``org``; ``leave-config``, not ``leave-types`` — or the card silently
    disappears for every role that is entitled to it.
    """
    apps = []
    if can_access_leave(user):
        apps.append({"key": "leave", "badge": _leave_badge(user)})
    if can_access_plans(user):
        apps.append({"key": "plans", "badge": _plans_badge(user)})
    if can_access_approvals(user):
        apps.append({"key": "approvals", "badge": _approvals_badge(user)})
    if can_access_org(user):
        apps.append({"key": "teams", "badge": _org_badge(user)})
    if can_access_documents(user):
        apps.append({"key": "documents", "badge": None})
    if can_access_leave_types(user):
        apps.append({"key": "leave-config", "badge": None})
    if can_access_calendar(user):
        apps.append({"key": "calendar-app", "badge": None})
    return apps
