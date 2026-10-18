from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("users.urls")),
    path("api/v1/", include("leave.urls")),
    path("api/v1/", include("workflows.urls")),
    path("api/v1/", include("plans.urls")),
    path("api/v1/", include("documents.urls")),
    path("api/v1/", include("audit.urls")),
    path("api/v1/apps/", include("launcher.urls")),
    path("api/v1/", include("leave_config.urls")),
]
