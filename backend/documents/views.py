from rest_framework import permissions, response, status
from rest_framework.views import APIView

from users.permissions import IsHRRole

from .serializers import LeaveDocumentTemplateSerializer
from .services import get_template


class LeaveDocumentTemplateView(APIView):
    """HR-only access to the single official leave-document template.

    A singleton: GET returns the current configuration (creating the editable
    default on first access) plus the backend-owned field catalog, PATCH updates
    the wording/labels/order/signature areas. Values for approved applications
    are never editable here.
    """

    permission_classes = [permissions.IsAuthenticated, IsHRRole]

    def get(self, request):
        template = get_template()
        return response.Response(
            LeaveDocumentTemplateSerializer(template).data,
            status=status.HTTP_200_OK,
        )

    def patch(self, request):
        template = get_template()
        serializer = LeaveDocumentTemplateSerializer(
            template, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return response.Response(serializer.data, status=status.HTTP_200_OK)