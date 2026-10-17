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

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
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

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
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

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
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