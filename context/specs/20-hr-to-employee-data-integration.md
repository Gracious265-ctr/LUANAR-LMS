# Unit 20 — HR-to-Employee Data Integration

<<<<<<< HEAD
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
=======
read `context/AGENTS.md` before starting. Depends on the HR track (Units 2–5
models and endpoints already merged on `development`) and the Employee track
(Units 12–14). Build-plan §6 Unit 20 — the first integration-track unit.

## 1. Goal

Replace the fixture-backed rules provider with one that reads **real
HR-managed records**, so the employee experience reflects the actual
configuration HR maintains: the leave rules and entitlements an application is
validated against, the financial year and holidays working-day math uses, and
the balance the employee sees. Visible result (build-plan): *"The employee
dashboard reflects the actual employee record configured by HR."*

Unit 20 swaps **only the rules provider** (`LEAVE_RULES_PROVIDER`). The
tracking and workflow providers stay fixture-backed behind their own settings —
re-pointing those to real `ApplicationStage`/`ApprovalDecision`/`Workflow` data
is the Unit 21 boundary (Workflow-to-Approver Integration).

## 2. Decisions locked in

| # | Decision |
|---|---|
| D1 | **Scope = rules provider only.** `LEAVE_RULES_PROVIDER` moves off `FixtureRulesProvider` to a DB-backed `DatabaseRulesProvider` (`leave/providers/database.py`). `LEAVE_TRACKING_PROVIDER` and `WORKFLOW_PROVIDER` are untouched (Unit 21). `LEAVE_BALANCE_PROVIDER` (`LedgerBalanceProvider`) already reads the real ledger and stays. |
| D2 | **Gender column added.** `users.EmployeeProfile.gender` (`M`/`F`, blank default), because the eligibility engine supports gender rules and the provider contract requires `gender` on `EmployeeInfo`. No `status` column exists yet — `LEAVE_BLOCKING_STATUSES` continues to be policy-by-config; a future account-status feature can populate it (documented, no schema invented). |
| D3 | **Structured eligibility added.** `leave.LeaveRule.eligibility_rules` = `JSONField` (list of `{type, params}` objects, default `[]`), the machine-readable input for the eligibility validator; the free-text `eligibility` field stays as HR's human description. The validation engine's closed vocabulary is unchanged (`gender`, `min_service`, `grade_range`, `employee_category`; unknown types fail closed). |
| D4 | **Duration/notice units derived by leave-type code, not stored.** `LeaveRule` has only `max_duration_days`/`min_notice_days` (no unit columns; Unit 4 stored none). The provider maps `code == "annual"` → `working_days` and every other type → `calendar_days`, for both `max_duration` and `min_notice`. This preserves Unit 14 D2 ("annual leave uses working days; special leave uses whatever its rule says"). Flagged assumption: if LUANAR ever needs per-type heterogeneity in units, add unit columns to `LeaveRule` (deferred — no current requirement). |
| D5 | **No financial-year/holiday seed.** Unit 5 explicitly forbids inventing LUANAR organization-specific dates. The DB provider returns real `FinancialYear`/`PublicHoliday` rows only; **HR configures the active financial year and holidays through the existing Unit 5 HR UI first**. Submissions (and the dev `seed_approvals_dev` command) fail with `NO_FINANCIAL_YEAR_CONFIGURED` when none exists — correct, documented behavior. |
| D6 | **Financial-year label is derived, not stored.** `{start.year}-{end.year[-2:]}` (`2026-2027` years → `2026-27`), same convention already used by `seed_approvals_dev`. New shared helper `financial_year_label()` in `leave/services/`; the provider and the new employee summary endpoint both use it. |
| D7 | **Available balance = resolved entitlement + ledger net.** `get_available_balance(employee_id, label)` resolves the employee's grade → `GradeEntitlement` via the existing `resolve_grade_entitlement` service (as of today), adds restorations minus deductions from the `LeaveBalanceTransaction` ledger, clamps at zero — the real-table equivalent of what `FixtureRulesProvider` stubbed with its own registry. |
| D8 | **Employee-facing summary endpoint.** New `GET /api/v1/leave/me/summary/` (authenticated) returns profile (grade, category, department, faculty, gender, appointment_date), resolved entitlement (`days`, `effective_from`), current financial-year (`label`, `start`, `end` — the active one per `active_financial_year()`), and `available_balance`. The dashboard consumes it; everything is nullable when the employee has no profile/grade or HR hasn't configured rows. |
| D9 | **Active-without-rule semantics.** A `LeaveType` with no `LeaveRule` effective on or before the query date is treated as unavailable (`get_leave_type_rules` → `None`, i.e. `LEAVE_TYPE_UNAVAILABLE`) — the DB equivalent of the old `is_active`/`effective_from` check. |
| D10 | No delete/audit-schema changes. `users` and `leave` migrations only add `gender` / `eligibility_rules`; `LeaveRuleSerializer` gains `eligibility_rules` in its fields + audit list; `EmployeeSerializer` gains `gender`. |

## 3. Implementation order (verify each step)

### 3.1 Schema + migrations

- `users/models.py`: `EmployeeProfile.Gender` TextChoices (`M`/`F`, `MALE`/`FEMALE` labels), field `gender = CharField(max_length=1, choices, blank=True, default="")`. Migration `users/0002_...`.
- `leave/models.py`: `LeaveRule.eligibility_rules = JSONField(default=list, blank=True)` (list of `{"type", "params"}`). Migration `leave/0008_...` (number = current next).
- Serializers: `LeaveRuleSerializer` adds `eligibility_rules` (fields + `audit_fields`); `EmployeeSerializer` adds `gender`. HR forms gain a gender select (employees) and a JSON array editor (leave rules, optional → defaults `[]`).

### 3.2 Services helper

- `leave/services/__init__.py`: `financial_year_label(year: FinancialYear) -> str` (`f"{year.start_date.year}-{str(year.end_date.year)[-2:]}"`).
- `leave/services/__init__.py`: `resolved_annual_entitlement(grade, as_of=None) -> GradeEntitlement | None` wraps `resolve_grade_entitlement` (keeps the ledger-agnostic entitlement lookup at one call site).

### 3.3 `DatabaseRulesProvider` (`leave/providers/database.py`)

All five protocol methods, real tables, no fixture imports, `select_related`/filters to avoid N+1:

- `get_employee_for_user(user)`: `EmployeeProfile` via `user.employee_profile`; requires non-blank `grade` (else `None`, per contract); `appointment_date` maps through as `date | None` because the column is nullable — a profile that exists without one is still an employee, and the run reports `ELIGIBILITY_DATA_MISSING` on the rule that needs it rather than `EMPLOYEE_PROFILE_MISSING`, which would deny the profile exists. `category` (or `None`), `department_id=None` (department is a string, not a FK — documented), `gender` from the new column. Blocker statuses: none evaluated (D2).
- `get_leave_type_rules(leave_type_id, as_of)`: effective `LeaveRule` via `resolve_leave_rule`; `None` if absent (D9). Units by code (D4). `eligibility` tuple from `eligibility_rules`. `effective_from` = rule's date.
- `get_financial_year_for(d)`: `financial_year_for_date(d)` mapped to the dataclass with `label` from D6.
- `get_public_holidays(start, end)`: `public_holidays_between` → `{date: name}`.
- `get_available_balance(employee_id, label)`: resolve profile by `user_id` → grade → `resolved_annual_entitlement` days (0 when unmapped) + ledger net (reuse the same aggregation the fixture used, via `LeaveBalanceTransaction`), clamp at 0.

Settings: `LEAVE_RULES_PROVIDER = "leave.providers.database.DatabaseRulesProvider"` in `config/settings/base.py` (update the handoff comment).

### 3.4 Seed updates (`seed_dev_users`)

- Add `gender` to each seeded profile (matching the fixture registry: employee F, supervisor M, hod M, dean M, registrar F, dvc F, hr E/M).
- On the seeded special-leave defaults, set `eligibility_rules` (maternity → `[{"type": "gender", "params": {"allowed": ["F"]}}]`; paternity → `... ["M"] ...`); others `[]`.
- **No FY/holiday seed** (D5).
- `seed_approvals_dev`: fail with a clear `CommandError` when `active_financial_year()` is `None`, instead of silently submitting against nothing.

### 3.5 Employee summary endpoint

- `leave/serializers/__init__.py`: `LeaveSummarySerializer` (nested `profile`, `entitlement`, `financial_year`, `available_balance`; all readable; `days` as int-or-null, `available_balance` as Decimal string).
- `leave/views/__init__.py`: `LeaveSummaryView` (`APIView`, `IsAuthenticated`) — uses `DatabaseRulesProvider` (via `get_provider()`) for balance-centric values and services for profile/FY/entitlement.
- `leave/urls.py`: `path("leave/me/summary/", LeaveSummaryView.as_view(), ...)`.
- Frontend: proxy `frontend/app/api/leave/me/summary/route.ts`; `lib/` client `getLeaveSummary()` with a typed result.

### 3.6 Dashboard

- `app/(dashboard)/dashboard/page.tsx`: replace the hard-coded `"21"` Available Balance stat with the live `available_balance` (from the summary, formatted like the review card), and surface grade · entitlement · financial-year when present (profile line under the welcome heading). Other stat cards stay.

### 3.7 Docs

- `backend/docs/leave-rules-provider-contract.md`: mark the swap complete (real class + settings change; note fixture deactivation lives behind the removed default), note D4 unit derivation and D5 FY/holiday prerequisite.
- `context/progress-tracker.md`: mark Unit 21 next after the Unit 20 entry.
- `context/specs/19-*.md` "Reconciliation with real Units 2–5 rules … (Unit 20)" notes → the reconciliation now lives at 20.

### 3.8 Tests

- New `backend/leave/tests/test_database_provider.py`: per-method coverage against real rows — employee mapping (grade/appointment/category/gender, missing-profile → None, blank grade → None), leave-type rules (effective rule, not-yet-effective → None, unit derivation annual vs special, eligibility tuple from JSON, deducts flag from `consumes_annual_entitlement`), financial year (contains-date + label; missing → None), holidays (range filter), balance (entitlement + ledger net + clamp) — mirroring the fixture-provider coverage.
- Update any test that asserted the default provider or fixture-data values.
- Frontend: `lib/tracking`-style unit test for `getLeaveSummary`; dashboard test asserting the live value replaces hard-coded `"21"`.
- Full backend suite + `manage.py check`, full frontend suite + `tsc --noEmit -p tsconfig.test.json` + `npm run lint`.

## 4. Verification checklist

- [ ] `LEAVE_RULES_PROVIDER` points at `DatabaseRulesProvider`; validation/submission/snapshot balance now read real `LeaveType`/`LeaveRule`/`GradeEntitlement`/`FinancialYear`/`PublicHoliday`/`EmployeeProfile`.
- [ ] `EmployeeInfo.gender` round-trips through the new profile column; gender eligibility rules fire for maternity/paternity.
- [ ] `get_leave_type_rules` derives units correctly and returns `None` for types without an effective rule.
- [ ] `get_financial_year_for` / `get_public_holidays` use configured rows only; absent config yields `None`/`{}`.
- [ ] `get_available_balance` = resolved entitlement + ledger net, clamped non-negative.
- [ ] `seed_dev_users` idempotent and new-field-complete (gender, eligibility_rules); `seed_approvals_dev` errors clearly without an active FY.
- [ ] `GET /api/v1/leave/me/summary/` returns the contract shape (nulls tolerated); dashboard shows the live Available Balance + profile line.
- [ ] Regression: full backend suite green, frontend suite + tsc + lint clean.
>>>>>>> feature/plans-teams
