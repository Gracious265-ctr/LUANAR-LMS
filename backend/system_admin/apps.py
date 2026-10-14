"""App config for the system-admin dashboard.

The dashboard is an extension of Django's built-in admin, not a parallel UI.
This config re-registers the ``admin`` app label in place of
``django.contrib.admin`` and points ``default_site`` at
``system_admin.sites.LuanarAdminSite``. Because the app label stays ``admin``
(we reuse the stock app's name below), every existing ``@admin.register`` call
and the ``admin:`` URL namespace keep working without change, while the site
itself gains the ``/system-admin/`` operations surface.
"""

from django.contrib.admin.apps import AdminConfig


class SystemAdminConfig(AdminConfig):
    default_site = "system_admin.sites.LuanarAdminSite"
