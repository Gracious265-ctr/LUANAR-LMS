"""Supporting-document endpoints (Unit 19).

Employee-scoped, owner-only document operations on a leave application:

- ``GET    .../documents/`` — active rows by default; ``?include_retired=true``
  adds retired rows with their lifecycle fields for the archive view.
- ``POST   .../documents/`` — upload on editable statuses (``draft``,
  ``rejected``); any other status returns 409 ``application_not_editable``.
- ``DELETE .../documents/{pk}/`` — remove; hard in a draft, retire otherwise.
- ``POST   .../documents/{pk}/replace/`` — replace on ``rejected``
  only; retires the old row and returns the new one plus ``retired_document``.

Authorization mirrors the rest of the employee API: another employee's
application/document resolves to a 404, never a 403.
"""

from django.http import Http404
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from ..documents import services as document_services
from ..documents.services import (
    DocumentNotActiveError,
    DocumentNotEditableError,
)
from ..models import LeaveApplication, SupportingDocument
from ..permissions import IsOwner
from ..serializers import SupportingDocumentFeedSerializer, SupportingDocumentSerializer
from ..services.storage import StorageUnavailableError


class SupportingDocumentViewSet(viewsets.ViewSet):
    """Employee-scoped document operations on their own leave applications."""

    permission_classes = [permissions.IsAuthenticated, IsOwner]
    parser_classes = [MultiPartParser, FormParser]
    serializer_class = SupportingDocumentSerializer

    def _application(self, request):
        application = LeaveApplication.objects.filter(
            id=self.kwargs["application_pk"], employee=request.user
        ).first()
        if application is None:
            raise Http404("Leave application not found.")
        return application

    def _document(self, application, pk):
        document = SupportingDocument.objects.filter(
            application=application, pk=pk
        ).first()
        if document is None:
            raise Http404("Document not found.")
        return document

    def _serializer(self, documents, many=False):
        return SupportingDocumentSerializer(
            documents, many=many, context={"request": self.request}
        )

    def list(self, request, application_pk=None):
        application = self._application(request)
        queryset = SupportingDocument.objects.filter(application=application)
        if request.query_params.get("include_retired") != "true":
            queryset = queryset.filter(status=SupportingDocument.Status.ACTIVE)
        return Response(
            self._serializer(queryset.order_by("-uploaded_at"), many=True).data
        )

    def retrieve(self, request, application_pk=None, pk=None):
        application = self._application(request)
        document = self._document(application, pk)
        return Response(self._serializer(document).data)

    def create(self, request, application_pk=None):
        application = self._application(request)
        try:
            document = document_services.upload(
                request.user, application, request.FILES.get("file")
            )
        except DocumentNotEditableError:
            return self._conflict(
                "application_not_editable",
                "This application is not editable. Documents can only be "
                "changed on a draft or on a rejected application.",
            )
        except ValidationError as exc:
            return self._bad_request(exc.detail)
        except StorageUnavailableError:
            return self._service_unavailable()
        return Response(
            self._serializer(document).data, status=status.HTTP_201_CREATED
        )

    def destroy(self, request, application_pk=None, pk=None):
        application = self._application(request)
        document = self._document(application, pk)
        try:
            document_services.remove(request.user, application, document)
        except DocumentNotEditableError:
            return self._conflict(
                "application_not_editable",
                "This application is not editable. Documents can only be "
                "changed on a draft or on a rejected application.",
            )
        except DocumentNotActiveError:
            return self._conflict(
                "document_not_active",
                "This document has already been removed or replaced.",
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def replace(self, request, application_pk=None, pk=None):
        application = self._application(request)
        document = self._document(application, pk)
        try:
            replacement = document_services.replace(
                request.user, application, document, request.FILES.get("file")
            )
        except DocumentNotEditableError:
            return self._conflict(
                "application_not_editable",
                "Documents can only be replaced on a rejected application.",
            )
        except DocumentNotActiveError:
            return self._conflict(
                "document_not_active",
                "This document has already been removed or replaced.",
            )
        except ValidationError as exc:
            return self._bad_request(exc.detail)
        except StorageUnavailableError:
            return self._service_unavailable()
        return Response(
            {
                "document": self._serializer(replacement).data,
                "retired_document": str(document.pk),
            },
            status=status.HTTP_201_CREATED,
        )

    def _conflict(self, code: str, detail: str) -> Response:
        return Response(
            {"code": code, "detail": detail},
            status=status.HTTP_409_CONFLICT,
        )

    def _service_unavailable(self) -> Response:
        return Response(
            {
                "code": "storage_unavailable",
                "detail": (
                    "Document storage is unavailable. Please try again shortly; "
                    "if the problem persists, contact the system administrator."
                ),
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    def _bad_request(self, detail) -> Response:
        if isinstance(detail, list):
            detail = detail[0] if detail else "Invalid request."
        return Response({"detail": str(detail)}, status=status.HTTP_400_BAD_REQUEST)


class SupportingDocumentFeedView(ListAPIView):
    """Every supporting document on the caller's leave applications.

    The documents module's supporting-documents list. Owner-scoped through
    ``application__employee`` so one employee never sees another's
    attachments; active rows by default, ``?include_retired=true`` adds the
    archive, mirroring the per-application list. Paginated by the project-wide
    page-number default.
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SupportingDocumentFeedSerializer

    def get_queryset(self):
        queryset = (
            SupportingDocument.objects.filter(
                application__employee=self.request.user
            )
            .select_related("application", "retired_by", "replaced_by")
            .order_by("-uploaded_at")
        )
        if self.request.query_params.get("include_retired") != "true":
            queryset = queryset.filter(status=SupportingDocument.Status.ACTIVE)
        return queryset