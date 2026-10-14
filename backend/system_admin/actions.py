"""Superuser-only account-management actions surfaced on the user changelist.

Each action is destructive in the privilege sense — it changes who can reach the
admin and every protected endpoint — so it is gated three ways: the model-admin
``permissions`` declaration hides it from non-superusers, the in-body
``_require_superuser`` guard refuses a direct call, and the change is confirmed
by typing the target username. Only then is the change applied and audited.
"""

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import render

from audit.models import AuditEntry
from audit.services import record_audit

UID_SUPERUSER_GRANT = "grant_superuser"
UID_SUPERUSER_REVOKE = "revoke_superuser"
UID_STAFF_ACCESS = "grant_staff_access"


def _require_superuser(request) -> None:
    if not getattr(request.user, "is_superuser", False):
        raise PermissionDenied("Only superusers can manage account access.")


def _single_target(request, modeladmin, queryset):
    """Return the exactly-one selected user, or report an error and return None."""
    users = list(queryset)
    if len(users) != 1:
        modeladmin.message_user(
            request,
            "Select exactly one account for this action.",
            messages.ERROR,
        )
        return None
    return users[0]


def _render_confirmation(
    request, modeladmin, user, *, action_uid, title, description
):
    context = {
        **modeladmin.admin_site.each_context(request),
        "title": title,
        "description": description,
        "action_uid": action_uid,
        "user": user,
        "opts": modeladmin.model._meta,
        "app_label": modeladmin.model._meta.app_label,
    }
    return render(request, "admin/confirm_superuser_grant.html", context)


def _audit(request, user, *, action, before, after, reason):
    record_audit(
        actor=request.user,
        action=action,
        target_type=AuditEntry.TargetType.USER_ACCOUNT,
        target_id=user.pk,
        target_summary=user.username,
        detail={"before": before, "after": after},
        reason=reason,
    )


@admin.action(
    description="Grant superuser status (requires confirmation)",
    permissions=["change"],
)
def grant_superuser(modeladmin, request, queryset):
    _require_superuser(request)
    user = _single_target(request, modeladmin, queryset)
    if user is None:
        return None
    if "confirm_username" not in request.POST:
        return _render_confirmation(
            request,
            modeladmin,
            user,
            action_uid=UID_SUPERUSER_GRANT,
            title="Grant superuser status",
            description=(
                f"This gives {user.username} unrestricted access to every model "
                "and every account-management action. Type the username to confirm."
            ),
        )
    if request.POST["confirm_username"].strip() != user.username:
        modeladmin.message_user(
            request,
            "The typed username did not match; nothing was changed.",
            messages.ERROR,
        )
        return None

    before = {"is_superuser": user.is_superuser, "is_staff": user.is_staff}
    user.is_superuser = True
    user.is_staff = True
    user.save(update_fields=["is_superuser", "is_staff"])
    _audit(
        request,
        user,
        action=AuditEntry.Action.SYSTEM_SUPERUSER_GRANTED,
        before=before,
        after={"is_superuser": True, "is_staff": True},
        reason="Granted via system-admin dashboard.",
    )
    modeladmin.message_user(
        request, f"{user.username} is now a superuser.", messages.SUCCESS
    )


@admin.action(
    description="Revoke superuser status (requires confirmation)",
    permissions=["change"],
)
def revoke_superuser(modeladmin, request, queryset):
    _require_superuser(request)
    user = _single_target(request, modeladmin, queryset)
    if user is None:
        return None
    if user.pk == request.user.pk:
        modeladmin.message_user(
            request,
            "You cannot revoke your own superuser status.",
            messages.ERROR,
        )
        return None
    if "confirm_username" not in request.POST:
        return _render_confirmation(
            request,
            modeladmin,
            user,
            action_uid=UID_SUPERUSER_REVOKE,
            title="Revoke superuser status",
            description=(
                f"This removes unrestricted access from {user.username}. They keep "
                "staff access. Type the username to confirm."
            ),
        )
    if request.POST["confirm_username"].strip() != user.username:
        modeladmin.message_user(
            request,
            "The typed username did not match; nothing was changed.",
            messages.ERROR,
        )
        return None

    before = {"is_superuser": user.is_superuser, "is_staff": user.is_staff}
    user.is_superuser = False
    user.save(update_fields=["is_superuser"])
    _audit(
        request,
        user,
        action=AuditEntry.Action.SYSTEM_SUPERUSER_REVOKED,
        before=before,
        after={"is_superuser": False, "is_staff": user.is_staff},
        reason="Revoked via system-admin dashboard.",
    )
    modeladmin.message_user(
        request,
        f"{user.username} is no longer a superuser.",
        messages.SUCCESS,
    )


@admin.action(
    description="Grant staff access (requires confirmation)",
    permissions=["change"],
)
def grant_staff_access(modeladmin, request, queryset):
    _require_superuser(request)
    user = _single_target(request, modeladmin, queryset)
    if user is None:
        return None
    if "confirm_username" not in request.POST:
        return _render_confirmation(
            request,
            modeladmin,
            user,
            action_uid=UID_STAFF_ACCESS,
            title="Grant staff access",
            description=(
                f"This lets {user.username} sign in to the admin site. Their data "
                "access still follows their group permissions. Type the username "
                "to confirm."
            ),
        )
    if request.POST["confirm_username"].strip() != user.username:
        modeladmin.message_user(
            request,
            "The typed username did not match; nothing was changed.",
            messages.ERROR,
        )
        return None

    before = {"is_staff": user.is_staff}
    user.is_staff = True
    user.save(update_fields=["is_staff"])
    _audit(
        request,
        user,
        action=AuditEntry.Action.SYSTEM_STAFF_ACCESS_GRANTED,
        before=before,
        after={"is_staff": True},
        reason="Granted via system-admin dashboard.",
    )
    modeladmin.message_user(
        request, f"{user.username} now has staff access.", messages.SUCCESS
    )
