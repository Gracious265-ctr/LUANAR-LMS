from django.urls import path

from .views import LauncherAppsView

urlpatterns = [
    path("launcher/", LauncherAppsView.as_view(), name="launcher-apps"),
]
