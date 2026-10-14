"""The custom admin site backing ``/system-admin/``.

Registered as the admin app's ``default_site``, so ``admin.site`` *is* an
instance of this class and every existing ``@admin.register`` decorator keeps
working unchanged. The only behaviour we add is a superuser-only dashboard
context on the index and two health URLs. The site ``name`` stays ``"admin"`` so
``{% url 'admin:...' %}`` and the login/logout flow are untouched.
"""

from django.conf import settings
from django.contrib.admin import AdminSite
from django.urls import path

from .health import gather_health_status
from .services import (
    TIER_SUPERUSER,
    gather_dashboard_stats,
    get_dashboard_tier,
    get_recent_admin_actions,
)
from .views import health_check_view, test_email_view


class LuanarAdminSite(AdminSite):
    site_title = "LUANAR Admin"
    index_title = "System dashboard"
    index_template = "admin/system_admin_index.html"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.site_header = settings.ADMIN_SITE_HEADER

    def has_permission(self, request):
        return bool(request.user.is_active and request.user.is_staff)

    def get_urls(self):
        custom = [
            path(
                "health/",
                self.admin_view(health_check_view),
                name="system-health",
            ),
            path(
                "health/test-email/",
                self.admin_view(test_email_view),
                name="system-test-email",
            ),
        ]
        return custom + super().get_urls()

    def index(self, request, extra_context=None):
        extra_context = dict(extra_context or {})
        tier = get_dashboard_tier(request.user)
        extra_context["dashboard_tier"] = tier
        if tier == TIER_SUPERUSER:
            extra_context["stats"] = gather_dashboard_stats()
            extra_context["health"] = gather_health_status()
            extra_context["recent_admin_actions"] = get_recent_admin_actions()
        return super().index(request, extra_context)
