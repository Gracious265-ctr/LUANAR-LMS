from django.urls import path

from .views import LauncherAppsView

urlpatterns = [
    path("apps/launcher/", LauncherAppsView.as_view(), name="launcher-apps"),
]
