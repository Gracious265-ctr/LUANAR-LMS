"""The organisation data-provider contract (refinement unit 05).

The provider is the single seam through which the system reads the
university's organisation data — employees, grades, org units and role
holders — so the source can move from a fixture to the real directory (HR
system, LDAP, ...) behind one setting (``ORG_DATA_BACKEND``) without touching
callers. Records are plain frozen dataclasses: the contract speaks values,
not ORM rows, and carries no Django imports beyond the standard library.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

EmployeeBranch = Literal["academic", "administrative"]

OrgUnitType = Literal[
    "institution",
    "campus",
    "faculty",
    "department_academic",
    "department_admin",
    "team",
]

RoleHolderRole = Literal[
    "hod",
    "dean",
    "manager",
    "supervisor",
    "campus_registrar",
    "institutional_registrar",
]


@dataclass(frozen=True)
class EmployeeRecord:
    """One employee as the external directory knows them."""

    id: str
    name: str
    email: str
    grade_id: str
    branch: EmployeeBranch
    gender: Literal["male", "female"]
    home_unit_id: str | None = None


@dataclass(frozen=True)
class GradeRecord:
    """One pay/grade level."""

    id: str
    name: str


@dataclass(frozen=True)
class OrgUnitRecord:
    """One node of the organisation tree."""

    id: str
    unit_type: OrgUnitType
    name: str
    parent_id: str | None = None
    has_teams: bool = False


@dataclass(frozen=True)
class RoleHolder:
    """Who holds a role on an org unit; ``employee_id=None`` means vacant."""

    org_unit_id: str
    role: RoleHolderRole
    employee_id: str | None = None


class OrganizationDataProvider(ABC):
    """Read-only view of the external organisation directory."""

    @abstractmethod
    def get_employee(self, employee_id: str) -> EmployeeRecord | None:
        """One employee by external id, or None when unknown."""

    @abstractmethod
    def get_employees(
        self,
        *,
        branch: EmployeeBranch | None = None,
        home_unit_id: str | None = None,
    ) -> list[EmployeeRecord]:
        """All employees, optionally narrowed by branch and/or home unit."""

    @abstractmethod
    def get_grade(self, grade_id: str) -> GradeRecord | None:
        """One grade by external id, or None when unknown."""

    @abstractmethod
    def get_grades(self) -> list[GradeRecord]:
        """Every grade the directory defines."""

    @abstractmethod
    def get_org_units(self) -> list[OrgUnitRecord]:
        """The organisation tree; parents may appear in any order."""

    @abstractmethod
    def get_role_holders(self) -> list[RoleHolder]:
        """Role assignments per org unit, including vacant posts."""
