"""Tests for the ``seed_tracking_scenarios`` command (Unit 15).

Covers the DEBUG guard, idempotency across runs, assignment-file consistency
and the reference-reservation behaviour (real applications keep using the
sequence from 900009 onward on the same financial-year label).
"""

import json
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings, tag

from leave.management.commands.seed_tracking_scenarios import (
    ASSIGNMENTS_PATH,
    SCENARIOS,
)
from leave.models import LeaveApplication, ReferenceSequence
from leave.services.references import next_reference

from .stubs import make_user


@tag("slow")
class SeedTrackingScenariosTests(TestCase):
    def setUp(self):
        self.employee = make_user()

    def _run(self):
        with override_settings(DEBUG=True):
            call_command("seed_tracking_scenarios")

    def test_refuses_without_debug(self):
        with self.assertRaises(CommandError):
            with override_settings(DEBUG=False):
                call_command("seed_tracking_scenarios")

    @mock.patch(
        "leave.management.commands.seed_tracking_scenarios.DEV_EMPLOYEE_USERNAME",
        "missing@test.luanar",
    )
    def test_complains_when_dev_employee_missing(self):
        with self.assertRaises(CommandError):
            self._run()

    def test_seeds_eight_submitted_applications(self):
        self._run()
        apps = list(
            LeaveApplication.objects.filter(employee=self.employee).order_by(
                "reference_number"
            )
        )
        self.assertEqual(len(apps), len(SCENARIOS))
        self.assertTrue(all(app.status == "submitted" for app in apps))
        self.assertEqual(
            [app.reference_number for app in apps],
            [f"LV-2026-27-{900001 + i:06d}" for i in range(len(SCENARIOS))],
        )

    def test_assignments_file_matches_applications(self):
        self._run()
        with ASSIGNMENTS_PATH.open(encoding="utf-8") as handle:
            assignments = json.load(handle)
        apps = LeaveApplication.objects.filter(employee=self.employee)
        refs = set(app.reference_number for app in apps)
        self.assertEqual(set(assignments.keys()), refs)
        self.assertEqual(
            list(assignments.values()),
            [scenario for scenario, *_ in SCENARIOS],
        )

    def test_runs_again_idempotently(self):
        self._run()
        before = LeaveApplication.objects.count()
        self._run()
        after = LeaveApplication.objects.count()
        self.assertEqual(before, after)

    def test_reserved_sequence_leaves_real_references_intact(self):
        self._run()
        # ReferenceSequence should sit at 900008 after the seed.
        seq = ReferenceSequence.objects.get(financial_year_label="2026-27")
        self.assertEqual(seq.last_value, 900008)
        reference = next_reference("2026-27")
        self.assertEqual(reference, "LV-2026-27-900009")