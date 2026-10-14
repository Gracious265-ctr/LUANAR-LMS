"""HR setup-hub endpoints: status, chain templates, apply-defaults, rollover.

HR-only throughout, and derived from the services in :mod:`leave.services.setup`
rather than re-implementing any rule here — the browser and the setup hub cannot
get a different answer from these than the action itself would give.
"""

from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import IsHRRole

from ..services.setup import apply_defaults, rollover_financial_year, setup_status


class SetupStatusView(APIView):
    """The setup spine's completion, derived from live data."""

    permission_classes = [permissions.IsAuthenticated, IsHRRole]

    def get(self, request):
        return Response(setup_status())


class SetupTemplatesView(APIView):
    """The approval-chain templates a team can be built from."""

    permission_classes = [permissions.IsAuthenticated, IsHRRole]

    def get(self, request):
        from workflows.presets import WORKFLOW_TEMPLATES

        return Response(
            {
                "templates": [
                    template.as_dict() for template in WORKFLOW_TEMPLATES.values()
                ]
            }
        )


class ApplyDefaultsView(APIView):
    """Apply the LUANAR defaults, or preview them with ``dry_run``.

    Idempotent and additive: re-running creates nothing and overwrites nothing,
    so the hub offers it as a plain button and a preview that writes nothing.
    """

    permission_classes = [permissions.IsAuthenticated, IsHRRole]

    def post(self, request):
        dry_run = bool(request.data.get("dry_run", False))
        result = apply_defaults(actor=request.user, dry_run=dry_run)
        return Response(result.as_dict(), status=status.HTTP_200_OK)


class RolloverView(APIView):
    """Open the next financial year, carrying the current policy forward."""

    permission_classes = [permissions.IsAuthenticated, IsHRRole]

    def post(self, request):
        result = rollover_financial_year(actor=request.user)
        return Response(result.as_dict(), status=status.HTTP_200_OK)
