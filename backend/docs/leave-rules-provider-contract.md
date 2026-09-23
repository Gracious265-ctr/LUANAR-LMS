# `RulesProvider` contract (Unit 20 handoff)

Validators, submission and reference generation depend on
`leave.providers.base.RulesProvider` (a `Protocol`). The current implementation,
`FixtureRulesProvider` (`leave/providers/fixture.py`), returns **placeholder
data only** and must be replaced by a provider backed by the HR-track models
from Units 2–5. The swap is one new class plus one settings change
(`LEAVE_RULES_PROVIDER`); nothing else in `leave/` imports the real models
(decision D1).

`get_provider()` in `leave/providers/__init__.py` instantiates the class
pointed to by the `LEAVE_RULES_PROVIDER` setting (a dotted path).

## Settings

- `LEAVE_RULES_PROVIDER` — dotted path to the `RulesProvider` subclass.
- `LEAVE_BLOCKING_STATUSES` — employee account statuses that block leave
  submission (precondition `EMPLOYEE_PROFILE_MISSING`).

## Methods to implement

All dataclasses live in `leave/providers/base.py`; `None` means "unknown".

```python
def get_employee_for_user(self, user) -> EmployeeInfo | None
```

Maps an authenticated `auth.User` to `EmployeeInfo`:
`{id, user_id, grade, appointment_date, category, department_id, gender}`.
Return `None` for users with no employee profile or with a status in
`LEAVE_BLOCKING_STATUSES`.

- **Real models:** the `Employee` model from the HR unit (Unit 2/3), keyed by
  `user_id`. Map `grade`, `category`, `department`, `gender` and
  `appointment_date` 1:1.

```python
def get_leave_type_rules(self, leave_type_id: int, as_of: date) -> LeaveTypeRules | None
```

The rules of one leave type **as evaluated for one application**: `None` for a
missing, inactive, or not-yet-effective (`effective_from > as_of`) leave type.
`LeaveTypeRules` carries `{id, code, name, is_active, deducts_annual_balance,
max_duration, max_duration_unit, min_notice, min_notice_unit, requires_document,
eligibility, effective_from}`.

- **Real models:** the `LeaveType` table and its `LeaveRule` rows (Unit 4),
  current as of `as_of`. `deducts_annual_balance` comes from the rule that
  deducts against the annual entitlement; `max_duration`/`min_notice` with their
  units from their respective rules; `eligibility` is the currently effective
  eligibility rules on the leave type.

```python
def get_financial_year_for(self, d: date) -> FinancialYear | None
```

The financial year containing `d`, or `None` if none is configured.
`FinancialYear` is `{label, start, end}` (end inclusive).

- **Real models:** the financial-year table (Unit 5). LUANAR's actual year
  start/end must replace the placeholder `2026-07-01 → 2027-06-30`.

```python
def get_public_holidays(self, start: date, end: date) -> dict[date, str]
```

Inclusive range of observed holidays, date → holiday name. May be empty. No
processing of weekend collisions — the working-days engine treats a holiday on a
weekend as a non-event.

- **Real models:** the public-holidays table (Unit 4), filtered to the range.

```python
def get_available_balance(self, employee_id: int, financial_year_label: str) -> Decimal
```

Employees' remaining annual leave (entitlement minus approved/deducted leave)
for the given financial year. Used only by the `balance` check, which fires
`INSUFFICIENT_BALANCE` when the requested working days exceed it.

- **Real models:** the entitlement + leave-day ledger for the employee and
  financial year (Unit 5). The fixture implements this as entitlement with no
  deductions.

```python
def get_leave_balance(self, employee_id: int, financial_year_label: str) -> LeaveBalance
```

Read-only annual-leave balances for approvers (Unit 16): `LeaveBalance`
`{entitlement, used, available}`. The approvals review payload renders this
block; no approver action ever mutates it. Must return zeros for employees
without an entitlement. The fixture implements it as entitlement-only; the stub
returns the current default balance. Implementations raise
`leave.providers.base.LeaveBalanceUnavailableError` when the balance cannot be
resolved at all (as opposed to a legitimately zero balance) — the approvals
API renders that case as an explicit unknown (`null` fields), while any other
exception is treated as a bug and propagates.

- **Real models:** the entitlement + leave-day ledger for the employee and
  financial year (Unit 5), same values as `get_available_balance` split into
  `entitlement`, `used` and `available`.

## Seeing it in action

`StubRulesProvider` (`leave/tests/stubs.py`) is a reference implementation with
explicit, per-test data and a fixed `today`. Run
`leave/tests/test_pipeline.py` against a new provider to check behaviour.