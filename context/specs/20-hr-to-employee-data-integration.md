# Unit 20 — HR-to-Employee Data Integration

> **Implementation status: COMPLETE** — merged to `development` as commit
> `d5b9f95` ("feat(leave): database rules provider + employee dashboard (unit 20)").
> This spec records the **implemented** design and contract so later units
> (21–25) build against the real provider. Read `context/AGENTS.md` before
> starting; the definitive contract document is
> `backend/docs/leave-rules-provider-contract.md`.

## Goal

Replace the placeholder `FixtureRulesProvider` with a real, read-only provider
backed by the HR-track models (Units 2–5) and the entitlement/day ledger, so
leave validation, submission, balances and the employee dashboard all reflect
what HR actually manages — via one settings swap, with no other `leave/` code
importing the real models directly (decision D1).

## Design

### Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Provider wiring | Dotted-path settings `LEAVE_RULES_PROVIDER` only | Existing pattern (`get_provider()` factory, `leave/providers/__init__.py`); one-line swap in `config/settings/base.py` |
| `max_duration` unit | `calendar_days` | `LeaveRule.max_duration_days` stores no unit; LUANAR caps (maternity 90, paternity 10, compassionate 5) are calendar-day limits |
| `min_notice` unit | `working_days` | Same `LeaveRule` limitation; notice counted in working days per LUANAR policy |
| `is_active` | Always `True` | `LeaveType` has no active/inactive flag |
| `department_id` | Always `None` | `EmployeeProfile.department` is free text, not a reference |
| Financial-year label | `f"{start.year}-{end.year % 100:02d}"` | App convention (`LV-YYYY-YY`), e.g. `2026-27` |
| Ledger net used | `Σ deductions − Σ restorations` | From the append-only `LeaveBalanceTransaction`; consistent with Unit 18 restoration logic |
| Dashboard | Single real page served by new `my/overview` + `my/leave-types` endpoints | Removes fake/placeholder values (`"21"` balance, zero counts) |
| Shared seeds | `leave/defaults.py` idempotent `ensure_*` helpers | Used by `seed_dev_users` and `seed_approvals_dev` so the post-swap seeds run real validation |

### Scope boundaries

- **In scope:** `DatabaseRulesProvider`, `EmployeeProfile.gender`,
  `LeaveRule.eligibility_rules` JSON, my-data endpoints, dashboard rewrite,
  seeds, tests.
- **Out of scope (later units):** real `WORKFLOW_PROVIDER` (Unit 21),
  real `LEAVE_TRACKING_PROVIDER` (does the fixture still, Unit 21), balance
  deduction on final approval (Unit 23), notifications (Unit 22), audit
  aggregation (Unit 24), document generation (Unit 23).

## Implementation

### 1. `DatabaseRulesProvider` — `backend/leave/providers/database.py`

Implements the `RulesProvider` protocol (dataclasses in
`leave/providers/base.py`; reference behavior in `leave/tests/stubs.py`):

- `get_employee_for_user(user) -> EmployeeInfo | None` — via
  `user.employee_profile`; returns `None` when grade is blank or
  `appointment_date` is `None`; `gender`/`category` normalized to upper/None.
  `department_id=None` per decision D1.
- `get_leave_type_rules(leave_type_id, as_of) -> LeaveTypeRules | None` —
  resolves the effective-dated `LeaveRule` via `resolve_leave_rule`; `None`
  when the leave type or its effective rule is missing. `eligibility` is
  materialized from `LeaveRule.eligibility_rules` JSON into `EligibilityRule`
  tuples (D7 vocabulary: `gender`/`min_service`/`grade_range`/`employee_category`).
- `get_financial_year_for(d) -> FinancialYear | None` — via
  `financial_year_for_date`; label via `_financial_year_label`.
- `get_public_holidays(start, end) -> dict[date, str]` — `PublicHoliday` rows
  in range, ordered by date.
- `get_available_balance(employee_id, financial_year_label) -> Decimal` —
  `entitlement_days − ledger_net_used`; `_ledger_net_used` aggregates
  `LeaveBalanceTransaction` `DEDUCTION`/`RESTORATION` sums.
- `get_leave_balance(...) -> LeaveBalance` — raises
  `LeaveBalanceUnavailableError` when the employee has no usable grade record;
  otherwise `{entitlement, used, available}` from the same ledger sums
  (not the display estimate — the exact Unit 20 approach reused for balances).

### 2. Schema — migrations

- `leave` migration `0011_leaverule_eligibility_rules.py`: JSONField on
  `LeaveRule`. Serializer validation enforces the D7 shapes
  (`LeaveRuleSerializer.validate_eligibility_rules`).
- `users` migration `0003_employeeprofile_gender.py`: `EmployeeProfile.gender`
  TextChoices `M`/`F`.

### 3. Endpoints — `backend/leave/views/my_leave.py`

Registered in `leave/urls.py`, both `IsAuthenticated` only:

- `GET /api/leave/my/overview` (`MyLeaveOverviewView`) — dashboard payload:
  `profile` (grade, department, designation, category, gender,
  appointment_date), `financial_year`, `entitlement`/`used`/`available`
  (via provider; `None` when balance unavailable), `pending_applications`
  (statuses `submitted`/`pending`/`correction_required` any count — distinct
  from `BLOCKING_STATUSES` in `leave/models.py` which blocks new drafts),
  `upcoming_leaves`, `next_leave_start`.
- `GET /api/leave/leave-types` (`MyLeaveTypesView`) — configured leave types
  that currently have an effective rule only (form never offers a type the
  backend would reject as missing/not-yet-effective), each with
  `max_duration_days`, `requires_supporting_document`,
  `consumes_annual_entitlement`, `min_notice_days`, `eligibility`.

### 4. Seeds — `backend/leave/defaults.py`

Idempotent `ensure_default_entitlements`, `ensure_default_leave_types_and_rules`,
`ensure_default_financial_year` shared by `seed_dev_users` and
`seed_approvals_dev`. The approvals dev seed now runs real validation, so it
ensures its own config (grades, entitlements, leave types+rules, financial
year, employee gender for the maternity scenario) and no longer needs the
fixture-data lookup in `_leave_type_id`. `StubProviderMixin.use_stub` now also
patches `workflows.approvals_serializers.get_provider`.

### 5. Frontend

- `frontend/lib/leave-overview.ts` — typed overview + `formatIsoDate`.
- `frontend/app/api/leave/my/overview/route.ts` +
  `frontend/app/api/leave/leave-types/route.ts` — Next proxy routes.
- `frontend/lib/services/leaveTypes.ts` — real fetch mapping between
  snake_case and camelCase (replaces the Unit-4 mock; consumers use only
  `id`+`name`).
- `frontend/app/(dashboard)/dashboard/page.tsx` — rewritten to render the real
  employee record and balances; the approver card is fed by the existing
  `approvals/capabilities` payload.

## Dependencies

- No new packages. Uses Django ORM, existing DRF, existing `django-q2`.

## Verification checklist

- `DJANGO_SETTINGS_MODULE=config.settings.test TEST_DB_NAME=test_luanar_leave_20 uv run manage.py test leave users workflows --keepdb --parallel auto` green (contract suite `test_database_rules_provider.py` incl. ledger, eligibility, FY, holidays, effective-dated rules; `test_my_leave_views.py`; `test_leave_rule_serializer.py`).
- Backend full suite green (643 at implementation).
- Frontend `npm test` green (277 at implementation), `tsc --noEmit` clean, `eslint` clean, `npm run build` clean.
- `manage.py check` clean.
- Manual: `seed_dev_users` then an employee sees their real grade/balance on the dashboard; form offers only effective leave types; applying for a type with no effective rule is impossible.