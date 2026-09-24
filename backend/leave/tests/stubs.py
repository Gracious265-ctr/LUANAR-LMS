"""Test doubles for Unit 14: a stub rules provider and shared helpers.

The stub implements the same ``RulesProvider`` protocol as the fixture
provider (``leave.providers.base.RulesProvider``) but with values a test can
mutate per-case, so validator tests are insulated from the placeholder fixture
data (which is explicitly non-authoritative).
"""

from datetime import date
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model

from leave.providers.base import (
    EmployeeInfo,
    EligibilityRule,
    FinancialYear,
    LeaveTypeRules,
)

# Reference date for the whole suite: Monday 21 September 2026.
TODAY = date(2026, 9, 21)

# Placeholder public holiday: Wednesday 30 September 2026.
HOLIDAY = date(2026, 9, 30)

User = get_user_model()

# Earliest start date satisfying the 5-working-day annual notice from TODAY.
EARLIEST_ANNUAL_START = date(2026, 9, 28)


def make_user(username="employee@test.luanar", **kwargs):
    return User.objects.create_user(
        username=username,
        email=kwargs.pop("email", username),
        password="testpass123",
        **kwargs,
    )


def _leave_types():
    return (
        LeaveTypeRules(
            id=1,
            code="annual",
            name="Annual Leave",
            is_active=True,
            deducts_annual_balance=True,
            max_duration=None,
            max_duration_unit="working_days",
            min_notice=5,
            min_notice_unit="working_days",
            requires_document=False,
            eligibility=(),
            effective_from=date(2026, 1, 1),
        ),
        LeaveTypeRules(
            id=2,
            code="maternity",
            name="Maternity Leave",
            is_active=True,
            deducts_annual_balance=False,
            max_duration=90,
            max_duration_unit="calendar_days",
            min_notice=0,
            min_notice_unit="working_days",
            requires_document=True,
            eligibility=(EligibilityRule("gender", {"allowed": ["F"]}),),
            effective_from=date(2026, 1, 1),
        ),
        LeaveTypeRules(
            id=3,
            code="paternity",
            name="Paternity Leave",
            is_active=True,
            deducts_annual_balance=False,
            max_duration=10,
            max_duration_unit="calendar_days",
            min_notice=0,
            min_notice_unit="working_days",
            requires_document=False,
            eligibility=(EligibilityRule("gender", {"allowed": ["M"]}),),
            effective_from=date(2026, 1, 1),
        ),
        LeaveTypeRules(
            id=4,
            code="compassionate",
            name="Compassionate Leave",
            is_active=True,
            deducts_annual_balance=False,
            max_duration=5,
            max_duration_unit="working_days",
            min_notice=0,
            min_notice_unit="calendar_days",
            requires_document=False,
            eligibility=(),
            effective_from=date(2026, 1, 1),
        ),
    )


class StubRulesProvider:
    """Controllable in-memory provider for validator/pipeline tests."""

    def __init__(self):
        self.leave_types = _leave_types()
        self.financial_years = (
            FinancialYear(label="2026-27", start=date(2026, 7, 1), end=date(2027, 6, 30)),
            FinancialYear(label="2027-28", start=date(2027, 7, 1), end=date(2028, 6, 30)),
        )
        self.holidays: dict[date, str] = {}
        self.employees: dict[int, EmployeeInfo] = {}
        self.balances: dict[tuple[int, str], Decimal] = {}
        self.default_balance = Decimal("24")
        self.next_employee_id = 1

    def register_employee(
        self,
        user,
        *,
        grade="B",
        appointment_date=date(2022, 3, 15),
        category="administration",
        gender="F",
    ) -> EmployeeInfo:
        info = EmployeeInfo(
            id=user.id,
            user_id=user.id,
            grade=grade,
            appointment_date=appointment_date,
            category=category,
            department_id=None,
            gender=gender,
        )
        self.employees[user.id] = info
        return info

    def add_holiday(self, day: date, name: str = "Placeholder Public Holiday"):
        self.holidays[day] = name

    def set_balance(self, employee_id: int, label: str, value):
        self.balances[(employee_id, label)] = Decimal(value)

    def get_employee_for_user(self, user) -> EmployeeInfo | None:
        return self.employees.get(user.id)

    def get_leave_type_rules(self, leave_type_id: int, as_of: date):
        for rules in self.leave_types:
            if rules.id != leave_type_id:
                continue
            if not rules.is_active or rules.effective_from > as_of:
                return None
            return rules
        return None

    def get_financial_year_for(self, d: date):
        for year in self.financial_years:
            if year.start <= d <= year.end:
                return year
        return None

    def get_public_holidays(self, start: date, end: date) -> dict[date, str]:
        return {
            day: name
            for day, name in self.holidays.items()
            if start <= day <= end
        }

    def get_available_balance(self, employee_id: int, financial_year_label: str):
        return self.balances.get(
            (employee_id, financial_year_label), self.default_balance
        )


class StubWorkflowProvider:
    """Controllable in-memory workflow provider (Unit 16).

    Mirrors the ``WorkflowProvider`` protocol. Roles not registered with an
    explicit approver fall back to the application's own employee, so existing
    submission tests keep passing without extra setup; approval tests register
    real approver users per role.
    """

    def __init__(self):
        self.approvers: dict[str, int] = {}
        self.default_chain = ("supervisor", "hod", "registrar", "dvc")
        self.strict = False
        self.cancellation_roles = ("supervisor", "hod")
        self.block_cancellation = False

    def set_chain(self, *roles: str) -> None:
        self.default_chain = tuple(roles)

    def register_approver(self, role: str, user) -> None:
        self.approvers[role] = user.id

    def get_stage_definitions(self, application):
        from workflows.models import STAGE_ROLE_LABELS
        from workflows.providers import StageDefinition

        definitions = []
        for order, role in enumerate(self.default_chain, start=1):
            approver_id = self.approvers.get(role)
            if approver_id is None and not self.strict:
                approver_id = application.employee_id
            definitions.append(
                StageDefinition(
                    order=order,
                    role=role,
                    role_label=STAGE_ROLE_LABELS[role],
                    approver_user_id=approver_id,
                )
            )
        return definitions

    def get_cancellation_stages(self, application):
        if self.block_cancellation:
            return []
        from django.db.models import Min
        from workflows.models import STAGE_ROLE_LABELS, ApplicationStage
        from workflows.providers import CancellationStageSpec

        cycle = (
            ApplicationStage.objects.filter(application=application).aggregate(
                chain=Min("submission_cycle")
            )["chain"]
            or 1
        )
        stages = ApplicationStage.objects.filter(
            application=application,
            submission_cycle=cycle,
            role__in=self.cancellation_roles,
        ).order_by("stage_order")
        return [
            CancellationStageSpec(
                order=stage.stage_order,
                role=stage.role,
                role_label=stage.role_label
                or STAGE_ROLE_LABELS.get(stage.role, stage.role),
                approver_user_id=stage.assigned_approver_id,
            )
            for stage in stages
        ]

    def get_workflow_member_user_ids(self, application):
        from django.db.models import Min
        from workflows.models import ApplicationStage

        cycle = (
            ApplicationStage.objects.filter(application=application).aggregate(
                chain=Min("submission_cycle")
            )["chain"]
            or 1
        )
        return list(
            ApplicationStage.objects.filter(
                application=application, submission_cycle=cycle
            )
            .order_by("stage_order")
            .values_list("assigned_approver_id", flat=True)
        )


class StubProviderMixin:
    """TestCase mixin that installs a stub provider + fixed ``today``.

    Call ``use_stub()`` at the start of a test (or in ``setUp``); it patches the
    two ``get_provider`` import sites and ``get_today`` for the duration of the
    test and returns the :class:`StubRulesProvider`. A stub workflow provider
    is attached as ``stub.workflow`` and installed for ``assign_workflow``.
    """

    def use_stub(self, stub=None, today=TODAY) -> StubRulesProvider:
        stub = stub or StubRulesProvider()
        stub.workflow = StubWorkflowProvider()
        patchers = [
            mock.patch("leave.validation.pipeline.get_provider", return_value=stub),
            mock.patch("leave.validation.pipeline.get_today", return_value=today),
            mock.patch("leave.providers.get_provider", return_value=stub),
            mock.patch(
                "workflows.providers.get_workflow_provider",
                return_value=stub.workflow,
            ),
        ]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)
        return stub