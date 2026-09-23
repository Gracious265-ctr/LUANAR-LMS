"""Small shared helpers for Unit 16 serialization and policies."""

from leave.models import LeaveType


def leave_type_name(application) -> str:
    """The application's leave-type name, taken from the snapshot first."""
    snapshot = application.rules_snapshot or {}
    name = (snapshot.get("leave_type") or {}).get("name")
    if name:
        return name
    if application.leave_type_id:
        leave_type = LeaveType.objects.filter(pk=application.leave_type_id).first()
        if leave_type is not None:
            return leave_type.name
    return ""


def full_name_for(user) -> str:
    """Display name falling back to the username for unset first/last names."""
    return user.get_full_name() or getattr(user, "username", "")


def employee_profile(instance):
    """The related employee profile, or None when missing."""
    return getattr(instance, "employee_profile", None)