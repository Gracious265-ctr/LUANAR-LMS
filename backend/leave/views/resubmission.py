"""Views for the Unit 17 resubmission API.

Paths (all behind JWT auth, ownership enforced server-side):

- ``GET/PATCH  /api/v1/applications/{id}/resubmission/``
- ``POST       /api/v1/applications/{id}/resubmission/documents/``
- ``POST       /api/v1/applications/{id}/resubmission/documents/{document_id}/replace/``
- ``DELETE     /api/v1/applications/{id}/resubmission/documents/{document_id}/``
- ``POST       /api/v1/applications/{id}/resubmit/``

Every error body follows the shared Unit 1 convention: ``{code, detail}`` for
conflicts and 404s, ``{code, errors: [{code, field, message}]}`` for validation
failures. ``row_version`` is required on every mutating call.
"""

from rest_framework import permissions, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from leave.models import LeaveApplication
from leave.serializers.resubmission import (
    DocumentRowVersionSerializer,
    RowVersionSerializer,
    SaveChangesSerializer,
)
from leave.services import resubmission
from leave.services.issue_payloads import issue_payload
from leave.services.resubmission import (
    ApplicationNotFoundError,
    ApproverUnavailableError,
    DocumentNotFoundError,
    InvalidContentError,
    NotEditableError,
    NotResubmittableError,
    ValidationFailedError,
    VersionConflictError,
    WorkflowInconsistentError,
)

DETAIL_NOT_FOUND = "The application does not exist or does not belong to you."


class ApplicationResubmissionView(APIView):
    """Edit context (GET) and in-place save (PATCH)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        try:
            payload = resubmission.get_edit_context(pk, request.user)
        except ApplicationNotFoundError:
            return Response(
                {"detail": DETAIL_NOT_FOUND},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(payload)

    def patch(self, request, pk):
        serializer = SaveChangesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        body = serializer.validated_data
        try:
            payload = resubmission.save_changes(
                application_id=pk,
                actor=request.user,
                leave_type_id=body["leave_type_id"],
                start_date=body["start_date"],
                end_date=body["end_date"],
                reason=body["reason"],
                expected_row_version=body["row_version"],
            )
        except ApplicationNotFoundError:
            return _not_found()
        except NotEditableError:
            return _conflict(
                "not_editable",
                "This application can no longer be edited.",
            )
        except VersionConflictError:
            return _conflict(
                "version_conflict",
                "This application was changed in another window.",
            )
        except InvalidContentError as exc:
            return _validation_failed(exc.errors)
        return Response(payload)


class ResubmissionDocumentCollectionView(APIView):
    """Add a document to a rejected / correction-required application."""

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, pk):
        file = request.FILES.get("file")
        if file is None:
            return _validation_failed(
                [
                    {
                        "code": "FILE_REQUIRED",
                        "field": "file",
                        "message": "Choose a file to upload.",
                    }
                ]
            )
        row_version = _row_version_from_form(request)
        try:
            payload = resubmission.add_document(
                application_id=pk,
                actor=request.user,
                file=file,
                expected_row_version=row_version,
            )
        except ApplicationNotFoundError:
            return _not_found()
        except NotEditableError:
            return _conflict(
                "not_editable",
                "This application can no longer be edited.",
            )
        except VersionConflictError:
            return _conflict(
                "version_conflict",
                "This application was changed in another window.",
            )
        return Response(payload)


class ResubmissionDocumentReplaceView(APIView):
    """Replace (retire + upload) one active document."""

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, pk, document_id):
        file = request.FILES.get("file")
        if file is None:
            return _validation_failed(
                [
                    {
                        "code": "FILE_REQUIRED",
                        "field": "file",
                        "message": "Choose a file to upload.",
                    }
                ]
            )
        row_version = _row_version_from_form(request)
        try:
            payload = resubmission.replace_document(
                application_id=pk,
                actor=request.user,
                document_id=document_id,
                file=file,
                expected_row_version=row_version,
            )
        except ApplicationNotFoundError:
            return _not_found()
        except DocumentNotFoundError:
            return _not_found()
        except NotEditableError:
            return _conflict(
                "not_editable",
                "This application can no longer be edited.",
            )
        except VersionConflictError:
            return _conflict(
                "version_conflict",
                "This application was changed in another window.",
            )
        return Response(payload)


class ResubmissionDocumentDetailView(APIView):
    """Remove (retire) one active document."""

    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, pk, document_id):
        row_version = _row_version_from_request(request)
        try:
            payload = resubmission.remove_document(
                application_id=pk,
                actor=request.user,
                document_id=document_id,
                expected_row_version=row_version,
            )
        except ApplicationNotFoundError:
            return _not_found()
        except DocumentNotFoundError:
            return _not_found()
        except NotEditableError:
            return _conflict(
                "not_editable",
                "This application can no longer be edited.",
            )
        except VersionConflictError:
            return _conflict(
                "version_conflict",
                "This application was changed in another window.",
            )
        return Response(payload)


class ApplicationResubmitView(APIView):
    """Validate and resubmit the application back to its stage."""

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser, FormParser]

    def post(self, request, pk):
        serializer = RowVersionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            application = resubmission.resubmit(
                application_id=pk,
                actor=request.user,
                expected_row_version=serializer.validated_data["row_version"],
            )
        except ApplicationNotFoundError:
            return _not_found()
        except NotResubmittableError:
            return _conflict(
                "not_resubmittable",
                "This application cannot be resubmitted in its current state.",
            )
        except VersionConflictError:
            return _conflict(
                "version_conflict",
                "This application was changed in another window.",
            )
        except WorkflowInconsistentError:
            return _conflict(
                "workflow_inconsistent",
                "The application state does not match the approval stage.",
            )
        except ApproverUnavailableError as exc:
            return _conflict("approver_unavailable", exc.message)
        except ValidationFailedError as exc:
            return _validation_failed(
                [issue_payload(issue) for issue in exc.errors]
            )
        return Response(
            {
                "id": str(application.id),
                "reference": application.reference_number,
                "status": application.status,
                "submission_cycle": application.submission_cycle,
            }
        )


def _row_version_from_form(request) -> int:
    """Parse ``row_version`` from a multipart field with serializer validation."""
    serializer = DocumentRowVersionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data["row_version"]


def _row_version_from_request(request) -> int:
    """Parse ``row_version`` from a query param, form field or JSON body."""
    serializer = RowVersionSerializer(data=request.query_params.dict() or request.data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data["row_version"]


def _not_found():
    return Response({"detail": DETAIL_NOT_FOUND}, status=status.HTTP_404_NOT_FOUND)


def _conflict(code, detail):
    return Response(
        {"code": code, "detail": detail},
        status=status.HTTP_409_CONFLICT,
    )


def _validation_failed(errors):
    return Response(
        {"code": "validation_failed", "errors": errors},
        status=status.HTTP_400_BAD_REQUEST,
    )