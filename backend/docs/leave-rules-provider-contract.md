# `RulesProvider` contract (Unit 20 — swapped)

Validators, submission and reference generation depend on
`leave.providers.base.RulesProvider` (a `Protocol`). Since Unit 20 the
default implementation is `DatabaseRulesProvider`
(`leave/providers/database.py`), backed by the real HR-track models from
Units 2–5. Nothing in `leave/` imports those models directly (decision D1);
the swap is one settings change.

`get_provider()` in `leave/providers/__init__.py` instantiates the class
pointed to by the `LEAVE_RULES_PROVIDER` setting (a dotted path).

## Settings

- `LEAVE_RULES_PROVIDER` — dotted path to the `RulesProvider` subclass,
  currently `leave.providers.database.DatabaseRulesProvider`.
- `LEAVE_BLOCKING_STATUSES` — employee account statuses that block leave
  submission (precondition `EMPLOYEE_PROFILE_MISSING`). Still policy-by-config
  only: `EmployeeProfile` has no status column.

## Methods to implement

All dataclasses live in `leave/providers/base.py`; `None` means "unknown".

```python
def get_employee_for_user(self, user) -> EmployeeInfo | None
```

Maps an authenticated `auth.User` to `EmployeeInfo`:
`{id, user_id, grade, appointment_date, category, department_id, gender}`.
Return `None` for users with no employee profile, or a blank grade /
missing appointment date.

- **Implementation:** reads `users.EmployeeProfile` keyed by `user_id`
  (`EmployeeProfile.gender` — a Unit 20 column), maps `grade`/`category`/
  `gender`/`appointment_date` 1:1. `department_id` stays `None` because
  `EmployeeProfile.department` is free text, not a foreign key, and no
  consumer uses the id.

```python
def get_leave_type_rules(self, leave_type_id: int, as_of: date) -> LeaveTypeRules | None
```

The rules of one leave type **as evaluated for one application**: `None` for a
missing or not-yet-effective (`effective_from > as_of`) leave type.
`LeaveTypeRules` carries `{id, code, name, is_active, deducts_annual_balance,
max_duration, max_duration_unit, min_notice, min_notice_unit, requires_document,
eligibility, effective_from}`.

- **Implementation:** resolves the currently effective `LeaveRule` for the
  `LeaveType` as of `as_of` (`leave.services.resolve_leave_rule`).
  `requires_document` from `requires_supporting_document`; `eligibility` from
  the JSON `eligibility_rules` column (list of `{"type", "params"}`).
- **Units (decision D4):** `LeaveRule` stores day counts with no units. The
  provider derives them by code: `annual` → `working_days`, every other type →
  `calendar_days`, for both `max_duration` and `min_notice`.

```python
def get_financial_year_for(self, d: date) -> FinancialYear | None
```

The financial year containing `d`, or `None` if none is configured.
`FinancialYear` is `{label, start, end}` (end inclusive).

- **Implementation:** `leave.services.financial_year_for_date` over the
  financial-year table; the label is derived
  `{start.year}-{str(end.year)[-2:]}` (decision D6). No year is invented — HR
  configures the real LUANAR period via the Unit 5 UI.

```python
def get_public_holidays(self, start: date, end: date) -> dict[date, str]
```

Inclusive range of observed holidays, date → holiday name. May be empty. No
processing of weekend collisions — the working-days engine treats a holiday on a
weekend as a non-event.

- **Implementation:** the public-holidays table filtered to the range.

```python
def get_available_balance(self, employee_id: int, financial_year_label: str) -> Decimal
```

Employees' remaining annual leave (entitlement minus approved/deducted leave)
for the given financial year. Used only by the `balance` check, which fires
`INSUFFICIENT_BALANCE` when the requested working days exceed it.

- **Implementation (decision D7):** resolved annual entitlement for the
  employee's grade plus the ledger net
  (`LeaveBalanceTransaction` restorations minus deductions for that financial
  year), clamped at zero. Returns `0` when the profile is missing.

## Seeing it in action

`DatabaseRulesProvider` is covered directly in
`leave/tests/test_database_provider.py`; `StubRulesProvider`
(`leave/tests/stubs.py`) remains the reference implementation for validator
tests with explicit, per-test data and a fixed `today`. The employee-facing
`GET /api/v1/leave/me/summary/` endpoint (`leave/views/me.py`) exposes the
same data for the dashboard.