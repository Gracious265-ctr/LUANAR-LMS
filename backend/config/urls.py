from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("users.urls")),
    path("api/v1/", include("leave.urls")),
    path("api/v1/", include("approvals.urls")),
    path("api/v1/", include("roles.urls")),
    path("api/v1/", include("campuses.urls")),
    path("api/v1/", include("teams.urls")),
    path("api/v1/", include("chains.urls")),
    path("api/v1/", include("plans.urls")),
    path("api/v1/", include("documents.urls")),
    path("api/v1/", include("audit.urls")),
    path("api/v1/apps/", include("launcher.urls")),
    path("api/v1/", include("leave_types.urls")),
    path("api/v1/", include("calendar_app.urls")),
    path("api/v1/", include("notifications.urls")),
]
