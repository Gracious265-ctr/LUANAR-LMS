"""Fixture implementation of the organisation data provider (placeholder).

PLACEHOLDER, like every fixture provider in this repository: the org tree,
grades and employees in ``seed_data.json`` are invented stand-ins for the
university's real directory, shipped so the sync, the entitlement mapping
and the dashboard can be exercised before an external system exists. The
employee emails deliberately match the users ``seed_demo_data`` creates, so
identity reconciliation by email resolves end to end in development.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..provider import (
    EmployeeRecord,
    GradeRecord,
    OrganizationDataProvider,
    OrgUnitRecord,
    RoleHolder,
)

SEED_DATA_PATH = Path(__file__).with_name("seed_data.json")


class FixtureOrganizationDataProvider(OrganizationDataProvider):
    """Reads ``seed_data.json`` once; employees are indexed by id."""

    def __init__(self, seed_path: Path = SEED_DATA_PATH):
        with seed_path.open(encoding="utf-8") as handle:
            data = json.load(handle)
        self._grades = [GradeRecord(**row) for row in data["grades"]]
        self._employees = {
            row["id"]: EmployeeRecord(**row) for row in data["employees"]
        }
        self._org_units = [OrgUnitRecord(**row) for row in data["org_units"]]
        self._role_holders = [RoleHolder(**row) for row in data["role_holders"]]

    def get_employee(self, employee_id: str) -> EmployeeRecord | None:
        return self._employees.get(employee_id)

    def get_employees(
        self,
        *,
        branch=None,
        home_unit_id=None,
    ) -> list[EmployeeRecord]:
        records = list(self._employees.values())
        if branch is not None:
            records = [record for record in records if record.branch == branch]
        if home_unit_id is not None:
            records = [
                record for record in records if record.home_unit_id == home_unit_id
            ]
        return records

    def get_grade(self, grade_id: str) -> GradeRecord | None:
        for grade in self._grades:
            if grade.id == grade_id:
                return grade
        return None

    def get_grades(self) -> list[GradeRecord]:
        return list(self._grades)

    def get_org_units(self) -> list[OrgUnitRecord]:
        return list(self._org_units)

    def get_role_holders(self) -> list[RoleHolder]:
        return list(self._role_holders)
