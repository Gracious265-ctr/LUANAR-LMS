"""Scenario-invariant tests for the Unit 15 tracking endpoint.

Each checked-in scenario fixture (one per ``assignments.json`` entry, plus the
fallback for unknown references) must satisfy the Section 1 contract:

- ``stages`` ascend by ``order``; only one stage is ``awaiting`` and everything
  before it is ``approved``; stages after a stopped workflow are ``upcoming``.
- exactly one ``rejected`` stage when ``status == rejected`` and one ``returned``
  stage when ``status == correction_required``.
- ``approved`` statuses set ``approved_at`` and approve every stage.
- ``events`` are newest first and the oldest is the original ``submitted``.
- ``can_resubmit`` is true exactly for the two resubmittable statuses and then
  carries ``returns_to_stage``; resubmitted applications reset outcomes to null.
- delegation is visible through the approver block / current stage.
"""

import json
from pathlib import Path

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from leave.models import ApplicationRevision, LeaveApplication, LeaveType

from .stubs import make_user

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "tracking" / "fixtures"
SCENARIOS_DIR = FIXTURES_DIR / "scenarios"

RESUBMITTABLE_STATUSES = {"rejected", "correction_required"}


def load_scenario(name: str) -> dict:
    with (SCENARIOS_DIR / f"{name}.json").open(encoding="utf-8") as handle:
        return json.load(handle)


def load_assignments() -> dict:
    """Read ``assignments.json`` into {reference -> scenario name}."""
    with (FIXTURES_DIR / "assignments.json").open(encoding="utf-8") as handle:
        return json.load(handle)


class TrackingScenarioTests(TestCase):
    url_template = "/api/v1/leave-applications/{id}/tracking/"

    def setUp(self):
        self.client = APIClient()
        self.user = make_user()
        self.client.force_authenticate(user=self.user)

    def create_for_reference(self, reference, status=None):
        assignments = load_assignments()
        name = assignments.get(reference, "pending_first_stage")
        scenario = load_scenario(name)
        if status is None:
            status = {
                "pending": LeaveApplication.Status.PENDING,
                "approved": LeaveApplication.Status.APPROVED,
                "rejected": LeaveApplication.Status.REJECTED,
                "correction_required": LeaveApplication.Status.CORRECTION_REQUIRED,
            }.get(scenario["status"], LeaveApplication.Status.SUBMITTED)
        app = LeaveApplication.objects.create(
            employee=self.user,
            leave_type_id=1,
            start_date="2026-11-02",
            end_date="2026-11-06",
            working_days=5,
            calendar_days=5,
            financial_year_label="2026-27",
            status=status,
            reference_number=reference,
            submitted_at="2026-10-12T07:15:03Z",
            rules_snapshot={"leave_type": {"id": 1, "name": "Annual Leave"}},
        )
        # A scenario with a ``resubmitted`` event describes an application that
        # actually went through a resubmission, which must exist as a real
        # immutable revision so ``resubmission.count`` stays consistent.
        if any(item.get("type") == "resubmitted" for item in scenario["events"]):
            leave_type, _ = LeaveType.objects.get_or_create(
                name="Annual Leave", code="annual"
            )
            ApplicationRevision.objects.create(
                application=app,
                revision_number=2,
                leave_type=leave_type,
                leave_type_name="Annual Leave",
                start_date=app.start_date,
                end_date=app.end_date,
                working_days=app.working_days,
                reason=app.reason,
            )
        return app

    def fetch(self, reference):
        app = self.create_for_reference(reference)
        response = self.client.get(self.url_template.format(id=app.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data

    def test_every_scenario_validates(self):
        for reference, name in load_assignments().items():
            data = self.fetch(reference)
            scenario = load_scenario(name)

            self.assertEqual(data["status"], scenario["status"], name)
            self._assert_stage_invariants(name, data)
            self._assert_event_invariants(name, data)
            self._assert_outcome_invariants(name, data)

    def test_unknown_reference_falls_back_to_pending_first_stage(self):
        data = self.fetch("LV-2026-27-123456")
        self.assertEqual(data["status"], "pending")
        self.assertEqual(data["stages"][0]["state"], "awaiting")
        self.assertEqual(data["stages"][0]["role_label"], "Supervisor")

    def _assert_stage_invariants(self, name, data):
        stages = data["stages"]
        orders = [stage["order"] for stage in stages]
        self.assertEqual(orders, sorted(orders), name)

        statuses = {stage["state"] for stage in stages}
        valid_states = {"approved", "awaiting", "upcoming", "rejected", "returned"}
        self.assertTrue(statuses.issubset(valid_states), name)

        awaiting = [s for s in stages if s["state"] == "awaiting"]
        rejected = [s for s in stages if s["state"] == "rejected"]
        returned = [s for s in stages if s["state"] == "returned"]

        if data["status"] == "approved":
            self.assertEqual(len(awaiting), 0, name)
            self.assertEqual(len(rejected), 0, name)
            self.assertEqual(len(returned), 0, name)
            self.assertTrue(all(s["state"] == "approved" for s in stages), name)
            self.assertIsNotNone(data["approved_at"], name)
        elif data["status"] == "rejected":
            self.assertEqual(len(rejected), 1, name)
            self.assertEqual(len(awaiting), 0, name)
            self.assertEqual(len(returned), 0, name)
        elif data["status"] == "correction_required":
            self.assertEqual(len(returned), 1, name)
            self.assertEqual(len(awaiting), 0, name)
            self.assertEqual(len(rejected), 0, name)
        else:  # pending
            self.assertEqual(len(awaiting), 1, name)
            self.assertEqual(len(rejected), 0, name)
            self.assertEqual(len(returned), 0, name)

        stopped = data["status"] in {"rejected", "correction_required"}
        if stopped:
            self.assertIsNone(data["current_stage"], name)

        for i, stage in enumerate(stages):
            if stage["state"] == "upcoming":
                self.assertTrue(
                    all(s["state"] == "upcoming" for s in stages[i:]),
                    f"{name}: upcoming must be trailing",
                )
                self.assertIsNone(stage["approver"], name)
            if stage["state"] in {"approved", "rejected", "returned"}:
                self.assertIsNotNone(stage["decided_at"], name)
                self.assertIsNotNone(stage["approver"], name)
            if stage["state"] == "awaiting":
                self.assertIsNone(stage["decided_at"], name)

        # stages before the awaiting/rejected/returned stage are all approved
        if not data["status"] == "approved":
            spine = next(
                (
                    j
                    for j, s in enumerate(stages)
                    if s["state"] in {"awaiting", "rejected", "returned"}
                ),
                None,
            )
            if spine is not None:
                self.assertTrue(
                    all(s["state"] == "approved" for s in stages[:spine]),
                    f"{name}: pre-spine stages must be approved",
                )

    def _assert_event_invariants(self, name, data):
        events = data["events"]
        self.assertGreaterEqual(len(events), 1, name)
        occurred = [event["occurred_at"] for event in events]
        self.assertEqual(occurred, sorted(occurred, reverse=True), name)
        self.assertEqual(events[-1]["type"], "submitted", name)

        types = {event["type"] for event in events}
        known = {
            "submitted",
            "approved",
            "rejected",
            "correction_requested",
            "resubmitted",
            "reassigned",
        }
        self.assertTrue(types.issubset(known), name)

        for event in events:
            if event["type"] == "resubmitted":
                self.assertIsNotNone(event["resubmission_number"], name)
                self.assertEqual(
                    event["resubmission_number"], data["resubmission"]["count"], name
                )

    def _assert_outcome_invariants(self, name, data):
        status_ = data["status"]
        rejection = data["rejection"]
        correction = data["correction"]
        resubmission = data["resubmission"]

        if status_ == "rejected":
            self.assertIsNotNone(rejection, name)
            self.assertIsNone(correction, name)
            self.assertTrue(resubmission["can_resubmit"], name)
            self.assertIsNotNone(resubmission["returns_to_stage"], name)
            self.assertEqual(
                resubmission["returns_to_stage"]["order"],
                rejection["stage_order"],
                name,
            )
        elif status_ == "correction_required":
            self.assertIsNotNone(correction, name)
            self.assertIsNone(rejection, name)
            self.assertTrue(resubmission["can_resubmit"], name)
            self.assertIsNotNone(resubmission["returns_to_stage"], name)
            self.assertEqual(
                resubmission["returns_to_stage"]["order"],
                correction["stage_order"],
                name,
            )
        else:
            self.assertIsNone(rejection, name)
            self.assertIsNone(correction, name)
            self.assertFalse(resubmission["can_resubmit"], name)
            self.assertIsNone(resubmission["returns_to_stage"], name)

        if resubmission["count"] > 0:
            self.assertIsNone(rejection, name)
            self.assertIsNone(correction, name)
            self.assertIsNotNone(resubmission["last_resubmitted_at"], name)

    def test_delegate_scenario_is_flagged(self):
        data = self.fetch("LV-2026-27-900003")
        current = data["current_stage"]
        self.assertTrue(current["is_delegate"])
        self.assertEqual(current["on_behalf_of"], "Dr. Grace Mwale")
        self.assertEqual(current["approver_name"], "Dr. Henry Gondwe")
        stage = data["stages"][0]
        self.assertTrue(stage["approver"]["is_delegate"])
        self.assertEqual(stage["approver"]["on_behalf_of"], "Dr. Grace Mwale")

    def test_approved_scenario_approved_at(self):
        data = self.fetch("LV-2026-27-900004")
        self.assertEqual(data["approved_at"], "2026-10-18T06:20:15Z")

    def test_can_resubmit_exactly_for_resubmittable_statuses(self):
        # Every reference in the workbook must exhibit the boolean rule, and the
        # two resubmittable statuses must be present across the corpus.
        seen_statuses = set()
        for reference, name in load_assignments().items():
            data = self.fetch(reference)
            seen_statuses.add(data["status"])
            expected = data["status"] in RESUBMITTABLE_STATUSES
            self.assertEqual(
                data["resubmission"]["can_resubmit"], expected, reference
            )
        self.assertTrue({"rejected", "correction_required"}.issubset(seen_statuses))