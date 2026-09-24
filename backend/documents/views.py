from rest_framework import permissions, response, status
from rest_framework.views import APIView

from audit.services import record_config_change
from users.permissions import IsHRRole

from .serializers import LeaveDocumentTemplateSerializer
from .services import get_template

TEMPLATE_AUDIT_FIELDS = (
    "title",
    "header",
    "intro",
    "fields",
    "closing",
    "signature_areas",
    "footer",
)


def _template_snapshot(template) -> dict:
    return {
        field: getattr(template, field, None)
        for field in TEMPLATE_AUDIT_FIELDS
    }


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
        before = _template_snapshot(template)
        serializer = LeaveDocumentTemplateSerializer(
            template, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        record_config_change(
            actor=request.user,
            action="document_template.updated",
            target=template,
            before=before,
            after=_template_snapshot(template),
        )
        return response.Response(serializer.data, status=status.HTTP_200_OK)