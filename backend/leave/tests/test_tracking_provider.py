"""Tracking provider tests (Unit 15).

- the configured ``LEAVE_TRACKING_PROVIDER`` setting is resolved through
  ``get_tracking_provider`` and honored by the endpoint (override_settings).
- the fixture provider parses ISO timestamps and builds contracts containing no
  Django ORM objects (so the serializer can render them directly).
"""

from datetime import datetime, timezone

from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from leave.models import LeaveApplication
from leave.tracking.contracts import (
    ResubmissionInfo,
    TrackedEvent,
    TrackedStage,
    WorkflowTracking,
)
from leave.tracking.fixture_provider import FixtureTrackingProvider
from leave.tracking.provider import TrackingProvider, get_tracking_provider

from .stubs import make_user


class InlineTrackingProvider(TrackingProvider):
    """Minimal provider whose payload is easy to assert on."""

    def get_workflow_tracking(self, application) -> WorkflowTracking:
        return WorkflowTracking(
            status="approved",
            approved_at=datetime(2026, 10, 18, 6, 20, 15, tzinfo=timezone.utc),
            current_stage=None,
            stages=(
                TrackedStage(
                    order=1,
                    role="reviewer",
                    role_label="Reviewer",
                    state="approved",
                    approver=None,
                    assigned_at=None,
                    decided_at=None,
                    comment=None,
                ),
            ),
            events=(
                TrackedEvent(
                    id="evt-1",
                    type="submitted",
                    occurred_at=datetime(
                        2026, 10, 12, 7, 15, 3, tzinfo=timezone.utc
                    ),
                    stage_order=None,
                    actor={"name": "Test Employee", "role_label": "Employee"},
                    comment=None,
                    resubmission_number=None,
                ),
            ),
            resubmission=ResubmissionInfo(
                count=0, last_resubmitted_at=None, can_resubmit=False
            ),
        )


class TrackingProviderSettingsTests(TestCase):
    def test_get_tracking_provider_resolves_configured_setting(self):
        self.assertIsInstance(get_tracking_provider(), FixtureTrackingProvider)

    def test_provider_swap_via_setting_is_honored(self):
        dummy_path = (
            f"{InlineTrackingProvider.__module__}.{InlineTrackingProvider.__name__}"
        )
        with override_settings(LEAVE_TRACKING_PROVIDER=dummy_path):
            client = APIClient()
            user = make_user()
            client.force_authenticate(user=user)
            app = LeaveApplication.objects.create(
                employee=user,
                leave_type_id=1,
                start_date="2026-11-02",
                end_date="2026-11-06",
                working_days=5,
                calendar_days=5,
                financial_year_label="2026-27",
                status=LeaveApplication.Status.SUBMITTED,
                reference_number="LV-2026-27-999999",
                submitted_at="2026-10-12T07:15:03Z",
                rules_snapshot={"leave_type": {"id": 1, "name": "Annual Leave"}},
            )
            response = client.get(
                f"/api/v1/leave-applications/{app.id}/tracking/"
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data["status"], "approved")
            self.assertEqual(
                response.data["approved_at"], "2026-10-18T06:20:15Z"
            )
            self.assertEqual(len(response.data["stages"]), 1)


class FixtureTrackingProviderTests(TestCase):
    def test_parses_absolute_utc_timestamps_into_aware_datetimes(self):
        provider = FixtureTrackingProvider()
        tracking = provider.get_workflow_tracking(
            type("App", (), {"reference_number": None})()
        )
        self.assertEqual(tracking.status, "pending")
        first_event = tracking.events[0]
        self.assertEqual(
            first_event.occurred_at,
            datetime(2026, 10, 12, 7, 15, 3, tzinfo=timezone.utc),
        )