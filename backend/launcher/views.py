from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import get_launcher_apps


class LauncherAppsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        apps = get_launcher_apps(request.user)
        return Response({"apps": apps})
