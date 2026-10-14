<<<<<<< HEAD
"""Views for the Unit 18 cancellation API (employee + approver).

Paths:
- GET    /api/applications/{id}/cancellation-eligibility/
- POST   /api/applications/{id}/cancel/
- GET    /api/applications/{id}/cancellations/
- GET    /api/approvals/cancellations/?tab=pending|decided
- GET    /api/approvals/cancellations/{request_id}/
- POST   /api/approvals/cancellations/{request_id}/decision/

Error responses carry ``{"code", "detail"}``; HTTP statuses follow section 3.8
(400 for client-body failures, 403 for wrong approver, 404 for unknown or
unowned resources, 409 for stale/conflicting state, 422 for a missing
approval chain).
"""

from rest_framework import permissions, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from workflows.approvals_serializers import CONFIGURED_PAGE_SIZE, MAX_PAGE_SIZE

from ..models import (
    CancellationApprovalStage,
    CancellationRequest,
    LeaveApplication,
)
from ..providers import get_today
from .serializers import CancellationDecisionSerializer, SubmitCancellationSerializer
from .services import (
    ActionChangedError,
    ApplicationNotFoundError,
    CommentRequiredError,
    ConfirmationRequiredError,
    LeaveAlreadyStartedError,
    NoCancellationApproversError,
    NotCurrentApproverError,
    OpenRequestExistsError,
    ReasonTooLongError,
    ReasonTooShortError,
    RequestNotPendingError,
    StaleStageVersionError,
    decide_cancellation,
    get_balance_provider,
    get_eligibility,
    submit_cancellation,
)


def _iso(value):
    if not value:
        return None
    return value.isoformat().replace("+00:00", "Z")


def _stage_payload(stage) -> dict:
    return {
        "order": stage.order,
        "role": stage.role,
        "role_label": stage.role_label,
        "approver_name": stage.approver.get_full_name() if stage.approver else "",
        "status": stage.status,
        "decided_at": _iso(stage.decided_at),
        "comment": stage.comment,
    }


class CancellationEligibilityView(APIView):
    """GET /api/applications/{id}/cancellation-eligibility/ (owner only)."""
=======
"""Employee cancellation views (Unit 18, spec 3.4/3.5).

- ``GET  /api/v1/leave-applications/{id}/cancellation-eligibility/``
- ``POST /api/v1/leave-applications/{id}/cancel/``
- ``GET  /api/v1/leave-applications/{id}/cancellations/``

All three enforce employee ownership with 404 (never 403), matching the
tracking endpoint's discipline.
"""

from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from ..models import LeaveApplication
from .payloads import eligibility_payload, request_summary
from .services import (
    ActionChangedError,
    ApplicationNotFoundError,
    ConfirmationRequiredError,
    get_eligibility,
    LeaveAlreadyStartedError,
    NoCancellationApproversError,
    NotCancellableError,
    OpenRequestExistsError,
    ReasonTooLongError,
    ReasonTooShortError,
    submit_cancellation,
)

WITHDRAWAL = "withdrawal"


class CancelApplicationInputSerializer(serializers.Serializer):
    """The ``cancel/`` request body (spec 3.5)."""

    reason = serializers.CharField()
    confirm = serializers.BooleanField()
    expected_action = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, default=None
    )


class _OwnedApplicationMixin:
    def _owned_application(self, user, pk):
        return LeaveApplication.objects.filter(id=pk, employee=user).first()


class CancellationEligibilityView(APIView, _OwnedApplicationMixin):
    """Read-only cancellation eligibility for one owned application."""
>>>>>>> feature/plans-teams

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
<<<<<<< HEAD
        application = LeaveApplication.objects.filter(
            id=pk, employee=request.user
        ).first()
        if application is None:
            return _application_not_found()
        return Response(get_eligibility(application, request.user))


class CancelApplicationView(APIView):
    """POST /api/applications/{id}/cancel/ (owner only)."""
=======
        application = self._owned_application(request.user, pk)
        if application is None:
            return Response(
                {"detail": "The application does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )
        eligibility = get_eligibility(application, request.user)
        return Response(
            eligibility_payload(application, eligibility),
            status=status.HTTP_200_OK,
        )


class CancelApplicationView(APIView, _OwnedApplicationMixin):
    """Submit a cancellation: withdraw a pending application or request one."""
>>>>>>> feature/plans-teams

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
<<<<<<< HEAD
        serializer = SubmitCancellationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        body = serializer.validated_data

        try:
            result = submit_cancellation(
                user=request.user,
                application_id=pk,
                reason=body["reason"],
                confirm=body["confirm"],
                expected_action=body["expected_action"],
            )
        except ApplicationNotFoundError:
            return _application_not_found()
        except ActionChangedError:
            return _error(
                "action_changed",
                "The application state has changed. Please refresh and try again.",
                status.HTTP_409_CONFLICT,
            )
        except ConfirmationRequiredError:
            return _error(
                "confirmation_required",
                "Confirmation is required.",
                status.HTTP_400_BAD_REQUEST,
            )
        except ReasonTooShortError:
            return _error(
                "reason_too_short",
                "The reason must be between 10 and 1000 characters.",
                status.HTTP_400_BAD_REQUEST,
            )
        except ReasonTooLongError:
            return _error(
                "reason_too_long",
                "The reason must be between 10 and 1000 characters.",
                status.HTTP_400_BAD_REQUEST,
            )
        except NoCancellationApproversError:
            return _error(
                "no_cancellation_approvers",
                "No Supervisor/HOD approval chain exists for this application.",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        except OpenRequestExistsError:
            return _error(
                "open_request_exists",
                "An open cancellation request already exists for this application.",
                status.HTTP_409_CONFLICT,
            )

        return Response(
            {
                "kind": result["kind"],
                "cancellation_request": {
                    "id": str(result["cancellation_request"].id),
                    "status": result["cancellation_request"].status,
                },
            },
            status=(
                status.HTTP_201_CREATED
                if result["kind"] == CancellationRequest.Kind.APPROVED_LEAVE
                else status.HTTP_200_OK
            ),
        )


class CancellationListView(APIView):
    """GET /api/applications/{id}/cancellations/ (owner only).

    Newest first, with stages and notification state (section 3.8).
    """
=======
        serializer = CancelApplicationInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            cancellation = submit_cancellation(
                user=request.user,
                application_id=pk,
                reason=data["reason"],
                confirm=data["confirm"],
                expected_action=data.get("expected_action"),
            )
        except ApplicationNotFoundError:
            return Response(
                {"detail": "The application does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except ConfirmationRequiredError:
            return Response(
                {
                    "code": "confirmation_required",
                    "detail": "Confirm the cancellation before submitting it.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ReasonTooShortError:
            return Response(
                {
                    "code": "reason_too_short",
                    "detail": "The reason must be at least 10 characters.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ReasonTooLongError:
            return Response(
                {
                    "code": "reason_too_long",
                    "detail": "The reason must be at most 1000 characters.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ActionChangedError as exc:
            application = self._owned_application(request.user, pk)
            return Response(
                {
                    "code": "action_changed",
                    "detail": "The application changed since you checked. Review the latest state.",
                    "eligibility": eligibility_payload(application, exc.eligibility),
                },
                status=status.HTTP_409_CONFLICT,
            )
        except NotCancellableError as exc:
            return Response(
                {
                    "code": exc.reason or "not_cancellable_status",
                    "detail": "This application cannot be cancelled right now.",
                },
                status=status.HTTP_409_CONFLICT,
            )
        except LeaveAlreadyStartedError:
            return Response(
                {
                    "code": "leave_already_started",
                    "detail": "The leave has already started and cannot be cancelled.",
                },
                status=status.HTTP_409_CONFLICT,
            )
        except OpenRequestExistsError:
            return Response(
                {
                    "code": "open_request_exists",
                    "detail": "A cancellation request is still awaiting approval.",
                },
                status=status.HTTP_409_CONFLICT,
            )
        except NoCancellationApproversError:
            return Response(
                {
                    "code": "no_cancellation_approvers",
                    "detail": "No Supervisor or HOD is available to approve the cancellation.",
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        response_status = (
            status.HTTP_200_OK
            if cancellation.kind == WITHDRAWAL
            else status.HTTP_201_CREATED
        )
        return Response(
            {
                "kind": cancellation.kind,
                "request": request_summary(cancellation),
            },
            status=response_status,
        )


class CancellationHistoryView(APIView, _OwnedApplicationMixin):
    """All cancellation requests for one owned application, newest first."""
>>>>>>> feature/plans-teams

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
<<<<<<< HEAD
        application = LeaveApplication.objects.filter(
            id=pk, employee=request.user
        ).first()
        if application is None:
            return _application_not_found()

        requests = (
            application.cancellation_requests.select_related("application")
            .select_related("requested_by")
            .prefetch_related("stages__approver")
            .order_by("-requested_at")
        )
        return Response([_cancellation_list_item(req) for req in requests])


class CancellationApprovalsListView(APIView):
    """GET /api/approvals/cancellations/?tab=pending|decided (approver)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        tab = request.query_params.get("tab", "pending")
        user = request.user

        if tab == "pending":
            queryset = (
                CancellationRequest.objects.filter(
                    status=CancellationRequest.Status.PENDING,
                    stages__status=CancellationApprovalStage.Status.PENDING,
                    stages__approver=user,
                )
                .distinct()
                .order_by("requested_at")
            )
            decided = False
        elif tab == "decided":
            queryset = (
                CancellationRequest.objects.filter(
                    stages__approver=user,
                    stages__status__in=[
                        CancellationApprovalStage.Status.APPROVED,
                        CancellationApprovalStage.Status.REJECTED,
                    ],
                )
                .distinct()
                .order_by("-requested_at")
            )
            decided = True
        else:
            return Response({"detail": "Unknown tab."}, status=400)

        queryset = queryset.select_related(
            "application", "requested_by"
        ).prefetch_related("stages__approver")

        paginator = PageNumberPagination()
        paginator.page_size = CONFIGURED_PAGE_SIZE
        paginator.page_size_query_param = "page_size"
        paginator.max_page_size = MAX_PAGE_SIZE
        page = paginator.paginate_queryset(queryset, request)

        rows = [
            _approvals_list_item(req, user, include_my_decision=decided)
            for req in page
        ]
        return paginator.get_paginated_response(rows)


class CancellationDetailView(APIView):
    """GET /api/approvals/cancellations/{request_id}/ (assigned, or owner)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, request_id):
        request_row = CancellationRequest.objects.select_related(
            "application__employee", "requested_by"
        ).prefetch_related("stages__approver").filter(id=request_id).first()
        if request_row is None:
            return _not_found("Cancellation request not found.")

        application = request_row.application
        user = request.user
        is_assigned = any(
            stage.approver_id == user.id for stage in request_row.stages.all()
        )
        is_employee = application.employee_id == user.id
        if not is_assigned and not is_employee:
            return Response(
                {"detail": "Not authorized."},
                status=status.HTTP_403_FORBIDDEN,
            )

        balance_impact = _balance_impact(request_row, application)
        return Response(
            {
                "id": str(request_row.id),
                "kind": request_row.kind,
                "status": request_row.status,
                "reason": request_row.reason,
                "requested_at": _iso(request_row.requested_at),
                "decided_at": _iso(request_row.decided_at),
                "stage_version": request_row.stage_version,
                "balance_restored_days": str(request_row.balance_restored_days),
                "restored_financial_year": request_row.restored_financial_year,
                "employee_notification_state": request_row.employee_notification_state,
                "application_status_at_request": request_row.application_status_at_request,
                "leave_started": _leave_started(application),
                "can_act": _can_act(request_row, user),
                "my_decision": _detail_my_decision(request_row, user),
                "application": {
                    "id": str(application.id),
                    "reference_number": application.reference_number,
                    "leave_type": _leave_type_name(application),
                    "start_date": (
                        application.start_date.isoformat()
                        if application.start_date
                        else None
                    ),
                    "end_date": (
                        application.end_date.isoformat()
                        if application.end_date
                        else None
                    ),
                    "working_days": application.working_days,
                    "status": application.status,
                },
                "balance_impact": balance_impact,
                "stages": [
                    _stage_payload(stage) for stage in request_row.stages.all()
                ],
            }
        )


class CancellationDecisionView(APIView):
    """POST /api/approvals/cancellations/{request_id}/decision/."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, request_id):
        serializer = CancellationDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        body = serializer.validated_data

        try:
            result = decide_cancellation(
                user=request.user,
                request_id=request_id,
                decision=body["decision"],
                comment=body.get("comment", ""),
                stage_version=body["stage_version"],
            )
        except RequestNotPendingError:
            return _error(
                "request_not_pending",
                "This request is no longer pending.",
                status.HTTP_409_CONFLICT,
            )
        except StaleStageVersionError:
            return _error(
                "stale_stage_version",
                "This request has changed since you opened it. Please refresh.",
                status.HTTP_409_CONFLICT,
            )
        except NotCurrentApproverError:
            return _error(
                "not_current_approver",
                "You are not the assigned approver for the current stage.",
                status.HTTP_403_FORBIDDEN,
            )
        except LeaveAlreadyStartedError:
            return _error(
                "leave_already_started",
                "The leave has already started and can no longer be cancelled.",
                status.HTTP_409_CONFLICT,
            )
        except CommentRequiredError:
            return _error(
                "comment_required",
                "A comment is required for rejections.",
                status.HTTP_400_BAD_REQUEST,
            )

        return Response(result)


def _cancellation_list_item(request_row) -> dict:
    latest_pending = next(
        (
            stage
            for stage in request_row.stages.all()
            if stage.status == CancellationApprovalStage.Status.PENDING
        ),
        None,
    )
    return {
        "id": str(request_row.id),
        "kind": request_row.kind,
        "status": request_row.status,
        "reason": request_row.reason,
        "requested_at": _iso(request_row.requested_at),
        "decided_at": _iso(request_row.decided_at),
        "stage_version": request_row.stage_version,
        "balance_restored_days": str(request_row.balance_restored_days),
        "restored_financial_year": request_row.restored_financial_year,
        "employee_notification_state": request_row.employee_notification_state,
        "application_status_at_request": request_row.application_status_at_request,
        "leave_started": _leave_started(request_row.application),
        "stages": [
            _stage_payload(stage) for stage in request_row.stages.all()
        ],
        "current_stage_role": (
            latest_pending.role_label if latest_pending is not None else None
        ),
        "application": {
            "reference_number": request_row.application.reference_number,
            "start_date": (
                request_row.application.start_date.isoformat()
                if request_row.application.start_date
                else None
            ),
            "end_date": (
                request_row.application.end_date.isoformat()
                if request_row.application.end_date
                else None
            ),
            "working_days": request_row.application.working_days,
        },
    }


def _approvals_list_item(request_row, user, *, include_my_decision) -> dict:
    application = request_row.application
    item = {
        "id": str(request_row.id),
        "kind": request_row.kind,
        "status": request_row.status,
        "reason": request_row.reason,
        "requested_at": _iso(request_row.requested_at),
        "decided_at": _iso(request_row.decided_at),
        "application_id": str(application.id),
        "application_reference": application.reference_number,
        "employee_name": request_row.requested_by.get_full_name()
        or request_row.requested_by.username,
        "leave_type": _leave_type_name(application),
        "start_date": (
            application.start_date.isoformat() if application.start_date else None
        ),
        "end_date": (
            application.end_date.isoformat() if application.end_date else None
        ),
        "working_days": application.working_days,
        "leave_started": _leave_started(application),
        "current_stage_role": _current_stage_label(request_row, user),
        "stage_version": request_row.stage_version,
    }
    if include_my_decision:
        item["my_decision"] = _my_decision(request_row, user)
    return item


def _can_act(request_row, user) -> bool:
    """True when ``user`` is the approver of the current pending stage.

    Viewer-specific: the panel decides from this single server-derived flag,
    never by scanning the stage list itself.
    """
    if request_row.status != CancellationRequest.Status.PENDING:
        return False
    current_pending = next(
        (
            stage
            for stage in request_row.stages.all()
            if stage.status == CancellationApprovalStage.Status.PENDING
        ),
        None,
    )
    return current_pending is not None and current_pending.approver_id == user.id


def _detail_my_decision(request_row, user):
    """The viewer's own terminal decision for the detail payload.

    Like ``_my_decision`` (the list shape) but adds ``comment`` so the
    decision panel can show the reviewer's words.
    """
    mine = [
        stage
        for stage in request_row.stages.all()
        if stage.approver_id == user.id
        and stage.status in (
            CancellationApprovalStage.Status.APPROVED,
            CancellationApprovalStage.Status.REJECTED,
        )
    ]
    latest = max(mine, key=lambda stage: stage.order) if mine else None
    if latest is None:
        return None
    return {
        "action": latest.status,
        "role_label": latest.role_label,
        "decided_at": _iso(latest.decided_at),
        "comment": latest.comment,
    }


def _my_decision(request_row, user):
    mine = [
        stage
        for stage in request_row.stages.all()
        if stage.approver_id == user.id
        and stage.status in (
            CancellationApprovalStage.Status.APPROVED,
            CancellationApprovalStage.Status.REJECTED,
        )
    ]
    latest = max(mine, key=lambda stage: stage.order) if mine else None
    if latest is None:
        return None
    return {
        "action": latest.status,
        "role_label": latest.role_label,
        "decided_at": _iso(latest.decided_at),
    }


def _current_stage_label(request_row, user) -> str | None:
    stages = sorted(request_row.stages.all(), key=lambda stage: stage.order)
    for stage in stages:
        if stage.status == CancellationApprovalStage.Status.PENDING:
            return stage.role_label
    return None


def _balance_impact(request_row, application) -> dict:
    if request_row.status == CancellationRequest.Status.PENDING:
        deduction = get_balance_provider().get_deduction(application)
        if deduction is not None:
            return {
                "restores_days": str(deduction.days),
                "financial_year": deduction.financial_year,
            }
        return {"restores_days": "0", "financial_year": None}
    return {
        "restores_days": str(request_row.balance_restored_days),
        "financial_year": request_row.restored_financial_year,
    }


def _leave_started(application) -> bool:
    if application.start_date is None:
        return False
    return application.start_date <= get_today()


def _leave_type_name(application) -> str:
    snapshot = application.rules_snapshot or {}
    leave_type = snapshot.get("leave_type") or {}
    name = leave_type.get("name")
    if name:
        return name
    from leave.models import LeaveType

    row = LeaveType.objects.filter(pk=application.leave_type_id).first()
    return row.name if row is not None else "Leave"


def _application_not_found() -> Response:
    return _not_found("Application not found.")


def _not_found(detail: str) -> Response:
    return Response({"detail": detail}, status=status.HTTP_404_NOT_FOUND)


def _error(code: str, detail: str, http_status: int) -> Response:
    return Response(
        {"code": code, "detail": detail},
        status=http_status,
    )
=======
        application = self._owned_application(request.user, pk)
        if application is None:
            return Response(
                {"detail": "The application does not exist."},
                status=status.HTTP_404_NOT_FOUND,
            )
        requests = (
            application.cancellation_requests.select_related(
                "application", "application__employee"
            )
            .prefetch_related("stages__approver")
            .order_by("-requested_at")
        )
        return Response(
            {"count": requests.count(), "results": [request_summary(r) for r in requests]},
            status=status.HTTP_200_OK,
        )
>>>>>>> feature/plans-teams
