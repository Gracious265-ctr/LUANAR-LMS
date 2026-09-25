from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("users.urls")),
    path("api/v1/", include("leave.urls")),
    path("api/v1/", include("workflows.urls")),
    path("api/v1/", include("workflows.approvals_urls")),
    path("api/v1/", include("documents.urls")),
    path("api/v1/", include("audit.urls")),
    path("api/v1/", include("notifications.urls")),
]
