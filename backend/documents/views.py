"""Document configuration and approved-document access views.

The template endpoints are HR-owned configuration (Unit 10). The approved
document endpoints (Unit 23b D7) are read-only: a signed URL is a bearer
token, so access control is the only thing standing between a stranger and a
le employee's official approval letter.
"""

import logging

from audit.models import AuditEntry
from audit.services import changed_fields, record_audit
from rest_framework import permissions, response, status
from rest_framework.views import APIView

from users.permissions import IsHRRole

from .models import ApprovedLeaveDocument
from .serializers import LeaveDocumentTemplateSerializer
from .services import get_template

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
    """The document's public shape, with a signed URL only when one exists.

    A ``pending`` or ``failed`` row reports its status and
    ``available: False`` so the client can say "being prepared" from the first
    response rather than needing a second request to discover there is
    nothing to open.

    Minting the signed URL is enrichment on top of the document row, not the
    row itself, so a storage problem degrades the payload instead of failing
    the request. ``available`` is an explicit promise that ``download_url``
    opens *now*; when a fresh URL cannot be minted the promise is withdrawn
    rather than served from the render-time URL, which by then has expired and
    would hand the employee a dead link. The other storage call sites fall back
    to that stored URL because they are best-effort listings, but this payload
    is the one the UI keys an "Open" button off, so no button is honest and a
    broken link is not.
    """
    from leave.services.storage import signed_document_url

    available = document.status == ApprovedLeaveDocument.Status.READY
    payload = {
        "id": str(document.pk),
        "application": str(document.application_id),
        "status": document.status,
        "available": available,
        "file_name": document.file_name or "",
        "content_type": document.content_type or "",
        "file_size": document.file_size or 0,
        "approved_on": document.approved_on,
        "rendered_at": document.rendered_at,
        "created_at": document.created_at,
        "download_url": "",
    }
    if available and document.file_path:
        # Signed URLs expire, so re-sign from the stored path rather than
        # handing back the URL captured at render time.
        try:
            payload["download_url"] = signed_document_url(document.file_path)
        except Exception:
            logger.exception(
                "Could not sign a download URL for approved document %s; "
                "reporting it as unavailable rather than failing the request.",
                document.pk,
            )
            payload["available"] = False
    return payload


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

