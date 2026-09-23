"""Fixture-backed tracking provider (Unit 15).

Maps ``application.reference_number`` to a named scenario in
``fixtures/assignments.json`` (falling back to ``pending_first_stage`` so any
real application submitted through Unit 14 is trackable in dev), then loads the
scenario JSON from ``fixtures/scenarios/{name}.json`` and returns a
``WorkflowTracking`` built from it. Does no database access.

Scenario JSON files mirror the provisional tracking contract (stages, events,
rejection, correction, resubmission). Unit 20 replaces this provider with one
reading the real Units 7-11 tables; the fixtures directory and the seed command
are then deleted while the serializers, view and tests stay.
"""

import json
from datetime import datetime
from pathlib import Path

from .contracts import (
    ResubmissionInfo,
    TrackedApprover,
    TrackedEvent,
    TrackedOutcome,
    TrackedStage,
    WorkflowTracking,
)
from .provider import TrackingProvider

FIXTURES_DIR = Path(__file__).parent / "fixtures"

FALLBACK_SCENARIO = "pending_first_stage"


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class FixtureTrackingProvider(TrackingProvider):
    """Read-only provider backed by the scenario fixture files."""

    def get_workflow_tracking(self, application) -> WorkflowTracking:
        scenario = self._load_scenario(application.reference_number)
        return self._to_tracking(scenario)

    def _load_scenario(self, reference_number: str | None) -> dict:
        assignments = _load_json(FIXTURES_DIR / "assignments.json")
        name = assignments.get(reference_number, FALLBACK_SCENARIO)
        return _load_json(FIXTURES_DIR / "scenarios" / f"{name}.json")

    def _to_tracking(self, scenario: dict) -> WorkflowTracking:
        return WorkflowTracking(
            status=scenario["status"],
            approved_at=_parse_dt(scenario.get("approved_at")),
            current_stage=scenario.get("current_stage"),
            stages=tuple(self._stage(item) for item in scenario["stages"]),
            events=tuple(self._event(item) for item in scenario["events"]),
            rejection=self._outcome(scenario.get("rejection")),
            correction=self._outcome(scenario.get("correction")),
            resubmission=self._resubmission(scenario["resubmission"]),
            submission_cycle=scenario.get("submission_cycle", 1),
            resubmissions=tuple(scenario.get("resubmissions") or ()),
            decisions=tuple(scenario.get("decisions") or ()),
        )

    def _stage(self, item: dict) -> TrackedStage:
        approver = item.get("approver")
        return TrackedStage(
            order=item["order"],
            role=item["role"],
            role_label=item["role_label"],
            state=item["state"],
            approver=TrackedApprover(**approver) if approver else None,
            assigned_at=_parse_dt(item.get("assigned_at")),
            decided_at=_parse_dt(item.get("decided_at")),
            comment=item.get("comment"),
        )

    def _event(self, item: dict) -> TrackedEvent:
        return TrackedEvent(
            id=item["id"],
            type=item["type"],
            occurred_at=_parse_dt(item["occurred_at"]),
            stage_order=item.get("stage_order"),
            actor=item["actor"],
            comment=item.get("comment"),
            resubmission_number=item.get("resubmission_number"),
        )

    def _outcome(self, item: dict | None) -> TrackedOutcome | None:
        if not item:
            return None
        return TrackedOutcome(
            stage_order=item["stage_order"],
            role_label=item["role_label"],
            approver_name=item["approver_name"],
            decided_at=_parse_dt(item["decided_at"]),
            reason=item.get("reason", item.get("comment", "")),
        )

    def _resubmission(self, item: dict) -> ResubmissionInfo:
        return ResubmissionInfo(
            count=item.get("count", 0),
            last_resubmitted_at=_parse_dt(item.get("last_resubmitted_at")),
            can_resubmit=item.get("can_resubmit", False),
            returns_to_stage=item.get("returns_to_stage"),
        )