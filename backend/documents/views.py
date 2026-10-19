"""Document configuration and approved-document access views.

The template endpoints are HR-owned configuration (Unit 10). The approved
document endpoints (Unit 23b D7) are read-only: a signed URL is a bearer
token, so access control is the only thing standing between a stranger and a
le employee's official approval letter.
"""

import logging

from audit.models import AuditEntry
from audit.services import changed_fields, record_audit
from rest_framework import generics, permissions, response, status
from rest_framework.views import APIView

from users.permissions import IsHRRole

from .models import ApprovedLeaveDocument
from .serializers import (
    ApprovedLeaveDocumentFeedSerializer,
    LeaveDocumentTemplateSerializer,
)
from .services import approved_document_payload, get_template

logger = logging.getLogger(__name__)

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


# ---------------------------------------------------------------------------
# Approved documents (Unit 23b D7) — read-only, signed URLs minted per request
# ---------------------------------------------------------------------------

_NOT_FOUND = {"error": "Approved document not found."}


def _approved_document_payload(document) -> dict:
    """The single-document payload (signing + availability rules).

    Delegates to :func:`documents.services.approved_document_payload` so the
    detail view and the list feed mint URLs through one implementation.
    """
    return approved_document_payload(document)


def _approved_document_or_404(user, application_id, *, hr_allowed: bool):
    """The application's document when ``user`` may read it, else ``None``.

    Keyed by **application** rather than by document: every surface that shows
    this already holds the application id, so this avoids making three payload
    serializers carry a document id they would otherwise never use.

    A stranger — authenticated, but neither the owner, HR, nor an approver of
    the application — gets ``None`` so the response is indistinguishable from
    an unknown id. A signed URL is a bearer token, so the endpoint must not
    confirm which applications or documents exist.
    """
    from users.models import User
    from workflows.policies import get_view_access

    document = (
        ApprovedLeaveDocument.objects.select_related("application")
        .filter(application_id=application_id)
        .first()
    )
    if document is None:
        return None

    application = document.application
    is_owner = application.employee_id == user.id
    is_hr = getattr(user, "role", None) == User.Role.HR
    if is_owner or (hr_allowed and is_hr):
        return document
    if get_view_access(user, application) is not None:
        return document
    return None


class ApprovedLeaveDocumentView(APIView):
    """Read an application's approved document as its owner or an approver.

    GET only. See :func:`_approved_document_or_404` for why an unauthorised
    caller sees a 404 rather than a 403.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, application_id):
        document = _approved_document_or_404(
            request.user, application_id, hr_allowed=True
        )
        if document is None:
            return response.Response(_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
        return response.Response(
            _approved_document_payload(document), status=status.HTTP_200_OK
        )


class HRAApprovedLeaveDocumentView(ApprovedLeaveDocumentView):
    """HR-scoped read of any application's approved document, for the audit trail.

    Same payload and same GET-only contract, but the HR route is not a secret
    route, so a non-HR caller is refused with a 403 by ``IsHRRole`` rather than
    being led to believe the document does not exist.
    """

    permission_classes = [permissions.IsAuthenticated, IsHRRole]


class MyApprovedLeaveDocumentsView(generics.ListAPIView):
    """The caller's own approved documents, newest first (documents module).

    Owner-scoped: only documents whose application belongs to the caller. Every
    status is included so the feed can show a document that is still being
    prepared (or failed) rather than hiding it. Paginated by the project-wide
    page-number default.

    No signed URL is minted per row (see the serializer): a list would otherwise
    make one storage round-trip per document, which is what made the documents
    page slow. The client asks for a single fresh URL when it opens a row, via
    the per-application view above.
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ApprovedLeaveDocumentFeedSerializer

    def get_queryset(self):
        return (
            ApprovedLeaveDocument.objects.filter(
                application__employee=self.request.user
            )
            .select_related("application")
            .order_by("-created_at")
        )

