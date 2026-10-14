"""Superuser-only views behind the system-admin URLs.

Admins reach these through the custom ``LuanarAdminSite.get_urls``; both views
are wrapped in ``admin_view`` there for session handling and then re-check
superuser status here, since ``admin_view`` only requires ``is_staff``.
"""

from django.contrib import messages
from django.contrib.admin import site as admin_site
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .health import gather_health_status


def _require_superuser(request) -> None:
    if not getattr(request.user, "is_superuser", False):
        raise PermissionDenied("Only superusers can view system health.")


def health_check_view(request):
    _require_superuser(request)
    context = {
        **admin_site.each_context(request),
        "title": "System health",
        "health": gather_health_status(),
    }
    return render(request, "admin/system_health.html", context)


@require_POST
def test_email_view(request):
    _require_superuser(request)
    if not request.user.email:
        messages.error(
            request,
            "Your account has no email address to send the test to.",
        )
        return HttpResponseRedirect(reverse("admin:system-health"))

    try:
        send_mail(
            subject="LUANAR Leave System — test email",
            message=(
                "This is a test message sent from the system-admin health page. "
                "If you received it, outbound email is working."
            ),
            from_email=None,
            recipient_list=[request.user.email],
            fail_silently=False,
        )
    except Exception as exc:
        messages.error(request, f"Test email failed: {exc}")
    else:
        messages.success(request, f"Test email sent to {request.user.email}.")
    return HttpResponseRedirect(reverse("admin:system-health"))
