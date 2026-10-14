"""The two dashboard counts on ``GET /api/v1/leave/me/summary/``.

Dates are built from :func:`leave.providers.get_today` — the exact seam the view
reads — rather than from a fixed fixture constant. `EARLIEST_ANNUAL_START` and
the stub's `TODAY` are both behind the wall clock now, and a fixed date in a
window test is a test that quietly starts failing the day it passes.
"""

from datetime import timedelta

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from leave.models import LeaveApplication
from leave.providers import get_today

from .stubs import make_user


class LeaveSummaryCountTests(TestCase):
    url = "/api/v1/leave/me/summary/"

    def setUp(self):
        self.client = APIClient()
        self.owner = make_user("summary-owner@luanar")
        self.other = make_user("summary-other@luanar")
        self.client.force_authenticate(user=self.owner)
        self.today = get_today()

    def application(self, status_, *, start=None, days=None, user=None):
        return LeaveApplication.objects.create(
            employee=user or self.owner,
            status=status_,
            start_date=start,
            end_date=start,
            calculated_days=days,
        )

    def get(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data

    def test_requires_authentication(self):
        client = APIClient()
        response = client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_pending_counts_submitted_and_correction_required(self):
        self.application(LeaveApplication.Status.SUBMITTED, start=self.today)
        self.application(
            LeaveApplication.Status.CORRECTION_REQUIRED, start=self.today
        )
        self.assertEqual(self.get()["pending_applications"], 2)

    def test_pending_excludes_every_other_status(self):
        for terminal in (
            LeaveApplication.Status.DRAFT,
            LeaveApplication.Status.APPROVED,
            LeaveApplication.Status.REJECTED,
            LeaveApplication.Status.CANCELLED,
        ):
            with self.subTest(status=terminal):
                self.application(terminal, start=self.today)
        self.assertEqual(self.get()["pending_applications"], 0)

    def test_pending_counts_nothing_but_the_owners(self):
        self.application(LeaveApplication.Status.SUBMITTED, user=self.other)
        self.assertEqual(self.get()["pending_applications"], 0)

    def test_upcoming_sums_approved_leave_starting_inside_the_window(self):
        self.application(
            LeaveApplication.Status.APPROVED,
            start=self.today + timedelta(days=3),
            days=4,
        )
        self.application(
            LeaveApplication.Status.APPROVED,
            start=self.today + timedelta(days=10),
            days=2,
        )
        payload = self.get()
        self.assertEqual(payload["upcoming_leave"]["days"], 6)
        self.assertEqual(payload["upcoming_leave"]["applications"], 2)

    def test_upcoming_window_is_inclusive_at_both_ends(self):
        self.application(
            LeaveApplication.Status.APPROVED, start=self.today, days=1
        )
        self.application(
            LeaveApplication.Status.APPROVED,
            start=self.today + timedelta(days=30),
            days=1,
        )
        self.application(
            LeaveApplication.Status.APPROVED,
            start=self.today + timedelta(days=31),
            days=5,
        )
        payload = self.get()
        # Day 31 falls outside, so its five days must not reach the total.
        self.assertEqual(payload["upcoming_leave"]["days"], 2)
        self.assertEqual(payload["upcoming_leave"]["applications"], 2)

    def test_upcoming_ignores_leave_that_has_already_started(self):
        self.application(
            LeaveApplication.Status.APPROVED,
            start=self.today - timedelta(days=1),
            days=3,
        )
        payload = self.get()
        self.assertEqual(payload["upcoming_leave"]["days"], 0)
        self.assertEqual(payload["upcoming_leave"]["applications"], 0)

    def test_upcoming_ignores_unapproved_leave_in_the_window(self):
        for in_motion in (
            LeaveApplication.Status.SUBMITTED,
            LeaveApplication.Status.CORRECTION_REQUIRED,
            LeaveApplication.Status.REJECTED,
            LeaveApplication.Status.DRAFT,
            LeaveApplication.Status.CANCELLED,
        ):
            with self.subTest(status=in_motion):
                self.application(
                    in_motion,
                    start=self.today + timedelta(days=2),
                    days=7,
                )
        payload = self.get()
        self.assertEqual(payload["upcoming_leave"]["days"], 0)
        self.assertEqual(payload["upcoming_leave"]["applications"], 0)

    def test_upcoming_ignores_another_users_leave(self):
        self.application(
            LeaveApplication.Status.APPROVED,
            start=self.today + timedelta(days=2),
            days=9,
            user=self.other,
        )
        payload = self.get()
        self.assertEqual(payload["upcoming_leave"]["days"], 0)
        self.assertEqual(payload["upcoming_leave"]["applications"], 0)

    def test_upcoming_reports_zeroes_when_nothing_is_scheduled(self):
        payload = self.get()
        self.assertEqual(
            payload["upcoming_leave"], {"days": 0, "applications": 0}
        )
        self.assertEqual(payload["pending_applications"], 0)

    def test_unfinished_days_are_counted_as_an_application_but_not_as_days(self):
        """``calculated_days`` is nullable; a null must not null the sum."""
        self.application(
            LeaveApplication.Status.APPROVED,
            start=self.today + timedelta(days=2),
            days=None,
        )
        payload = self.get()
        self.assertEqual(payload["upcoming_leave"]["applications"], 1)
        self.assertEqual(payload["upcoming_leave"]["days"], 0)

    def test_the_existing_summary_fields_are_still_present(self):
        """Additive: the dashboard reads four fields it already relied on."""
        payload = self.get()
        for key in (
            "profile",
            "entitlement",
            "financial_year",
            "available_balance",
            "pending_applications",
            "upcoming_leave",
        ):
            with self.subTest(key=key):
                self.assertIn(key, payload)

    def test_counts_are_per_authenticated_user(self):
        """Two people with the same shapes read their own numbers, not each other's."""
        self.application(
            LeaveApplication.Status.SUBMITTED, start=self.today, user=self.other
        )
        self.application(
            LeaveApplication.Status.APPROVED,
            start=self.today + timedelta(days=1),
            days=5,
            user=self.other,
        )
        self.application(
            LeaveApplication.Status.SUBMITTED, start=self.today, user=self.owner
        )

        owner_payload = self.get()

        self.client.force_authenticate(user=self.other)
        other_payload = self.get()

        self.assertEqual(owner_payload["pending_applications"], 1)
        self.assertEqual(owner_payload["upcoming_leave"]["days"], 0)
        self.assertEqual(other_payload["pending_applications"], 1)
        self.assertEqual(other_payload["upcoming_leave"]["days"], 5)
