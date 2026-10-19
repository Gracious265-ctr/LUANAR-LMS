"""Approvals HTTP API: approvals desk, cancellations, delegations, and reassignments."""

from __future__ import annotations

from uuid import UUID
from django.db import transaction
from django.core.exceptions import ValidationError
from django.db.models import Exists, OuterRef, Q, Subquery
from django.utils import timezone
from rest_framework import decorators, mixins, permissions, response, serializers, status
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import viewsets
from rest_framework import serializers as drf_serializers

from audit.validation import uuid_value
from leave.models import LeaveApplication, SupportingDocument
from leave_config.models import LeaveType
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
    SelfDecisionError,
    StaleStageVersionError,
    decide_cancellation,
)
from users.models import User
from users.permissions import IsHRRole

from approvals.models import (
    ApplicationStage,
    ApprovalDecision,
    Delegation,
    Reassignment,
)

from workflows.policies import get_view_access
from workflows.permissions import IsApproverRoleOrHR

from approvals.serializers import (
    DelegationActionSerializer,
    DelegationSerializer,
    PendingApplicationSerializer,
    ReassignmentSerializer,
)
from .payloads import (
    briefing_blocks,
    list_item,
    review_payload,
)
from organisation.services import (
    approver_role_labels_for,
    is_approver_user,
)
from .services import (
    ApprovalConflictError,
    ApprovalNotAllowedError,
    ApprovalNotFoundError,
    ApprovalStageChangedError,
    ApprovalValidationError,
    DelegationActionError,
    SelfApprovalBlockedError,
    acting_approver_map,
    acting_approver_predicate,
    approve_delegation,
    cancel_delegation,
    decide,
    reject_delegation,
)

def _may_use_approvals(user) -> bool:
    """Whether ``user`` may use the approvals API.

    Approver status is the authoritative
    :func:`~workflows.services.is_approver_user` check — an active holder of an
    active approver role. HR is admitted explicitly alongside it, so HR keeps the
    oversight access it has always had without HR needing a role assignment.
    """
    if not (user and user.is_authenticated and user.is_active):
        return False
    return is_approver_user(user) or user.role == User.Role.HR


class _ApproverOnly(permissions.BasePermission):
    """Active approvers (and HR) may use the approvals API."""

    def has_permission(self, request, view):
        return _may_use_approvals(request.user)


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
    """What the signed-in user may do on the approval desk.

    ``approver_roles`` is the live role list the user holds, so the frontend can
    describe them by the roles HR actually assigned instead of a hardcoded map.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        is_approver = _may_use_approvals(user)
        pending_count = (
            LeaveApplication.objects.filter(
                status=LeaveApplication.Status.SUBMITTED,
            )
            .filter(acting_approver_predicate(user))
            .count()
            if is_approver
            else 0
        )
        return Response(
            {
                "is_approver": is_approver,
                "approver_roles": approver_role_labels_for(user),
                "pending_count": pending_count,
            }
        )


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
        except ApprovalConflictError as exc:
            conflict = exc.conflict
            return Response(
                {
                    "error": (
                        "Approving this application would leave the team "
                        "over-subscribed on "
                        f"{conflict.day.isoformat()}."
                    ),
                    "reason": "team_conflict",
                    "conflict": {
                        "day": conflict.day.isoformat(),
                        "out_count": conflict.out_count,
                        "team_size": conflict.team_size,
                        "threshold": conflict.threshold,
                    },
                },
                status=status.HTTP_409_CONFLICT,
            )
        except SelfApprovalBlockedError as exc:
            # The approval would have to go to the applicant themself. The
            # decision is rolled back; HR must correct the workflow.
            return Response(
                {
                    "error": " ".join(exc.messages),
                    "reason": "workflow_unavailable",
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


#: A batch approval is capped so one mis-click cannot sweep a whole queue.
BULK_APPROVAL_LIMIT = 25


class BulkDecisionItemSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    stage_version = serializers.IntegerField(min_value=1)


class BulkApprovalInputSerializer(serializers.Serializer):
    """The batch decision body (spec 5): approve-only, capped, no dupes.

    Reject needs a per-item reason, so it stays one-at-a-time and is not
    accepted here.
    """

    action = serializers.ChoiceField(choices=[("approve", "approve")])
    comment = serializers.CharField(
        max_length=1000,
        required=False,
        allow_blank=True,
        default="",
        trim_whitespace=True,
    )
    items = BulkDecisionItemSerializer(many=True)

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("Select at least one application.")
        if len(value) > BULK_APPROVAL_LIMIT:
            raise serializers.ValidationError(
                f"Approve at most {BULK_APPROVAL_LIMIT} applications at once."
            )
        ids = [str(item["id"]) for item in value]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError(
                "Remove duplicate applications from the selection."
            )
        return value


class BulkApprovalDecisionAPIView(APIView):
    """Approve up to 25 applications in one request (UI/UX Phase 2, spec 3.11).

    Every item runs through the same locked :func:`~workflows.services.decide`
    path — its own transaction and its own audit row — so partial success is
    expected. The response reports each item's outcome and the totals; a single
    bad item never discards the successes around it.
    """

    permission_classes = [permissions.IsAuthenticated, _ApproverOnly]

    def post(self, request):
        serializer = BulkApprovalInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        results = []
        approved = 0
        failed = 0
        for item in data["items"]:
            item_id = str(item["id"])
            try:
                decide(
                    application_id=item["id"],
                    actor=request.user,
                    action=data["action"],
                    comment=data.get("comment") or "",
                    expected_version=item["stage_version"],
                )
            except ApprovalNotFoundError:
                results.append(
                    {"id": item_id, "status": "failed", "reason": "not_found"}
                )
                failed += 1
            except ApprovalStageChangedError:
                results.append(
                    {"id": item_id, "status": "failed", "reason": "stage_changed"}
                )
                failed += 1
            except ApprovalConflictError:
                results.append(
                    {"id": item_id, "status": "failed", "reason": "team_conflict"}
                )
                failed += 1
            except SelfApprovalBlockedError:
                results.append(
                    {
                        "id": item_id,
                        "status": "failed",
                        "reason": "workflow_unavailable",
                    }
                )
                failed += 1
            except ApprovalNotAllowedError as exc:
                results.append(
                    {"id": item_id, "status": "failed", "reason": exc.reason}
                )
                failed += 1
            except ApprovalValidationError:
                results.append(
                    {"id": item_id, "status": "failed", "reason": "validation"}
                )
                failed += 1
            else:
                results.append({"id": item_id, "status": "approved"})
                approved += 1

        return Response(
            {
                "results": results,
                "approved": approved,
                "failed": failed,
                "limit": BULK_APPROVAL_LIMIT,
            }
        )


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
        "self_application": "You cannot decide on your own application.",
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
                eligible_approvers__user=user,
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
        except SelfDecisionError:
            return Response(
                {
                    "code": "self_application",
                    "error": "You cannot decide on your own cancellation.",
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
    entitled = CancellationApprovalStage.objects.filter(
        request=request_row,
        eligible_approvers__user=user,
    ).exclude(status=CancellationApprovalStage.Status.NOT_REACHED)
    return request_row if entitled.exists() else None


class DelegateCandidateSerializer(drf_serializers.ModelSerializer):
    """Minimal approver shape for the delegate picker.

    Deliberately narrower than the HR ``EmployeeSerializer``: an approver needs
    a name and a role to pick a delegate, not the whole employee record.
    """

    full_name = drf_serializers.CharField(
        source="get_full_name", read_only=True
    )

    class Meta:
        model = User
        fields = ["id", "full_name", "role"]


class DelegationViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Delegation requests, HR decisions, and active management.

    ``create`` is open to active approvers (self-service) and HR (on behalf).
    ``list``/``retrieve`` are open to HR (everything) and to approvers, who see
    only the delegations they are a party to. The approve/reject/cancel actions
    stay HR-only.
    """

    serializer_class = DelegationSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_permissions(self):
        if self.action in ("create", "candidates"):
            return [permissions.IsAuthenticated(), IsApproverRoleOrHR()]
        if self.action in ("list", "retrieve"):
            return [permissions.IsAuthenticated(), IsApproverRoleOrHR()]
        return [permissions.IsAuthenticated(), IsHRRole()]

    def get_queryset(self):
        queryset = Delegation.objects.select_related(
            "approver", "delegate", "requested_by", "decided_by"
        )
        user = self.request.user
        if getattr(user, "role", None) != User.Role.HR:
            # An approver only ever sees their own side of the story. Scoping the
            # queryset (rather than checking per object) also makes ``retrieve``
            # 404 on someone else's delegation instead of leaking its existence.
            queryset = queryset.filter(Q(approver=user) | Q(delegate=user))
        state = self.request.query_params.get("state")
        today = timezone.localdate()
        if state == "requested":
            queryset = queryset.filter(status=Delegation.Status.REQUESTED)
        elif state == "rejected":
            queryset = queryset.filter(status=Delegation.Status.REJECTED)
        elif state == "cancelled":
            queryset = queryset.filter(status=Delegation.Status.CANCELLED)
        elif state == "scheduled":
            queryset = queryset.filter(
                status=Delegation.Status.APPROVED, starts_on__gt=today
            )
        elif state == "active":
            queryset = queryset.filter(
                status=Delegation.Status.APPROVED, starts_on__lte=today
            ).filter(Q(ends_on__isnull=True) | Q(ends_on__gte=today))
        elif state == "ended":
            queryset = queryset.filter(
                status=Delegation.Status.APPROVED, ends_on__lt=today
            )

        search = self.request.query_params.get("approver")
        if search:
            queryset = queryset.filter(
                Q(approver__first_name__icontains=search)
                | Q(approver__last_name__icontains=search)
                | Q(approver__email__icontains=search)
            )
        return queryset

    @decorators.action(detail=False, methods=["get"])
    def candidates(self, request):
        """Active approver-role users the caller may nominate as delegate.

        A self-service requester needs this to name a delegate without being
        handed the HR-only employee list. The caller is excluded, because a
        delegation to oneself is rejected on write anyway.
        """
        candidates = [
            user
            for user in User.objects.filter(is_active=True).order_by(
                "first_name", "last_name"
            )
            if is_approver_user(user) and user.pk != request.user.pk
        ]
        return response.Response(
            {
                "candidates": DelegateCandidateSerializer(
                    candidates, many=True
                ).data
            }
        )

    @decorators.action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        return self._run_action(request, pk, approve_delegation)

    @decorators.action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        return self._run_action(request, pk, reject_delegation)

    @decorators.action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        return self._run_action(request, pk, cancel_delegation)

    def _run_action(self, request, pk, service):
        delegation = self.get_object()
        payload = DelegationActionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            delegation = service(delegation, request.user, payload.validated_data)
        except DelegationActionError as exc:
            raise drf_serializers.ValidationError(
                {exc.field: [exc.message]}
            )
        return response.Response(
            DelegationSerializer(
                delegation, context=self.get_serializer_context()
            ).data,
            status=status.HTTP_200_OK,
        )


class ReassignmentViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """HR-only emergency reassignment of pending applications (no delete)."""

    serializer_class = ReassignmentSerializer
    permission_classes = [permissions.IsAuthenticated, IsHRRole]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        queryset = Reassignment.objects.select_related(
            "application__employee", "from_approver", "to_approver", "decided_by"
        )
        application = self.request.query_params.get("application")
        if application:
            queryset = queryset.filter(
                application_id=uuid_value(application, "application")
            )
        return queryset

    @decorators.action(detail=False, methods=["get"])
    def pending(self, request):
        """The intervention queue: submitted applications awaiting approval.

        Resolved in bulk so the queue stays a fixed number of queries: the
        acting approver (Unit 21 routing) is reported alongside the responsible
        one, which is what tells HR whether a reassignment would actually change
        who holds the application.
        """
        queryset = (
            LeaveApplication.objects.filter(status=LeaveApplication.Status.SUBMITTED)
            .select_related("employee", "current_approver", "current_stage")
            .order_by("-submitted_at")
        )
        page = self.paginate_queryset(queryset)
        rows = list(page) if page is not None else list(queryset)
        serializer = PendingApplicationSerializer(
            rows,
            many=True,
            context={
                "leave_type_names": dict(
                    LeaveType.objects.values_list("id", "name")
                ),
                "acting_approver_map": acting_approver_map(rows),
            },
        )
        return self.get_paginated_response(serializer.data)


