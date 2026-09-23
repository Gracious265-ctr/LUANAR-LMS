"""Fixture-backed approval workflow provider (Unit 16).

Resolves an application's ordered stages from a fixture map keyed by the
employee's category and department/faculty, then binds each stage role to the
seeded active user holding that role. Supports the two example workflows
(``Supervisor -> HOD -> Registrar -> DVC`` for academics and
``HOD -> Dean -> Registrar -> DVC`` for administration) plus per-department
overrides so HOD/Dean scope checks are testable in dev.

Placeholder until Unit 20 wires the real Unit 6 workflow store; the swap is
the ``WORKFLOW_PROVIDER`` setting only (see
``docs/leave-rules-provider-contract.md`` for the handoff pattern).
"""

from users.models import User

from leave.providers import fixture_data as leave_fixture_data

from .errors import WorkflowValidationError
from .providers import StageDefinition, WorkflowProvider

# Keyed by (category, department). A blank department matches any department;
# each category falls back to its blank-department entry, then to
# ``DEFAULT_WORKFLOW_ROLES`` for unknown categories. Keys are exact matches to
# keep the map predictable; the blank entries are the defaults.
FIXTURE_WORKFLOWS: dict[tuple[str, str], tuple[str, ...]] = {
    ("academic", ""): ("supervisor", "hod", "registrar", "dvc"),
    ("administration", ""): ("hod", "dean", "registrar", "dvc"),
}

DEFAULT_WORKFLOW_ROLES: tuple[str, ...] = ("hod", "dean", "registrar", "dvc")


class FixtureWorkflowProvider(WorkflowProvider):
    """Read-only provider backed by the fixture workflow map and seeded users."""

    def get_stage_definitions(self, application) -> list[StageDefinition]:
        employee = application.employee
        category, department = self._employee_scope(employee)

        roles = FIXTURE_WORKFLOWS.get((category, department))
        if roles is None:
            roles = FIXTURE_WORKFLOWS.get((category, ""))
        if roles is None:
            roles = DEFAULT_WORKFLOW_ROLES

        definitions: list[StageDefinition] = []
        for order, role in enumerate(roles, start=1):
            approver = self._resolve_approver(role)
            if approver is None:
                raise WorkflowValidationError(
                    "stages",
                    f"No active user holds the {User.Role(role).label} approver role.",
                )
            definitions.append(
                StageDefinition(
                    order=order,
                    role=role,
                    role_label=User.Role(role).label,
                    approver_user_id=approver.id,
                )
            )
        return definitions

    def _resolve_approver(self, role: str):
        return (
            User.objects.filter(role=role, is_active=True)
            .order_by("username")
            .first()
        )

    def _employee_scope(self, employee) -> tuple[str, str]:
        profile = getattr(employee, "employee_profile", None)
        category = ""
        department = ""
        if profile is not None and profile.category:
            category = profile.category
        if profile is not None and profile.department:
            department = profile.department
        if not category:
            row = leave_fixture_data.EMPLOYEES.get(employee.username)
            if row and row.get("category"):
                category = row["category"]
        return (category, department)