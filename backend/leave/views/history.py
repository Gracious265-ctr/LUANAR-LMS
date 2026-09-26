"""Unit 24 — per-application and "my" history endpoints.

Both endpoints read the append-only :class:`audit.models.AuditEvent` trail via
``audit.services.application_timeline`` and render it for the caller. Access
fails closed with 404 (never 403) per project convention: the owner, any
approver who reached the application (Unit 16 ``get_view_access``), and HR may
see an application's timeline; drafts are owner-only.
"""

from django.http import Http404
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.services import application_timeline
from leave.models import LeaveApplication
from users.models import User
from workflows.policies import get_view_access


def _application_summary(application) -> dict:
    latest_revision = application.revisions.order_by("-revision_number").first()
    return {
        "id": str(application.pk),
        "reference_number": application.reference_number,
        "status": application.status,
        "leave_type_name": (
            latest_revision.leave_type_name if latest_revision else ""
        ),
        "start_date": application.start_date.isoformat() if application.start_date else None,
        "end_date": application.end_date.isoformat() if application.end_date else None,
        "working_days": application.working_days,
    }


class ApplicationHistoryView(APIView):
    """Complete chronological trail for one application (owner/approver/HR)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        application = (
            LeaveApplication.objects.select_related("employee", "current_stage")
            .filter(pk=pk)
            .first()
        )
        if application is None:
            raise Http404("Not found.")

        user = request.user
        is_owner = application.employee_id == user.id
        is_hr = getattr(user, "role", None) == User.Role.HR
        reached = get_view_access(user, application) is not None
        if not (is_owner or is_hr or reached):
            raise Http404("Not found.")
        if application.status == LeaveApplication.Status.DRAFT and not is_owner:
            raise Http404("Not found.")

        entries = application_timeline(application)
        return Response(
            {
                "application": {
                    **_application_summary(application),
                    "employee_name": (
                        application.employee.get_full_name()
                        or application.employee.username
                    ),
                },
                "entries": entries,
            }
        )


class MyLeaveHistoryView(APIView):
    """All of the signed-in employee's applications with their timelines.

    Applications with no recorded activity are omitted, so a bare draft never
    crowds the dashboard's recent-activity feed.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        applications = LeaveApplication.objects.filter(
            employee=request.user
        ).order_by("-updated_at")

        data = []
        for application in applications:
            entries = application_timeline(application)
            if not entries:
                continue
            data.append(
                {
                    "application": _application_summary(application),
                    "entries": entries,
                }
            )
        return Response(data)