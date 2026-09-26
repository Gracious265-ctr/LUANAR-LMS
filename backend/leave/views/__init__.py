import logging
from datetime import date, datetime

from django.conf import settings
from django.http import FileResponse, Http404
from django.utils import timezone
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import IsHRRole

from documents.models import ApprovedLeaveDocument
from workflows.policies import can_view_approved_document

from ..models import (
    FinancialYear,
    GradeEntitlement,
    LeaveApplication,
    LeaveRule,
    LeaveType,
    PublicHoliday,
    SupportingDocument,
)
from ..permissions import IsOwner
from ..serializers import (
    FinancialYearSerializer,
    GradeEntitlementSerializer,
    LeaveApplicationSerializer,
    LeaveRuleSerializer,
    LeaveTypeSerializer,
    PublicHolidaySerializer,
    SupportingDocumentSerializer,
)
from ..services import documents, normalize_grade, resolve_grade_entitlement
from ..services.working_days import calculate_working_days
from ..storage import get_storage_backend

logger = logging.getLogger(__name__)


class GradeEntitlementViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """HR-only CRUD for grade/entitlement rules (no hard delete)."""

    serializer_class = GradeEntitlementSerializer
    permission_classes = [permissions.IsAuthenticated, IsHRRole]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        return GradeEntitlement.objects.all()

    @action(detail=False, methods=["get"])
    def resolve(self, request):
        """Resolve a grade to the effective entitlement rule on a date."""
        grade = request.query_params.get("grade", "")
        key = normalize_grade(grade)
        if key is None:
            return Response(
                {"detail": "The grade query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        as_of = timezone.localdate()
        as_of_raw = request.query_params.get("as_of")
        if as_of_raw:
            try:
                as_of = date.fromisoformat(as_of_raw)
            except ValueError:
                return Response(
                    {"detail": "The as_of parameter must be a valid date (YYYY-MM-DD)."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        rule = resolve_grade_entitlement(key, as_of)
        return Response(
            {
                "grade": key,
                "days": rule.days if rule else None,
                "effective_from": rule.effective_from.isoformat() if rule else None,
            }
        )

class LeaveTypeViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """HR-only CRUD for leave types (no hard delete)."""

    serializer_class = LeaveTypeSerializer
    permission_classes = [permissions.IsAuthenticated, IsHRRole]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        return LeaveType.objects.all()


class LeaveRuleViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """HR-only CRUD for effective-dated leave rules (no hard delete)."""

    serializer_class = LeaveRuleSerializer
    permission_classes = [permissions.IsAuthenticated, IsHRRole]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        queryset = LeaveRule.objects.all()
        leave_type = self.request.query_params.get("leave_type")
        if leave_type:
            queryset = queryset.filter(leave_type=leave_type)
        effective = self.request.query_params.get("effective")
        if effective == "current":
            queryset = queryset.filter(effective_from__lte=timezone.localdate())
        elif effective == "upcoming":
            queryset = queryset.filter(effective_from__gt=timezone.localdate())
        return queryset


class FinancialYearViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """HR-only CRUD for configured financial-year periods (no hard delete)."""

    serializer_class = FinancialYearSerializer
    permission_classes = [permissions.IsAuthenticated, IsHRRole]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        return FinancialYear.objects.all()


class PublicHolidayViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """HR-only CRUD for configured public holidays (no hard delete)."""

    serializer_class = PublicHolidaySerializer
    permission_classes = [permissions.IsAuthenticated, IsHRRole]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        queryset = PublicHoliday.objects.all()
        year = self.request.query_params.get("year")
        if year:
            queryset = queryset.filter(date__year=year)
        return queryset


class LeaveApplicationViewSet(viewsets.ModelViewSet):
    serializer_class = LeaveApplicationSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        qs = LeaveApplication.objects.filter(employee=self.request.user)
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    def perform_create(self, serializer):
        serializer.save(employee=self.request.user, status=LeaveApplication.Status.DRAFT)
        instance = serializer.instance
        if instance.start_date and instance.end_date:
            instance.calculated_days = calculate_working_days(
                instance.start_date, instance.end_date
            )
            instance.save(update_fields=["calculated_days"])

    def perform_update(self, serializer):
        instance = serializer.save()
        if instance.start_date and instance.end_date:
            instance.calculated_days = calculate_working_days(
                instance.start_date, instance.end_date
            )
            instance.save(update_fields=["calculated_days"])

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status != LeaveApplication.Status.DRAFT:
            return Response(
                {"detail": "Submitted applications cannot be edited."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status != LeaveApplication.Status.DRAFT:
            return Response(
                {"detail": "Submitted applications cannot be edited."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().partial_update(request, *args, **kwargs)

    def perform_destroy(self, instance):
        if instance.status != LeaveApplication.Status.DRAFT:
            raise ValidationError("Submitted applications cannot be deleted.")
        documents.delete_draft_documents(instance)
        instance.delete()

    @action(detail=False, methods=["post"], url_path="preview-days")
    def preview_days(self, request):
        start_date = request.data.get("start_date")
        end_date = request.data.get("end_date")
        if not start_date or not end_date:
            return Response(
                {"detail": "start_date and end_date are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {"detail": "Invalid date format. Use YYYY-MM-DD."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        days = calculate_working_days(start, end)
        return Response({"days": days})

    @action(detail=True, methods=["get"], url_path="approved-document")
    def approved_document(self, request, *args, **kwargs):
        """Stream the official approved-leave PDF for this application.

        Visible to the employee, workflow members and HR only (Unit 23);
        anything else is 404 so existence is never leaked. Mirrors the Unit 19
        ``content`` action — the application is resolved directly rather than
        through ``get_object`` so the ``IsOwner`` scoping never blocks
        approvers and HR.
        """
        application = LeaveApplication.objects.filter(id=self.kwargs["pk"]).first()
        if (
            application is None
            or not can_view_approved_document(request.user, application)
        ):
            raise Http404(
                "No approved document matches the given query."
            )
        document = ApprovedLeaveDocument.objects.filter(
            application=application
        ).first()
        if document is None:
            raise Http404("No approved document matches the given query.")
        stream = get_storage_backend().open(document.file_path)
        return FileResponse(
            stream,
            content_type=document.content_type,
            as_attachment=bool(request.query_params.get("download")),
            filename=document.file_name,
        )


class LeaveDocumentConfigView(APIView):
    """Server-driven upload limits for the frontend (max size + allowed types)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(
            {
                "max_size_bytes": settings.LEAVE_DOCUMENT_MAX_SIZE_BYTES,
                "allowed_content_types": settings.LEAVE_DOCUMENT_ALLOWED_TYPES,
            }
        )


class SupportingDocumentViewSet(viewsets.ModelViewSet):
    """Supporting-document lifecycle (Unit 19), backed by the service module.

    HTTP verbs are list/retrieve/create/destroy plus the ``replace``, ``content``
    and ``history`` actions. Ownership and the status gate are enforced in the
    service; retired documents never appear in the default queryset or the
    ``content`` endpoint.
    """

    serializer_class = SupportingDocumentSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]
    parser_classes = [MultiPartParser, FormParser]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        owned = LeaveApplication.objects.filter(
            id=self.kwargs["application_pk"], employee=self.request.user
        ).exists()
        if not owned:
            raise Http404
        return documents.active_documents_queryset(self.kwargs["application_pk"])

    def _document_error_response(self, exc):
        if exc.code == "document_read_only":
            return Response(
                {"code": exc.code, "detail": exc.message},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(
            {"field": exc.field, "code": exc.code, "message": exc.message},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            document = documents.add_document(
                application_id=self.kwargs["application_pk"],
                actor=request.user,
                file=request.FILES.get("file"),
            )
        except documents.ApplicationNotFoundError:
            raise Http404
        except documents.DocumentError as exc:
            return self._document_error_response(exc)
        documents.set_content_url(document, request)
        serializer = self.get_serializer(document)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            documents.remove_document(
                application_id=self.kwargs["application_pk"],
                document_id=instance.id,
                actor=request.user,
            )
        except documents.DocumentError as exc:
            return self._document_error_response(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="replace")
    def replace_document(self, request, *args, **kwargs):
        try:
            document = documents.replace_document(
                application_id=self.kwargs["application_pk"],
                document_id=self.kwargs["pk"],
                actor=request.user,
                file=request.FILES.get("file"),
            )
        except documents.ApplicationNotFoundError:
            raise Http404
        except documents.DocumentNotFoundError:
            raise Http404
        except documents.DocumentError as exc:
            return self._document_error_response(exc)
        documents.set_content_url(document, request)
        return Response(SupportingDocumentSerializer(document).data)

    @action(detail=True, methods=["get"], url_path="content")
    def content(self, request, *args, **kwargs):
        application = LeaveApplication.objects.filter(
            id=self.kwargs["application_pk"]
        ).first()
        if application is None or not documents.can_view_content(
            request.user, application
        ):
            raise Http404(
                "No supporting document matches the given query."
            )
        document = (
            documents.active_documents_queryset(self.kwargs["application_pk"])
            .filter(id=self.kwargs["pk"])
            .first()
        )
        if document is None:
            raise Http404("No supporting document matches the given query.")
        stream, content_type, file_name = documents.get_document_content(document)
        return FileResponse(
            stream,
            content_type=content_type,
            as_attachment=bool(request.query_params.get("download")),
            filename=file_name,
        )

    @action(detail=False, methods=["get"], url_path="history")
    def history(self, request, *args, **kwargs):
        try:
            payload = documents.get_document_history(
                self.kwargs["application_pk"], request.user
            )
        except documents.ApplicationNotFoundError:
            raise Http404
        return Response(payload)
