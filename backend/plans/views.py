"""Plan API views (Unit 25, D16–D19).

Employee:  create / list-mine / detail / submit / confirm / release /
           pending-confirmations.
Approvers: capabilities + approval queue / review / decision (mirrors the
           Unit 16 approvals API, plan-scoped). "Approver" is decided by
           :func:`workflows.services.is_approver_user` — holding an active
           approver role — and never by ``User.role``.
HR:        admin list across the organisation + PlanSettings.
"""

from __future__ import annotations

from uuid import UUID

from django.db.models import Q
from leave.providers import get_today
from rest_framework import permissions, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    LeaveDayPlan,
    LeavePlanBlock,
    PlanSettings,
    get_plan_settings,
)
from .payloads import (
    approver_detail_payload,
    approver_list_row,
    block_payload,
    plan_detail_payload,
    plan_row,
)
from .policies import (
    campus_member_ids,
    plan_view_access,
    team_member_ids,
    user_is_approver,
    user_is_hr,
)
from .serializers import (
    PlanCreateSerializer,
    PlanDecisionInputSerializer,
    PlanSettingsSerializer,
)
from .services import (
    BlockStateError,
    PlanBlockInputError,
    PlanDecisionNotAllowedError,
    PlanDecisionValidationError,
    PlanNotFoundError,
    PlanNotSubmittableError,
    PlanStageChangedError,
    PlanValidationFailedError,
    acting_approver_predicate,
    confirm_block,
    create_plan,
    decide_plan,
    release_block,
    submit_plan,
)


class _ApproverOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        return user_is_approver(request.user)


class _HROnly(permissions.BasePermission):
    def has_permission(self, request, view):
        return user_is_hr(request.user)


class _Paginator(PageNumberPagination):
    page_size = 20
    max_page_size = 100


def _pk(value):
    try:
        return UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


class PlanCapabilitiesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        is_approver = user_is_approver(user) or user_is_hr(user)
        approver_pending = (
            LeaveDayPlan.objects.filter(
                status=LeaveDayPlan.Status.SUBMITTED,
            )
            .filter(acting_approver_predicate(user))
            .count()
            if is_approver
            else 0
        )
        pending_confirmations = (
            LeavePlanBlock.objects.filter(
                plan__employee=user,
                plan__status=LeaveDayPlan.Status.APPROVED,
                status=LeavePlanBlock.Status.RESERVED,
                start_date__gt=get_today(),
            ).count()
            if user.pk
            else 0
        )
        return Response(
            {
                "is_approver": is_approver,
                "approver_pending_count": approver_pending,
                "pending_confirmation_count": pending_confirmations,
            }
        )


class PlanListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        scope = (request.query_params.get("scope") or "mine").lower()
        if scope not in ("mine", "team", "campus", "all"):
            scope = "mine"

        base = LeaveDayPlan.objects.select_related(
            "employee__employee_profile", "employee__employee_profile__team"
        )

        if scope == "mine":
            qs = base.filter(employee=user)
        elif scope == "team":
            peers = team_member_ids(user)
            if not peers:
                return Response(
                    {
                        "error": (
                            "You are not in a team yet, so there is no team view. "
                            "Ask HR to assign you to a team."
                        )
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            qs = base.filter(
                employee_id__in=peers,
                status=LeaveDayPlan.Status.APPROVED,
            )
        elif scope == "campus":
            colleagues = campus_member_ids(user)
            if not colleagues:
                return Response(
                    {
                        "error": (
                            "Your team has no campus, so there is no "
                            "campus view."
                        )
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            qs = base.filter(
                employee_id__in=colleagues,
                status=LeaveDayPlan.Status.APPROVED,
            )
        else:  # "all"
            if not user_is_hr(user):
                return Response(
                    {"error": "Only HR can view all plans."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            qs = base.all()

        qs = qs.prefetch_related("plan_blocks").order_by("-created_at")
        rows = [plan_row(plan, user, scope=scope) for plan in qs]
        return Response({"scope": scope, "count": len(rows), "results": rows})

    def post(self, request):
        serializer = PlanCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            plan = create_plan(
                user=request.user,
                period_start=data["period_start"],
                period_end=data["period_end"],
                blocks=[dict(b) for b in data["blocks"]],
            )
        except (ValueError, PlanBlockInputError) as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(
            plan_detail_payload(plan, request.user, None),
            status=status.HTTP_201_CREATED,
        )


class PlanDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        user = request.user
        plan = (
            LeaveDayPlan.objects.select_related("employee__employee_profile")
            .prefetch_related("plan_blocks",
            "approval_stages__assigned_approver",
            "approval_stages__eligible_approvers__user",
            "approval_decisions__stage",)
            .filter(pk=_pk(pk))
            .first()
        )
        if plan is None:
            return Response(
                {"error": "Plan not found."}, status=status.HTTP_404_NOT_FOUND
            )
        access = plan_view_access(user, plan)
        if access is None:
            return Response(
                {"error": "You cannot view this plan."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(plan_detail_payload(plan, user, access))


class PlanSubmitAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        plan_id = _pk(pk)
        if plan_id is None:
            return Response(
                {"error": "Plan not found."}, status=status.HTTP_404_NOT_FOUND
            )
        try:
            plan = submit_plan(user=request.user, plan_id=plan_id)
        except PlanNotFoundError:
            return Response(
                {"error": "Plan not found."}, status=status.HTTP_404_NOT_FOUND
            )
        except PlanNotSubmittableError:
            return Response(
                {"error": "Only a draft plan can be submitted."},
                status=status.HTTP_409_CONFLICT,
            )
        except PlanValidationFailedError as exc:
            return Response(
                {
                    "errors": [
                        {
                            "field": e.field,
                            "code": e.code,
                            "message": e.message,
                            "block": e.block,
                        }
                        for e in exc.errors
                    ],
                    "warnings": exc.warnings,
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        plan = (
            LeaveDayPlan.objects.select_related("employee__employee_profile")
            .prefetch_related("plan_blocks",
            "approval_stages__assigned_approver",
            "approval_stages__eligible_approvers__user",
            "approval_decisions__stage",)
            .filter(pk=plan.pk)
            .first()
        )
        return Response(plan_detail_payload(plan, request.user, None))


class PlanBlockConfirmAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk, block_id):
        try:
            block = confirm_block(_pk(pk), _pk(block_id), request.user)
        except PlanNotFoundError:
            return Response(
                {"error": "Plan or block not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except BlockStateError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_409_CONFLICT
            )
        return Response({"status": block.status, "id": str(block.id)})


class PlanBlockReleaseAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk, block_id):
        user = request.user
        plan_id = _pk(pk)
        if not user_is_hr(user):
            plan = LeaveDayPlan.objects.filter(id=plan_id, employee=user).first()
            if plan is None:
                return Response(
                    {"error": "Plan not found."}, status=status.HTTP_404_NOT_FOUND
                )
        try:
            block = release_block(plan_id, _pk(block_id), user)
        except PlanNotFoundError:
            return Response(
                {"error": "Plan or block not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except BlockStateError as exc:
            return Response(
                {"error": str(exc)}, status=status.HTTP_409_CONFLICT
            )
        return Response({"status": block.status, "id": str(block.id)})


class PlanPendingConfirmationsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        today = get_today()
        blocks = (
            LeavePlanBlock.objects.filter(
                plan__employee=request.user,
                plan__status=LeaveDayPlan.Status.APPROVED,
                status=LeavePlanBlock.Status.RESERVED,
                start_date__gt=today,
            )
            .select_related("plan")
            .order_by("start_date")
        )

        return Response(
            {
                "count": blocks.count(),
                "results": [
                    {
                        "plan_id": str(b.plan_id),
                        "plan_period_start": b.plan.period_start.isoformat(),
                        "plan_period_end": b.plan.period_end.isoformat(),
                        **block_payload(b, for_owner=True),
                    }
                    for b in blocks
                ],
            }
        )


class PlanApprovalListAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, _ApproverOnly]

    def get(self, request):
        user = request.user
        tab = request.query_params.get("tab", "pending")
        tab = tab if tab in ("pending", "decided") else "pending"
        qs = LeaveDayPlan.objects.select_related(
            "employee__employee_profile", "current_stage"
        ).prefetch_related("plan_blocks")
        if tab == "pending":
            qs = qs.filter(status=LeaveDayPlan.Status.SUBMITTED).filter(
                acting_approver_predicate(user)
            )
        else:
            qs = (
                qs.filter(approval_decisions__approver=user)
                .exclude(
                    Q(status=LeaveDayPlan.Status.SUBMITTED)
                    & acting_approver_predicate(user),
                )
                .distinct()
            )
        qs = qs.order_by("submitted_at" if tab == "pending" else "-created_at")

        paginator = _Paginator()
        page = paginator.paginate_queryset(qs, request, view=self)
        if page is not None:
            rows = [approver_list_row(plan, user) for plan in page]
            return Response(
                {
                    "tab": tab,
                    "count": paginator.page.paginator.count,
                    "next": paginator.get_next_link(),
                    "previous": paginator.get_previous_link(),
                    "results": rows,
                }
            )
        rows = [approver_list_row(plan, user) for plan in qs]
        return Response({"tab": tab, "count": len(rows), "results": rows})


class PlanApprovalDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, _ApproverOnly]

    def get(self, request, pk):
        plan = _find_approvable(request.user, pk)
        if plan is None:
            return Response(
                {"error": "You cannot review this plan."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(approver_detail_payload(plan, request.user))


class PlanApprovalDecisionAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, _ApproverOnly]

    def post(self, request, pk):
        serializer = PlanDecisionInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            plan = decide_plan(
                plan_id=_pk(pk),
                actor=request.user,
                action=data["action"],
                comment=data.get("comment") or "",
                expected_version=data["stage_version"],
            )
        except PlanNotFoundError:
            return Response(
                {"error": "Plan not found."}, status=status.HTTP_404_NOT_FOUND
            )
        except PlanStageChangedError:
            return Response(
                {
                    "error": "This plan has already been decided. Refresh to see the latest state.",
                    "reason": "stage_changed",
                },
                status=status.HTTP_409_CONFLICT,
            )
        except PlanDecisionNotAllowedError as exc:
            return Response(
                {
                    "error": {
                        "not_current_stage": "This plan is not with you right now.",
                        "already_decided": "You have already made a decision on this plan.",
                        "plan_closed": "This plan is closed or not awaiting your decision.",
                    }.get(exc.reason, "You cannot decide on this plan."),
                    "reason": exc.reason,
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        except PlanDecisionValidationError as exc:
            return Response(
                {"errors": exc.errors}, status=status.HTTP_400_BAD_REQUEST
            )
        plan = (
            LeaveDayPlan.objects.select_related("employee__employee_profile")
            .prefetch_related(
                "plan_blocks",
                "approval_stages__assigned_approver",
                "approval_stages__eligible_approvers__user",
                "approval_decisions__stage",
            )
            .filter(pk=plan.pk)
            .first()
        )
        return Response(plan_detail_payload(plan, request.user, None))


def _find_approvable(user, pk):
    pk = _pk(pk)
    if pk is None:
        return None
    plan = (
        LeaveDayPlan.objects.filter(pk=pk)
        .select_related(
            "employee__employee_profile",
            "current_stage__assigned_approver",
        )
        .first()
    )
    if plan is None:
        return None
    if plan_view_access(user, plan) is None:
        return None
    return plan


class PlanAdminListAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, _HROnly]

    def get(self, request):
        qs = LeaveDayPlan.objects.select_related(
            "employee__employee_profile", "current_stage"
        ).prefetch_related("plan_blocks")
        plan_status = (request.query_params.get("status") or "").strip()
        if plan_status:
            qs = qs.filter(status=plan_status)
        block_status = (request.query_params.get("block_status") or "").strip()
        if block_status:
            # Filtering across this reverse FK joins plan_blocks, so a plan
            # holding several blocks in the same status would otherwise repeat
            # once per block — duplicating table rows and inflating `count`.
            qs = qs.filter(plan_blocks__status=block_status).distinct()
        qs = qs.order_by("-created_at")

        paginator = _Paginator()
        page = paginator.paginate_queryset(qs, request, view=self)
        rows = [plan_row(plan, request.user, scope="hr") for plan in (page or qs)]
        return Response(
            {
                "count": paginator.page.paginator.count if page is not None else len(rows),
                "next": paginator.get_next_link() if page is not None else None,
                "previous": paginator.get_previous_link() if page is not None else None,
                "results": rows,
            }
        )


class PlanSettingsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated, _HROnly]

    def get(self, request):
        settings = get_plan_settings()
        return Response(
            {"confirmation_lead_days": settings.confirmation_lead_days}
        )

    def patch(self, request):
        settings = get_plan_settings()
        serializer = PlanSettingsSerializer(settings, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"confirmation_lead_days": settings.confirmation_lead_days}
        )