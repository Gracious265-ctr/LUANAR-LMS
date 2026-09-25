"""Approver review and decision API (Unit 16, spec section 5).

Read endpoints are guarded by :func:`workflows.policies.get_view_access`; the
decision endpoint is guarded by ``get_decision_authority`` inside the locked
decision service. Unauthorised non-approvers get a 403 from role checks below
(or a 404 for applications they cannot see).
"""

from __future__ import annotations

from uuid import UUID

from django.db.models import Exists, OuterRef, Q, Subquery
from rest_framework import permissions, serializers, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from leave.models import LeaveApplication, SupportingDocument
from leave.cancellations import payloads as cancellation_payloads
from leave.cancellations.models import (
    CancellationApprovalStage,
    CancellationRequest,
)
from leave.cancellations.services import (
    CommentRequiredError,
    CommentTooLongError,
    DECISION_APPROVE,
    DECISION_REJECT,
    LeaveAlreadyStartedError,
    NotCurrentApproverError,
    RequestNotFoundError,
    RequestNotPendingError,
    StaleStageVersionError,
    decide_cancellation,
)

from .approval_payloads import (
    briefing_blocks,
    list_item,
    review_payload,
)
from .models import APPROVER_ROLE_CODES, ApplicationStage, ApprovalDecision
from .policies import get_view_access
from .services import (
    ApprovalNotFoundError,
    ApprovalNotAllowedError,
    ApprovalStageChangedError,
    ApprovalValidationError,
    acting_approver_predicate,
    decide,
)


class _ApproverOnly(permissions.BasePermission):
    """Approver roles (incl. HR) may use the approvals API."""

    def has_permission(self, request, view):
        return bool(request.user) and request.user.role in APPROVER_ROLE_CODES


class _Paginator(PageNumberPagination):
    page_size = 20
    max_page_size = 100


class ApprovalDecisionInputSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=ApprovalDecision.Action.choices)
    comment = serializers.CharField(
        max_length=1000,
        required=False,
        allow_blank=True,
        default="",
        trim_whitespace=True,
    )
    stage_version = serializers.IntegerField(min_value=1)


class ApprovalsCapabilitiesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        is_approver = user.role in APPROVER_ROLE_CODES
        pending_count = (
            LeaveApplication.objects.filter(
                status=LeaveApplication.Status.SUBMITTED,
            )
            .filter(acting_approver_predicate(user))
            .count()
            if is_approver
            else 0
        )
        return Response({"is_approver": is_approver, "pending_count": pending_count})


class ApprovalListAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, _ApproverOnly]

    def get(self, request):
        user = request.user
        tab = request.query_params.get("tab", "pending")
        tab = tab if tab in ("pending", "decided") else "pending"
        q = (request.query_params.get("q") or "").strip()

        qs = LeaveApplication.objects.select_related(
            "employee__employee_profile"
        )
        if tab == "pending":
            qs = qs.filter(status=LeaveApplication.Status.SUBMITTED).filter(
                acting_approver_predicate(user)
            )
        else:
            # Decided tab: everything the approver ever decided on, but hide a
            # row whose pipeline has since left them (a resubmission now pending
            # with a different approver keeps its place in *that* approver's
            # list instead of lingering in this one).
            qs = qs.filter(
                approval_decisions__approver=user,
            ).exclude(
                Q(current_stage__status=ApplicationStage.Status.PENDING)
                & acting_approver_predicate(user),
            ).distinct()
        if q:
            qs = qs.filter(
                Q(reference_number__icontains=q)
                | Q(employee__first_name__icontains=q)
                | Q(employee__last_name__icontains=q)
                | Q(employee__username__icontains=q)
            )
        if tab == "pending":
            qs = qs.order_by("submitted_at")
        else:
            most_recent_decision = (
                ApprovalDecision.objects.filter(
                    application=OuterRef("pk"), approver=user
                )
                .order_by("-decided_at")
                .values("decided_at")[:1]
            )
            qs = (
                qs.annotate(last_decided=Subquery(most_recent_decision))
                .order_by("-last_decided")
                .distinct()
            )

        paginator = _Paginator()
        page = paginator.paginate_queryset(qs, request, view=self)
        if page is not None:
            items = [list_item(app, user) for app in page]
            return Response(
                {
                    "tab": tab,
                    "count": paginator.page.paginator.count,
                    "next": paginator.get_next_link(),
                    "previous": paginator.get_previous_link(),
                    "results": items,
                }
            )
        items = [list_item(app, user) for app in qs]
        return Response({"tab": tab, "count": len(items), "results": items})


class ApprovalDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, _ApproverOnly]

    def get(self, request, pk):
        app, view_access = _find_viewable(request.user, pk)
        if app is None:
            return Response(
                {"error": "Approver dashboard cannot view this application."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(review_payload(app, request.user, view_access))


class ApprovalDecisionAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, _ApproverOnly]

    def post(self, request, pk):
        serializer = ApprovalDecisionInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            app = decide(
                application_id=_pk(pk),
                actor=request.user,
                action=data["action"],
                comment=data.get("comment") or "",
                expected_version=data["stage_version"],
            )
        except ApprovalNotFoundError:
            return Response(
                {"error": "Application not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except ApprovalStageChangedError:
            return Response(
                {
                    "error": "This application has already been decided. Refresh to see the latest state.",
                    "reason": "stage_changed",
                },
                status=status.HTTP_409_CONFLICT,
            )
        except ApprovalNotAllowedError as exc:
            return Response(
                {"error": _reason_message(exc.reason), "reason": exc.reason},
                status=status.HTTP_403_FORBIDDEN,
            )
        except ApprovalValidationError as exc:
            return Response(
                {"errors": exc.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(briefing_blocks(app, request.user))


class ApprovalDocumentDownloadView(APIView):
    permission_classes = [permissions.IsAuthenticated, _ApproverOnly]

    def get(self, request, pk, document_id):
        app, _view_access = _find_viewable(request.user, pk)
        if app is None:
            return Response(
                {"error": "Approver dashboard cannot view this application."},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            document_id = UUID(str(document_id))
        except (ValueError, AttributeError):
            return Response(
                {"error": "Document not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        document = SupportingDocument.objects.filter(
            application=app, pk=document_id, status="active"
        ).first()
        if document is None:
            return Response(
                {"error": "Document not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            from leave.services.storage import signed_document_url

            download_url = signed_document_url(document.file_path)
        except Exception:
            download_url = document.file_url
        return Response(
            {
                "id": str(document.id),
                "name": document.file_name,
                "content_type": document.content_type,
                "size": document.file_size,
                "download_url": download_url,
                "document_url": document.file_url,
            }
        )


def _find_viewable(user, pk):
    """The application and the caller's access, else ``(None, None)``."""
    pk = _pk(pk)
    if pk is None:
        return None, None
    app = (
        LeaveApplication.objects.filter(pk=pk)
        .select_related(
            "employee__employee_profile",
            "current_stage__assigned_approver",
        )
        .first()
    )
    if app is None:
        return None, None
    view_access = get_view_access(user, app)
    if view_access is None:
        return None, None
    return app, view_access


def _pk(value):
    try:
        return UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


def _reason_message(reason: str) -> str:
    return {
        "application_closed": "This application is closed or not awaiting your decision.",
        "already_decided": "You have already made a decision on this application.",
        "not_current_stage": "This application is not with you right now.",
    }.get(reason, "You are not allowed to decide on this application.")


class CancellationInputSerializer(serializers.Serializer):
    """The cancellation decision body (Unit 18, spec 3.5)."""

    decision = serializers.ChoiceField(
        choices=[
            (DECISION_REJECT, "reject"),
            (DECISION_APPROVE, "approve"),
        ]
    )
    comment = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=1000,
        trim_whitespace=True,
    )
    stage_version = serializers.IntegerField(min_value=1)


class CancellationListAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, _ApproverOnly]
    pagination_class = _Paginator

    def get(self, request):
        user = request.user
        tab = request.query_params.get("tab", "pending")
        tab = tab if tab in ("pending", "decided") else "pending"

        base = CancellationRequest.objects.select_related(
            "application", "application__employee"
        )
        if tab == "pending":
            # The pending stage is unique per request; correlated Exists avoids
            # a multivalued-join where an approver of a waiting stage matches a
            # request whose pending stage belongs to someone else.
            is_current = CancellationApprovalStage.objects.filter(
                request=OuterRef("pk"),
                approver=user,
                status=CancellationApprovalStage.Status.PENDING,
            )
            requests = (
                base.filter(
                    status=CancellationRequest.Status.PENDING,
                    stages__status=CancellationApprovalStage.Status.PENDING,
                )
                .annotate(_is_current=Exists(is_current))
                .filter(_is_current=True)
                .order_by("requested_at")
                .distinct()
            )
        else:
            decided_mine = CancellationApprovalStage.objects.filter(
                request=OuterRef("pk"),
                approver=user,
                decided_at__isnull=False,
            )
            latest_decided = (
                CancellationApprovalStage.objects.filter(
                    request=OuterRef("pk"),
                    approver=user,
                    decided_at__isnull=False,
                )
                .order_by("-decided_at")
                .values("decided_at")[:1]
            )
            requests = (
                base.annotate(
                    _decided_mine=Exists(decided_mine),
                    _last_decided=Subquery(latest_decided),
                )
                .filter(_decided_mine=True)
                .order_by("-_last_decided")
                .distinct()
            )

        paginator = _Paginator()
        page = paginator.paginate_queryset(requests, request, view=self)
        if page is not None:
            results = [
                cancellation_payloads.approver_row(req) for req in page
            ]
            return Response(
                {
                    "tab": tab,
                    "count": paginator.page.paginator.count,
                    "next": paginator.get_next_link(),
                    "previous": paginator.get_previous_link(),
                    "results": results,
                }
            )
        results = [
            cancellation_payloads.approver_row(req) for req in requests
        ]
        return Response(
            {
                "tab": tab,
                "count": len(results),
                "next": None,
                "previous": None,
                "results": results,
            }
        )


class CancellationDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, _ApproverOnly]

    def get(self, request, request_id):
        request_row = _find_cancellation(request.user, request_id)
        if request_row is None:
            return Response(
                {"error": "This cancellation request is not viewable."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(cancellation_payloads.approver_detail(request_row, request.user))


class CancellationDecisionAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, _ApproverOnly]

    def post(self, request, request_id):
        serializer = CancellationInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            request_row = decide_cancellation(
                user=request.user,
                request_id=request_id,
                decision=data["decision"],
                comment=data.get("comment") or "",
                stage_version=data["stage_version"],
            )
        except RequestNotFoundError:
            return Response(
                {"error": "Cancellation request not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except RequestNotPendingError:
            return Response(
                {
                    "code": "request_not_pending",
                    "error": "This cancellation request was already decided.",
                },
                status=status.HTTP_409_CONFLICT,
            )
        except StaleStageVersionError:
            return Response(
                {
                    "code": "stale_stage_version",
                    "error": "This cancellation request has changed. Refresh to see the latest stage.",
                },
                status=status.HTTP_409_CONFLICT,
            )
        except LeaveAlreadyStartedError:
            return Response(
                {
                    "code": "leave_already_started",
                    "error": "The leave has already started; only reject the cancellation.",
                },
                status=status.HTTP_409_CONFLICT,
            )
        except NotCurrentApproverError:
            return Response(
                {
                    "code": "not_current_approver",
                    "error": "This cancellation is not with you right now.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        except CommentRequiredError:
            return Response(
                {
                    "code": "comment_required",
                    "error": "A comment is required when rejecting a cancellation.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except CommentTooLongError:
            return Response(
                {
                    "code": "comment_too_long",
                    "error": "The comment must be at most 1000 characters.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(cancellation_payloads.approver_detail(request_row, request.user))


def _find_cancellation(user, request_id):
    """The cancellation request the user is a non-skipped stage approver of."""
    request_id = _pk(request_id)
    if request_id is None:
        return None
    request_row = (
        CancellationRequest.objects.filter(pk=request_id)
        .select_related("application", "application__employee", "requested_by")
        .prefetch_related("stages__approver")
        .first()
    )
    if request_row is None:
        return None
    assigned = CancellationApprovalStage.objects.filter(
        request=request_row,
        approver=user,
    ).exclude(status=CancellationApprovalStage.Status.NOT_REACHED)
    return request_row if assigned.exists() else None