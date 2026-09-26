"""Unit 16 approvals API views.

Authentication is always the JWT identity (invariants 12.2/12.6); no employee
or approver id is ever read from the client. Every request routes through the
policies module, so the frontend never decides who may act.
"""

from django.db.models import Max, Prefetch, Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from leave.models import LeaveApplication, SupportingDocument
from leave.storage import get_storage_backend

from .approvals_serializers import (
    CONFIGURED_PAGE_SIZE,
    MAX_PAGE_SIZE,
    ApprovalDecisionInputSerializer,
    ApprovalDetailSerializer,
    ApprovalListItemSerializer,
)
from .errors import DecisionValidationError, NotAllowed, StageChanged
from .models import ApplicationStage, ApprovalDecision
from .policies import get_view_access
from .approval import decide


def _review_payload(application, user, view_access, request) -> dict:
    return ApprovalDetailSerializer(
        application, context={"user": user, "view_access": view_access, "request": request}
    ).data


def _load_application(application_id):
    return get_object_or_404(
        LeaveApplication.objects.select_related(
            "employee", "employee__employee_profile"
        ).prefetch_related(
            "stages",
            "documents",
            "revisions",
            Prefetch(
                "approval_decisions",
                queryset=ApprovalDecision.objects.select_related("stage"),
            ),
        ),
        id=application_id,
    )


def _view_access_or_404(user, application):
    view_access = get_view_access(user, application)
    if view_access is None:
        raise Http404("No application matches the given query.")
    return view_access


class ApprovalCapabilitiesView(APIView):
    """`{is_approver, pending_count}` driving the sidebar visible/state."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        stages = ApplicationStage.objects.filter(
            assigned_approver=request.user
        )
        pending_count = stages.filter(status=ApplicationStage.Status.PENDING).count()
        return Response(
            {"is_approver": stages.exists(), "pending_count": pending_count}
        )


class ApprovalListView(APIView):
    """Paginated approvals list: ``?tab=pending|decided&q=&page=&page_size=``."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        tab = request.query_params.get("tab", "pending")
        q = (request.query_params.get("q") or "").strip()

        if tab == "decided":
            queryset, decisions_map = self._decided_queryset(request.user)
        else:
            queryset, decisions_map = self._pending_queryset(request.user)

        if q:
            queryset = queryset.filter(
                Q(reference_number__icontains=q)
                | Q(employee__username__icontains=q)
                | Q(employee__first_name__icontains=q)
                | Q(employee__last_name__icontains=q)
            )

        paginator = PageNumberPagination()
        paginator.page_size = CONFIGURED_PAGE_SIZE
        paginator.page_size_query_param = "page_size"
        paginator.max_page_size = MAX_PAGE_SIZE
        page = paginator.paginate_queryset(queryset, request)

        payload = ApprovalListItemSerializer(
            page,
            many=True,
            context={"my_decisions_by_application": decisions_map},
        )
        return paginator.get_paginated_response(payload.data)

    def _pending_queryset(self, user):
        queryset = (
            LeaveApplication.objects.filter(
                current_stage__assigned_approver=user,
                current_stage__status=ApplicationStage.Status.PENDING,
            )
            .select_related("employee", "employee__employee_profile")
            .order_by("submitted_at", "id")
        )
        return queryset, {}

    def _decided_queryset(self, user):
        decisions = ApprovalDecision.objects.filter(approver=user)
        latest = Max(
            "approval_decisions__decided_at", filter=Q(approval_decisions__approver=user)
        )
        # Unit 17: exclude applications whose current stage is this user's and
        # currently pending — a resubmitted application shows only in Pending.
        queryset = (
            LeaveApplication.objects.filter(approval_decisions__approver=user)
            .exclude(
                current_stage__assigned_approver=user,
                current_stage__status=ApplicationStage.Status.PENDING,
            )
            .distinct()
            .annotate(_last_decided=latest)
            .order_by("-_last_decided")
            .select_related("employee", "employee__employee_profile")
        )
        decisions_map = {
            decision.application_id: decision for decision in decisions
        }
        return queryset, decisions_map


class ApprovalDetailView(APIView):
    """Full review payload for one application, 404 when not visible."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, application_id):
        application = _load_application(application_id)
        view_access = _view_access_or_404(request.user, application)
        return Response(
            _review_payload(application, request.user, view_access, request)
        )


class ApprovalDecisionView(APIView):
    """Record exactly one decision and return the updated review payload."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, application_id):
        payload = ApprovalDecisionInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        application = _load_application(application_id)
        try:
            decide(
                application_id=application.id,
                actor=request.user,
                action=payload.validated_data["action"],
                comment=payload.validated_data.get("comment", ""),
                expected_stage_version=payload.validated_data["stage_version"],
            )
        except NotAllowed as exc:
            if exc.reason == "application_cancelled":
                return Response(
                    {
                        "code": "application_cancelled",
                        "detail": "This application was cancelled and can no longer be decided.",
                    },
                    status=status.HTTP_409_CONFLICT,
                )
            return Response(
                {"detail": f"Decision not allowed ({exc.reason})."},
                status=status.HTTP_403_FORBIDDEN,
            )
        except StageChanged:
            return Response(
                {"detail": "This application has changed since you opened it."},
                status=status.HTTP_409_CONFLICT,
            )
        except DecisionValidationError as exc:
            return Response(
                {exc.field: [exc.message]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        application = _load_application(application.id)
        view_access = _view_access_or_404(request.user, application)
        return Response(_review_payload(application, request.user, view_access, request))


class ApprovalDocumentDownloadView(APIView):
    """Short-lived signed URL for one of the application's supporting documents."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, application_id, document_id):
        application = _load_application(application_id)
        _view_access_or_404(request.user, application)

        document = SupportingDocument.objects.filter(
            application=application,
            id=document_id,
            status=SupportingDocument.Status.ACTIVE,
        ).first()
        if document is None:
            raise Http404("No document matches the given query.")

        try:
            url = get_storage_backend().signed_url(document.file_path, expires=60)
        except ValueError:
            return Response(
                {"detail": "Document download is unavailable."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({"url": url})