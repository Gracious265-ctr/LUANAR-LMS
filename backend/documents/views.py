from audit.models import AuditEntry
from audit.services import changed_fields, record_audit
from rest_framework import permissions, response, status
from rest_framework.views import APIView

from users.permissions import IsHRRole

from .serializers import LeaveDocumentTemplateSerializer
from .services import get_template

_TEMPLATE_FIELDS = (
    "title",
    "header",
    "intro",
    "fields",
    "closing",
    "signature_areas",
    "footer",
)


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
        before = {field: getattr(template, field) for field in _TEMPLATE_FIELDS}
        serializer = LeaveDocumentTemplateSerializer(
            template, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        after = {field: getattr(template, field) for field in _TEMPLATE_FIELDS}
        record_audit(
            actor=request.user,
            action=AuditEntry.Action.UPDATED,
            target_type=AuditEntry.TargetType.DOCUMENT_TEMPLATE,
            target_id=template.pk,
            target_summary=template.title,
            detail=changed_fields(before, after),
        )
        return response.Response(serializer.data, status=status.HTTP_200_OK)