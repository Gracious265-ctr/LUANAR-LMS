"""Employee-facing leave views for the Unit 20 data integration."""

from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from ..providers import get_provider
from ..services import active_financial_year, financial_year_label, resolved_annual_entitlement


class LeaveSummaryView(APIView):
    """Authenticated summary of the employee's HR-configured record.

    ``GET /api/v1/leave/me/summary/`` returns the employee's profile, resolved
    annual entitlement, active financial year and available balance — all read
    from the real HR-track tables through the rules provider, so the dashboard
    reflects exactly what HR manages. Fields degrade to ``None`` (or ``"0"``
    for the balance) when records or configuration are missing.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        provider = get_provider()

        profile = getattr(user, "employee_profile", None)
        entitlement = None
        if profile is not None:
            entitlement = resolved_annual_entitlement(profile.grade)

        year = active_financial_year()
        year_payload = None
        if year is not None:
            year_payload = {
                "label": financial_year_label(year),
                "start": year.start_date,
                "end": year.end_date,
            }

        available_balance = None
        if profile is not None and year_payload is not None:
            available_balance = provider.get_available_balance(
                user.id, year_payload["label"]
            )

        return Response(
            {
                "profile": (
                    {
                        "grade": profile.grade,
                        "category": profile.category,
                        # The name, not the row: this is rendered as JSON.
                        "team": (
                            profile.team.name if profile.team_id else None
                        ),
                        "faculty": profile.faculty,
                        "gender": profile.gender,
                        "appointment_date": profile.appointment_date,
                    }
                    if profile is not None
                    else None
                ),
                "entitlement": (
                    {
                        "days": entitlement.days,
                        "effective_from": entitlement.effective_from,
                    }
                    if entitlement is not None
                    else None
                ),
                "financial_year": year_payload,
                "available_balance": (
                    str(available_balance) if available_balance is not None else None
                ),
            }
        )