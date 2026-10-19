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
    """Create a user, defaulting to an ordinary employee.

    ``role`` accepts a :class:`~users.models.User.Role` value *or* one of the six
    approver role codes (``"hod"``, ``"registrar"``, ...). An approver code
    produces a real ``ApproverRole`` plus an institution-wide holding, because
    setting the user row alone no longer makes somebody an approver — see
    :func:`workflows.services.is_approver_user`.
    """
    from workflows.testing import create_user_with_role

    kwargs.setdefault("role", User.Role.EMPLOYEE)
    return create_user_with_role(
        username, role=kwargs.pop("role"), password=kwargs.pop("password", "testpass123"), **kwargs
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
            team_id=None,
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
        # Mirrors the database provider: only a missing id returns None, and
        # ``as_of`` is no longer a gate since effective dating was retired.
        for rules in self.leave_types:
            if rules.id == leave_type_id:
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


def _active_user_id_for_role(role: str, exclude: int | None = None) -> int | None:
    """The lowest-id active user *holding* ``role``, optionally not ``exclude``.

    Resolution goes through the role tables — a section appointment or an
    institution-wide assignment — not ``User.role``, which no longer records an
    approval position. With one approver per section the lowest id of the
    holders is simply the one appointed; a stub that needs a specific person to
    act registers them explicitly instead.

    The applicant's own id is excluded so a stubbed chain never resolves a stage
    to the applicant, a configuration ``assign_workflow`` rejects outright.
    """
    from workflows.models import (
        SectionMember,
    )
    from organisation.models import (
        ApproverRole,
        RoleAssignment,
    )

    role_obj = ApproverRole.objects.filter(code=role, is_active=True).first()
    if role_obj is None:
        return None
    holder_ids = set(
        SectionMember.objects.filter(section__approver_role=role_obj)
        .values_list("user_id", flat=True)
    ) | set(
        RoleAssignment.objects.filter(role=role_obj).values_list("user_id", flat=True)
    )
    from django.contrib.auth import get_user_model

    candidates = (
        get_user_model()
        .objects.filter(id__in=holder_ids, is_active=True)
        .order_by("id")
    )
    if exclude is not None:
        candidates = candidates.exclude(id=exclude)
    return candidates.values_list("id", flat=True).first()


def register_chain_approvers(
    stub, *roles: str, prefix: str = "approver"
) -> dict[str, object]:
    """Register one distinct active approver per role and return them by role.

    Each approver gets a real :class:`RoleAssignment`, so
    :func:`workflows.services.is_approver_user` — and therefore the approvals
    API — sees them as approvers. Creating users with ``User.role`` alone would
    leave them unable to use the API, which is the point of the feature.

    Submission-focused tests only care about what submission does, not about who
    approves. Rather than repeating four ``register_approver`` calls in every
    ``setUp``, they call this to obtain a chain the product would accept.
    """
    from workflows.testing import make_approver

    chain = roles or ("supervisor", "hod", "registrar", "dvc")
    approvers = {
        role: make_approver(
            role,
            username=f"{prefix}-{role}@test.luanar",
            institution_wide=True,
        )
        for role in chain
    }
    for role, user in approvers.items():
        stub.workflow.register_approver(role, user)
    return approvers


class StubWorkflowProvider:
    """Controllable in-memory workflow provider (Unit 16).

    Mirrors the ``WorkflowProvider`` protocol. A role registered with
    :meth:`register_approver` uses that user. An unregistered role resolves to
    the lowest-id active user holding it, or — when no such user exists — to a
    lazily created filler approver for that role. Either way the stage never
    resolves to the applicant, which ``assign_workflow`` now rejects outright,
    so the double only ever produces chains the product would accept.
    """

    def __init__(self):
        self.approvers: dict[str, set[int]] = {}
        self.default_chain = ("supervisor", "hod", "registrar", "dvc")
        self.strict = False
        self.cancellation_roles = ("supervisor", "hod")
        self.block_cancellation = False
        self._fillers: dict[str, int] = {}

    def set_chain(self, *roles: str) -> None:
        self.default_chain = tuple(roles)

    def register_approver(self, role: str, user) -> None:
        """Add ``user`` to ``role``'s section. Repeatable: sections take any-of."""
        self.approvers.setdefault(role, set()).add(user.id)

    def _filler_approver_id(self, role: str) -> int:
        """A stable, non-applicant approver for an otherwise unstaffed role.

        Built as a real approver (role row plus institution-wide assignment) so
        the filler is indistinguishable from a hand-registered one, including to
        :func:`workflows.services.is_approver_user`.
        """
        from workflows.testing import make_approver

        if role not in self._fillers:
            user = make_approver(
                role, username=f"stub-filler-{role}@test.luanar", institution_wide=True
            )
            self._fillers[role] = user.id
        return self._fillers[role]

    def get_stage_definitions(self, application):
        """A planned chain, one definition per step, as a set of approvers.

        A section is decided by whichever eligible person acts first, so the stub
        resolves to a *set* here exactly as the real provider does, and a role
        registered more than once is a section with several members.

        The applicant is removed from every set, as the real provider removes
        them. Where that leaves nobody the stage is *skipped* rather than routed
        to a stand-in (Unit 30), mirroring
        :meth:`workflows.providers.DatabaseWorkflowProvider.get_stage_definitions`:
        the first stage staffed by the applicant alone is skipped, so is every
        stage below it, and if that was the last stage the application is handed
        to HR instead of being left with nothing to decide.

        A *shared* stage is not a skip: the applicant leaves a colleague behind,
        so that stage routes to them and the chain still opens at section one.
        """
        from workflows.providers import StageDefinition
        from workflows.testing import ensure_roles

        applicant_id = application.employee_id
        roles = ensure_roles(*self.default_chain)

        resolved = []
        for order, code in enumerate(self.default_chain, start=1):
            members = set(self.approvers.get(code, ()))
            if not members and not self.strict:
                fallback = _active_user_id_for_role(code, exclude=applicant_id)
                if fallback is None:
                    fallback = self._filler_approver_id(code)
                members = {fallback}
            resolved.append((order, code, roles[code], members))

        # The first stage the applicant staffed alone. Comparing the *raw* member
        # set is what keeps a genuinely unstaffed stage refusing the submission
        # instead of masquerading as a skip.
        sole_applicant_order = next(
            (
                order
                for order, _code, _role, members in resolved
                if applicant_id is not None and members == {applicant_id}
            ),
            None,
        )

        definitions = []
        for order, code, role, members in resolved:
            skipped = sole_applicant_order is not None and order <= sole_applicant_order
            if skipped:
                reason = (
                    "Applicant cannot approve their own application."
                    if order == sole_applicant_order
                    else "Applicant is a higher-stage approver."
                )
            else:
                reason = ""
            definitions.append(
                StageDefinition(
                    order=order,
                    role=role.code,
                    role_label=role.label,
                    approver_user_ids=() if skipped else tuple(sorted(members - {applicant_id})),
                    role_id=role.pk,
                    history_scope=role.history_scope,
                    handles_cancellation=role.handles_cancellation,
                    skipped=skipped,
                    skip_reason=reason,
                )
            )

        if sole_applicant_order == len(resolved) and sole_applicant_order is not None:
            from workflows.providers import _hr_review_stage

            definitions.append(_hr_review_stage(len(resolved) + 1, applicant_id))
        return definitions

    def get_cancellation_stages(self, application):
        if self.block_cancellation:
            return []
        from django.db.models import Min
        from approvals.models import ApplicationStage
        from workflows.providers import CancellationStageSpec

        cycle = (
            ApplicationStage.objects.filter(application=application).aggregate(
                chain=Min("submission_cycle")
            )["chain"]
            or 1
        )
        # Filtered on the stage's own ``handles_cancellation`` snapshot, matching
        # the real provider: a role that has since been retired from
        # cancellation handling must not pick up an in-flight application.
        stages = ApplicationStage.objects.filter(
            application=application,
            submission_cycle=cycle,
            handles_cancellation=True,
        ).order_by("stage_order")
        return [
            CancellationStageSpec(
                order=stage.stage_order,
                role=stage.role,
                role_label=stage.role_label or stage.role,
                approver_user_ids=stage.eligible_approver_ids(),
            )
            for stage in stages
        ]

    def get_workflow_member_user_ids(self, application):
        from django.db.models import Min
        from approvals.models import ApplicationStage, ApplicationStageApprover

        cycle = (
            ApplicationStage.objects.filter(application=application).aggregate(
                chain=Min("submission_cycle")
            )["chain"]
            or 1
        )
        return list(
            ApplicationStageApprover.objects.filter(
                stage__application=application, stage__submission_cycle=cycle
            )
            .order_by("user_id")
            .values_list("user_id", flat=True)
            .distinct()
        )


def ensure_annual_leave_type(leave_type_id: int = 1) -> None:
    """Make ``leave_type_id`` a live type that deducts annual leave.

    An application a test builds directly carries no submission snapshot, so
    cancellation restoration resolves through the documented fallback: the
    currently configured type. With no consuming type the answer is
    deliberately "does not deduct", because a cancellation must never invent a
    restoration the configuration never granted. So a test that wants a
    restoration has to configure the type, exactly as HR would in the Leave
    Configuration app (there is no separate rule row to configure any more).
    """
    from leave_config.models import LeaveType

    LeaveType.objects.update_or_create(
        id=leave_type_id,
        defaults={
            "code": "annual",
            "name": "Annual leave",
            "max_duration_days": 30,
            "notice_days": 5,
            "requires_supporting_document": False,
            "eligibility_rules": [],
            "consumes_annual_entitlement": True,
        },
    )


class StubProviderMixin:
    """TestCase mixin that installs a stub provider + fixed ``today``.

    Call ``use_stub()`` at the start of a test (or in ``setUp``); it patches the
    ``get_provider`` import sites and every ``get_today`` seam for the duration
    of the test and returns the :class:`StubRulesProvider`. A stub workflow
    provider is attached as ``stub.workflow`` and installed for
    ``assign_workflow``.

    The cancellations package has its own ``get_today``, reached through two
    import sites. It is frozen here too, so a test that drives a cancellation
    through the API reads the same reference day as the service-level tests
    beside it. Without this the suite silently depends on the wall clock: a
    fixture that puts leave "15 days after the stub's today" eventually starts
    in the past, and an approved application's eligibility flips to
    ``leave_already_started`` without anything under test changing.
    """

    def use_stub(self, stub=None, today=TODAY) -> StubRulesProvider:
        stub = stub or StubRulesProvider()
        stub.workflow = StubWorkflowProvider()
        patchers = [
            mock.patch("leave.validation.pipeline.get_provider", return_value=stub),
            mock.patch("leave.validation.pipeline.get_today", return_value=today),
            mock.patch("leave.providers.get_provider", return_value=stub),
            # Unit 18 keeps its own clock seam and the HTTP views never pass a
            # ``today``, so without these two the suite reads the wall clock.
            mock.patch("leave.cancellations.services.get_today", return_value=today),
            mock.patch("leave.cancellations.providers.get_today", return_value=today),
            mock.patch(
                "workflows.providers.get_workflow_provider",
                return_value=stub.workflow,
            ),
            mock.patch("leave.cancellations.providers.get_today", return_value=today),
            mock.patch("leave.cancellations.services.get_today", return_value=today),
        ]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)
        return stub