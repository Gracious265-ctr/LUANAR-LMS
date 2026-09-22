# Unit 14 — Leave Validation and Submission

read `context/AGENTS.md` before starting.

## 1. Goal

Turn a Unit 13 draft into a **submitted** leave application through a single, backend-authoritative validation pipeline (working days, notice, duration, eligibility, financial year, balance, overlap, documents) that issues a unique reference number such as `LV-2026-27-000123`. The employee sees the calculated result on a review screen, confirms, and lands on a confirmation screen showing that reference number.

Out of scope for this unit: approver assignment, workflow routing, email notifications, approval/rejection/correction, balance deduction, cancellation, resubmission. This unit only leaves clean hook points for them.

---

## 2. Design

### 2.1 Decisions locked in

| # | Decision |
|---|---|
| D1 | Units 2–5 are being built in parallel and are not merged until Unit 20+. Unit 14 depends on a **rules-provider interface** (Section 3.2) with a fixture-backed implementation. Validators never import the other units' models directly. |
| D2 | Notice period and maximum duration each carry a unit: `working_days` or `calendar_days`. Annual leave uses working days; special leave uses whatever its rule says. |
| D3 | Statuses that block an overlapping application: `submitted`, `pending`, `correction_required`, `approved`. Statuses that do not: `draft`, `rejected`, `cancelled`. Overlap is calendar-date based, across all leave types, and an application never overlaps itself. |
| D4 | Balance validation is **strict against the approved-deduction balance** and ignores other pending applications, per the stated rules. Unit 14 does not calculate balances (entitlement, proration, carry-forward); it asks the provider for `get_available_balance`. |
| D5 | Start date must be a future working day. End date may be any date on or after start, provided the range contains at least one working day. |
| D6 | "Today" is evaluated in `Africa/Blantyre` (CAT), never UTC. |
| D7 | Eligibility rule types: `gender`, `min_service`, `grade_range`, `employee_category`. Unknown rule types **fail closed**. |
| D8 | Reference format: `LV-{financial-year-label}-{6-digit sequence}`. The sequence is per financial year, concurrency-safe, never reused, and retained on resubmission. **The financial year used is the one containing the leave start date**, because validation already guarantees it exists. This means the reference year can be later than the submission date (e.g. a June submission for July leave). |
| D9 | Submission sets status to `submitted`, snapshots rules and calculated values, assigns the reference number and writes an audit record. It does not route or notify. A `leave_application_submitted` signal fires on commit for later units. |
| D10 | Two endpoints: a stateless `validate` endpoint for live feedback, and a `submit` endpoint. Both use the same pipeline. The client never sends an employee ID. |
| D11 | Every validation run returns **all** errors at once, each with a machine-readable code and a field mapping. |
| D12 | "Required document" means: when the leave type's `requires_document` is true, at least one finalized supporting document exists on the draft. No per-document-type checking. |
| D13 | A blank reason blocks submission (`REASON_REQUIRED`). This is not in the Unit 14 bullet list but the project overview requires a reason on every application. |
| D14 | Submitting an already-submitted application returns `409 ALREADY_SUBMITTED` with its reference number, so a double-click or reload lands on the confirmation screen instead of erroring. |

### 2.2 Validation pipeline

Validators are small, pure-ish functions run in a fixed order. Each receives a `ValidationContext` and appends `ValidationIssue`s. There are two tiers:

1. **Preconditions** (stop the run if they fail, since nothing else can be evaluated): employee profile found, leave type found and active, `end_date >= start_date`.
2. **Independent checks** (all run and all errors are collected): start-date rules, financial year, notice, duration, eligibility, documents, reason, overlap, balance. A check that needs a value an earlier failure made unavailable (e.g. working days when no dates) is skipped, not errored.

### 2.3 Error codes

| Code | Field | Meaning |
|---|---|---|
| `EMPLOYEE_PROFILE_MISSING` | — | No employee record for the authenticated user |
| `LEAVE_TYPE_UNAVAILABLE` | `leave_type` | Not found, inactive, or not effective on the submission date |
| `END_BEFORE_START` | `end_date` | End date earlier than start date |
| `START_ON_SUBMISSION_DATE` | `start_date` | Start date equals today |
| `START_IN_PAST` | `start_date` | Start date before today |
| `START_NOT_WORKING_DAY` | `start_date` | Weekend or public holiday (detail says which) |
| `NO_WORKING_DAYS` | `end_date` | Range contains zero working days |
| `NO_FINANCIAL_YEAR_CONFIGURED` | `start_date` / `end_date` | A date is not inside any configured financial year |
| `CROSSES_FINANCIAL_YEAR` | `end_date` | Start and end are in different financial years |
| `MIN_NOTICE_NOT_MET` | `start_date` | Notice given is less than required |
| `MAX_DURATION_EXCEEDED` | `end_date` | Duration exceeds the configured maximum |
| `NOT_ELIGIBLE` | `leave_type` | An eligibility rule failed (detail names the rule) |
| `ELIGIBILITY_RULE_UNSUPPORTED` | `leave_type` | Unknown rule type (fail closed) |
| `ELIGIBILITY_DATA_MISSING` | `leave_type` | Rule needs an employee attribute the profile lacks (fail closed) |
| `DOCUMENT_REQUIRED` | `documents` | Leave type requires a document and none is attached |
| `REASON_REQUIRED` | `reason` | Reason is blank |
| `OVERLAPPING_LEAVE` | `start_date` | Overlaps another blocking application (detail lists its reference numbers) |
| `INSUFFICIENT_BALANCE` | `end_date` | Requested working days exceed available balance (detail has both numbers) |
| `APPLICATION_NOT_SUBMITTABLE` | — | Application is not in `draft` status (submit only) |
| `ALREADY_SUBMITTED` | — | Submit on an already-submitted application (returns `409`, includes reference) |

### 2.4 Frontend visual and structural decisions

Follow the existing project design tokens:

- **Colors:** LUANAR blue `#0097F0` for the primary button and links; institutional green `#009119` for the success state; error uses the existing rejected red; the "Submitted" status badge uses the existing pending orange token.
- **Type and icons:** Inter throughout; Lucide React icons only (`AlertCircle`, `CheckCircle2`, `Copy`, `Check`, `Loader2`, `ArrowLeft`, `CalendarDays`, `FileText`).
- **Components:** 21st.dev components first, then Tailwind. Cards use radius-xl, flat subtle shadows, no gradients and no glassmorphism, minimal animation. Both light and dark themes must work using the existing tokens.
- **Flow:** the Unit 13 draft form gains a **Review and submit** action, which navigates to `/leave/applications/[id]/review`. Confirming navigates to `/leave/applications/[id]/submitted`.

**Review screen layout (inside the existing dashboard shell):**

1. Page header: "Review your application" with a back link to the draft.
2. Summary card: leave type, start date, end date, **working days** (large, prominent), calendar days, financial year, reason, attached documents (names only).
3. Balance card (annual-deducting leave types only): available balance, and "Balance if approved" (`available − working days`). Below it, a fixed note: *"Nothing is deducted until your application is finally approved."*
4. Validation panel: when there are errors, a red-bordered alert (`role="alert"`) lists each message, each linking back to the relevant field or step. When valid, a green "All checks passed" line.
5. Footer actions: secondary "Back to edit" and primary **Submit application**. Submit is disabled while validation is loading or errors exist, and shows a `Loader2` spinner while submitting.

**Confirmation screen layout:**

1. Centered card with a green `CheckCircle2` and the heading "Application submitted".
2. The reference number in large monospace type with a **Copy** button (icon swaps to `Check` with "Copied" for 2 seconds).
3. A "Submitted" status badge (pending orange), the submission timestamp and a compact summary (leave type, dates, working days).
4. Text: "Keep this reference number to track your application."
5. Actions: "View my applications" (primary) and "Back to dashboard" (secondary).

**Accessibility:** validation errors are announced through an `aria-live="polite"` region. On a failed submit, focus moves to the error summary. Buttons have visible focus rings. The reference number is selectable text.

---

## 3. Implementation

### 3.1 Backend module layout

```
backend/leave/
├── providers/
│   ├── __init__.py
│   ├── base.py               # dataclasses + RulesProvider Protocol
│   ├── fixture.py            # FixtureRulesProvider (in-memory)
│   └── fixture_data.py       # placeholder data, clearly marked
├── validation/
│   ├── __init__.py
│   ├── types.py              # ValidationContext, ValidationIssue, ValidationResult
│   ├── working_days.py       # calendar helpers
│   ├── pipeline.py           # ordered runner
│   └── validators/
│       ├── preconditions.py
│       ├── start_date.py
│       ├── financial_year.py
│       ├── notice.py
│       ├── duration.py
│       ├── eligibility.py
│       ├── documents.py
│       ├── reason.py
│       ├── overlap.py
│       └── balance.py
├── services/
│   ├── submission.py         # submit_application()
│   ├── references.py         # next_reference()
│   └── workflow_gate.py      # stub, see 3.8
├── signals.py                # leave_application_submitted
├── serializers/validation.py
├── views/validation.py
└── tests/
    ├── test_working_days.py
    ├── test_validators.py
    ├── test_pipeline.py
    ├── test_references.py
    ├── test_submission.py
    └── test_api.py
```

Settings (`config/settings`):

```python
TIME_ZONE = "Africa/Blantyre"
USE_TZ = True
LEAVE_RULES_PROVIDER = "leave.providers.fixture.FixtureRulesProvider"
LEAVE_BLOCKING_STATUSES = ["submitted", "pending", "correction_required", "approved"]
```

`get_provider()` imports the dotted path from `LEAVE_RULES_PROVIDER`. `get_today()` returns `timezone.localdate()` and can be patched in tests through a single function, so no test ever depends on the real clock.

### 3.2 Rules provider interface (`providers/base.py`)

Frozen dataclasses:

```python
@dataclass(frozen=True)
class EmployeeInfo:
    id: int
    user_id: int
    grade: str                     # letter, "A".."U"
    appointment_date: date
    category: str | None
    department_id: int | None
    gender: str | None             # optional; None means not recorded

@dataclass(frozen=True)
class EligibilityRule:
    type: str                      # gender | min_service | grade_range | employee_category
    params: dict                   # e.g. {"allowed": ["F"]}, {"months": 12}, {"min": "A", "max": "G"}

@dataclass(frozen=True)
class LeaveTypeRules:
    id: int
    code: str
    name: str
    is_active: bool
    deducts_annual_balance: bool
    max_duration: int | None
    max_duration_unit: Literal["working_days", "calendar_days"]
    min_notice: int                # 0 allowed
    min_notice_unit: Literal["working_days", "calendar_days"]
    requires_document: bool
    eligibility: tuple[EligibilityRule, ...]
    effective_from: date

@dataclass(frozen=True)
class FinancialYear:
    label: str                     # e.g. "2026-27"
    start: date
    end: date                      # inclusive
```

Protocol methods:

| Method | Returns |
|---|---|
| `get_employee_for_user(user)` | `EmployeeInfo` or `None` |
| `get_leave_type_rules(leave_type_id, as_of: date)` | `LeaveTypeRules` or `None` (inactive or not yet effective returns `None`) |
| `get_financial_year_for(d: date)` | `FinancialYear` or `None` |
| `get_public_holidays(start: date, end: date)` | `dict[date, str]` (date to holiday name) |
| `get_available_balance(employee_id, financial_year_label)` | `Decimal` |

**Unit 20 handoff:** add `docs/leave-rules-provider-contract.md` mapping each method to the colleague's real models, so the swap is one new class plus one settings change.

`fixture_data.py` is **placeholder data only**, with a header comment saying so. All tests inject explicit data rather than depending on it:

- Financial year `2026-27`: 2026-07-01 to 2027-06-30 (placeholder, not confirmed as LUANAR's actual year).
- Annual entitlement by grade, from the project overview: A–C 21, D–G 24, H–U 30. Fixture balance = entitlement, with no deductions.
- Leave types:
  - Annual (deducts, working days, notice 5 working days, no max).
  - Maternity (no deduct, max 90 `calendar_days`, gender rule `F`, requires document).
  - Paternity (no deduct, max 10 `calendar_days`, gender rule `M`).
  - Compassionate (no deduct, max 5 `working_days`, notice 0).
  - Notice, max and document values other than maternity 90 and paternity 10 are invented placeholders.
- A few arbitrary public holidays.
- Employees are resolved by username for the seeded dev users; unknown usernames return `None`.

### 3.3 Working-day and calendar helpers (`validation/working_days.py`)

```python
def is_weekend(d: date) -> bool                          # Saturday or Sunday
def is_working_day(d: date, holidays: set[date]) -> bool # not weekend and not holiday
def count_working_days(start: date, end: date, holidays: set[date]) -> int   # inclusive both ends; 0 if end < start
def count_calendar_days(start: date, end: date) -> int   # (end - start).days + 1
def working_days_elapsed(today: date, start: date, holidays: set[date]) -> int
    # working days in [today + 1, start], inclusive of start
```

Rules:

- Ranges are inclusive on both ends.
- Weekends are Saturday and Sunday. Holidays come only from the provider. There is no substitute-holiday logic in this unit, since that is Unit 5 data.
- Iterate day by day. Ranges are bounded by the financial year (at most 366 days), so this is fine.
- Fetch holidays once per run: `get_public_holidays(min(today + 1, start), end)`.

Worked examples (today = Monday 2026-09-21):

| Range | Working days | Calendar days |
|---|---|---|
| Mon 2026-09-28 to Fri 2026-10-02 | 5 | 5 |
| Same, with Wed 2026-09-30 a holiday | 4 | 5 |
| Fri 2026-10-02 to Tue 2026-10-06 | 3 | 5 |
| Sat 2026-10-03 to Sun 2026-10-04 | 0 | 2 |

### 3.4 Validators (`validation/validators/`)

Each validator has a docstring stating its rule and codes.

- **preconditions.** Employee missing gives `EMPLOYEE_PROFILE_MISSING`. Leave type via `get_leave_type_rules(id, today)` returning `None` gives `LEAVE_TYPE_UNAVAILABLE`. End before start gives `END_BEFORE_START`. Any failure here stops the run.
- **start_date.** In order: `start == today` gives `START_ON_SUBMISSION_DATE`; `start < today` gives `START_IN_PAST`; otherwise, if the start is a weekend or holiday, gives `START_NOT_WORKING_DAY` (detail: `"weekend"` or the holiday name). Then, if `count_working_days == 0`, gives `NO_WORKING_DAYS`.
- **financial_year.** Look up the financial year for both start and end. If either is `None`, give `NO_FINANCIAL_YEAR_CONFIGURED`. If both exist with different labels, give `CROSSES_FINANCIAL_YEAR` (detail names both years). The resolved financial year is stored on the context for the balance check and the reference number.
- **notice.** `min_notice_unit == "calendar_days"`: notice given is `(start - today).days`. `"working_days"`: notice given is `working_days_elapsed(today, start, holidays)`. Fail with `MIN_NOTICE_NOT_MET` if notice given is less than `min_notice`. The detail includes required, given and the earliest valid start date. Example, with today Monday 2026-09-21 and 5 working days required: start Fri 2026-09-25 gives 4 and fails; Mon 2026-09-28 gives 5 and passes.
- **duration.** If `max_duration` is set, measure in `max_duration_unit`. Fail with `MAX_DURATION_EXCEEDED` if measured value is greater than `max_duration` (detail has both).
- **eligibility.** Evaluate every rule in the leave type's eligibility list:
  - `gender`: employee gender must be in `params.allowed`. If gender is `None`, give `ELIGIBILITY_DATA_MISSING`.
  - `min_service`: whole months from `appointment_date` to the leave **start date** must be at least `params.months`.
  - `grade_range`: employee grade is compared by letter order against `params.min` and `params.max`, inclusive.
  - `employee_category`: employee category must be in `params.allowed`. If category is `None`, give `ELIGIBILITY_DATA_MISSING`.
  - Any other type gives `ELIGIBILITY_RULE_UNSUPPORTED` (fail closed).
  - A failing rule gives `NOT_ELIGIBLE` with the rule type in the detail.
- **documents.** Runs only when a draft/application ID is present. If `requires_document` is true and the count of finalized supporting documents is zero, give `DOCUMENT_REQUIRED`. Use a small helper `count_supporting_documents(application)` wrapping Unit 13's document relation, so a model rename touches one function.
- **reason.** Runs only with a draft ID. A blank or whitespace-only reason gives `REASON_REQUIRED`.
- **overlap.** Query the employee's other applications with status in `LEAVE_BLOCKING_STATUSES` where `existing.start <= new.end AND existing.end >= new.start`, excluding the current application ID. Results are always scoped to the same employee. Give `OVERLAPPING_LEAVE` with the conflicting reference numbers (all belong to the same employee, so nothing leaks).
- **balance.** Runs only when `deducts_annual_balance` is true and a financial year resolved. Call `get_available_balance(employee.id, fy.label)`. Fail with `INSUFFICIENT_BALANCE` if `working_days > available`. Pending, rejected and correction-required applications are deliberately not consulted (D4). This validator never writes anything.

### 3.5 Pipeline result (`validation/types.py`, `pipeline.py`)

`run_validation(*, user, leave_type_id, start_date, end_date, application=None, today=None) -> ValidationResult`

```python
@dataclass
class ValidationResult:
    valid: bool
    errors: list[ValidationIssue]      # code, field, message, detail(dict)
    warnings: list[ValidationIssue]    # reserved, always [] in Unit 14
    skipped_checks: list[str]          # e.g. ["documents", "reason"] when no draft ID
    working_days: int | None
    calendar_days: int | None
    financial_year: str | None
    available_balance: Decimal | None
    balance_after_if_approved: Decimal | None
    context: ValidationContext         # internal: rules, holidays; used for the snapshot
```

`message` strings are human-readable and come from the backend (the frontend renders them as-is). `detail` carries structured values (required, given, available and so on).

### 3.6 Model changes (`leave` app, one migration)

On `LeaveApplication` (built in Unit 13), add:

| Field | Type | Notes |
|---|---|---|
| `reference_number` | `CharField(max_length=32, unique=True, null=True, blank=True)` | `NULL` until submission; never regenerated once set |
| `submitted_at` | `DateTimeField(null=True)` | Set once at first submission |
| `working_days` | `PositiveSmallIntegerField(null=True)` | Authoritative, server-calculated |
| `calendar_days` | `PositiveSmallIntegerField(null=True)` | |
| `financial_year_label` | `CharField(max_length=16, null=True)` | |
| `rules_snapshot` | `JSONField(null=True)` | See below |

Add `submitted` to the status choices if Unit 13 does not already define it.

New model `ReferenceSequence`: `financial_year_label` (unique), `last_value` (`PositiveIntegerField`, default 0).

`rules_snapshot` contents (historical integrity, invariant 12.5): the leave type's rules exactly as evaluated (all `LeaveTypeRules` fields), the financial-year label and dates, the list of public-holiday dates used in the range, `working_days`, `calendar_days`, `available_balance` at submission, the eligibility outcome, and `validator_version` (a string constant, starting at `"1"`). Later configuration changes never alter this record.

### 3.7 Reference numbers (`services/references.py`)

```python
def next_reference(financial_year_label: str) -> str:
    # Must be called inside transaction.atomic().
    seq, _ = ReferenceSequence.objects.select_for_update().get_or_create(
        financial_year_label=financial_year_label, defaults={"last_value": 0})
    seq.last_value += 1
    seq.save(update_fields=["last_value"])
    return f"LV-{financial_year_label}-{seq.last_value:06d}"
```

- Format example: `LV-2026-27-000123`.
- Never reuse a number, even if the surrounding transaction later rolls back (a rollback also rolls back the increment, so no gap-based collision is possible). The unique constraint on `reference_number` is the final safety net.
- `get_or_create` race on the very first submission of a financial year: catch `IntegrityError` and retry once inside the same function.

### 3.8 Submission service (`services/submission.py`)

`submit_application(*, user, application_id) -> LeaveApplication`. Everything below runs in one `transaction.atomic()`:

1. Resolve the employee via the provider from the authenticated user. Never accept an employee ID from the client.
2. Load the application with `select_for_update()`, filtered to that employee. Not found (including another employee's application) raises `NotFound` (404), never 403, so existence is not revealed.
3. If status is `submitted` (or later), raise `ALREADY_SUBMITTED` (409) with the existing reference. If status is not `draft`, raise `APPLICATION_NOT_SUBMITTABLE`.
4. Take a per-employee Postgres advisory lock so two simultaneous submissions cannot both pass the overlap check: `SELECT pg_advisory_xact_lock(hashtext('leave_submit'), %s)` with the employee ID. It releases automatically at transaction end.
5. Run `run_validation(...)` with the draft attached. If `valid` is false, raise `ValidationFailed(result.errors)` (mapped to 422). Nothing is written.
6. `workflow_gate.check_workflow_ready(application)`: a stub that returns success in this unit, with a docstring and `TODO(unit-workflow)` marking that invariant 12.7 (valid configured workflow before submission) must be enforced here once workflows exist.
7. Persist: `working_days`, `calendar_days`, `financial_year_label`, `rules_snapshot`, `submitted_at = timezone.now()`, `status = "submitted"`, and `reference_number = next_reference(fy_label)` only if it is still `NULL`.
8. Write an audit record through the existing audit app (actor = user, action = `leave_application.submitted`, target = application, previous state = `draft`, new state = `submitted`, metadata = reference number and working days). If the audit app has no such function yet, add a thin `record_event(...)` with that shape.
9. `transaction.on_commit(lambda: leave_application_submitted.send(sender=LeaveApplication, application=app))`. No receivers exist in this unit.

Submission must not touch any balance data. There are no ledger writes and no changes to any balance field.

### 3.9 API (`views/validation.py`, `serializers/validation.py`)

Both endpoints require authentication. Follow the shared error envelope from Unit 1; the `errors` array below is the payload of that envelope.

**`POST /api/leave/validate/`** (stateless, persists nothing, always `200`):

```json
// request
{ "leave_type_id": 3, "start_date": "2026-09-28", "end_date": "2026-10-02", "draft_id": 41 }
```

`draft_id` is optional. When given, the draft must belong to the caller (else `404`), overlap excludes that draft, and the reason and document checks run. When omitted, those two checks are skipped and listed in `skipped_checks`. Any `employee_id` in the body is ignored.

```json
// response
{
  "valid": false,
  "working_days": 5,
  "calendar_days": 5,
  "financial_year": "2026-27",
  "available_balance": "24.0",
  "balance_after_if_approved": "19.0",
  "errors": [
    { "code": "MIN_NOTICE_NOT_MET", "field": "start_date",
      "message": "This leave type needs 5 working days' notice. The earliest start date is 28 Sep 2026.",
      "detail": { "required": 5, "given": 4, "unit": "working_days", "earliest_start": "2026-09-28" } }
  ],
  "warnings": [],
  "skipped_checks": []
}
```

**`POST /api/leave/applications/{id}/submit/`** (no body):

- `200`: `{ "id": 41, "reference_number": "LV-2026-27-000123", "status": "submitted", "submitted_at": "2026-09-21T09:14:03+02:00", "working_days": 5, "calendar_days": 5, "leave_type": {...}, "start_date": "...", "end_date": "..." }`
- `422 VALIDATION_FAILED` with the same `errors` array as above. Nothing is persisted.
- `409 ALREADY_SUBMITTED` with `reference_number`.
- `409 APPLICATION_NOT_SUBMITTABLE`.
- `404` for a missing draft or another employee's draft.

Also extend the Unit 13 application detail serializer to include `reference_number`, `submitted_at`, `working_days`, `calendar_days` and `financial_year_label`.

### 3.10 Frontend

Files (adjust paths to the existing structure):

```
frontend/
├── lib/
│   ├── api/leave-validation.ts        # validateLeave(), submitApplication()
│   └── leave/validation-types.ts      # ValidationResult, ValidationIssue, error code union
├── hooks/use-leave-validation.ts
├── components/leave/
│   ├── leave-review-summary.tsx
│   ├── balance-card.tsx
│   ├── validation-panel.tsx
│   └── submission-confirmation.tsx
└── app/leave/applications/[id]/
    ├── review/page.tsx
    └── submitted/page.tsx
```

- **Service layer.** `validateLeave` and `submitApplication` call the real backend endpoints (no mocks; the backend fixture provider makes them work standalone). `submitApplication` never sends an employee ID. The server's `message` is displayed as-is, and the frontend never recomputes working days or balances.
- **`useLeaveValidation`.** Debounces 400 ms on leave type or date change, cancels stale requests (`AbortController`), and exposes `{ result, isLoading, error }`. On the Unit 13 form it powers live inline feedback (working days, first blocking error under the relevant field). On the review page it runs once on mount with `draft_id`.
- **Review page.** Loads the draft (Unit 13 GET) and validation together. Renders the layout in Section 2.4. Submit calls `submitApplication`, guarded by an `isSubmitting` ref so a double-click sends exactly one request.
- **Submit outcomes.** `200` navigates to `/leave/applications/[id]/submitted`. `422` replaces the validation panel content, moves focus to it, and keeps the user on the page. `409 ALREADY_SUBMITTED` navigates to the submitted page. Network or other errors show a dismissible inline alert with a retry action.
- **Submitted page.** Fetches the application detail. If `reference_number` is `null` or the status is not `submitted`, redirect to the review page. It renders the confirmation layout from Section 2.4 and reloads safely, since it reads everything from the server.
- **Types.** The error code union type mirrors the table in Section 2.3.
- **Docs.** Add a short `docs/leave-validation.md` describing the pipeline order and error codes for the other developer.

### 3.11 Tests

Backend (Django `TestCase`; `TransactionTestCase` for the concurrency test). All tests inject a stub provider with explicit data and a fixed `today = date(2026, 9, 21)` (a Monday).

- **Working days:** the four worked examples in 3.3, holiday on a weekend, range entirely on a weekend, single-day range, `end < start`.
- **Each validator**, at boundary and failing values:
  - start today, yesterday, tomorrow;
  - start Saturday, start on a holiday;
  - notice with working days vs calendar days (Friday 4 vs Monday 5 case);
  - duration exactly at the max and max plus 1;
  - each of the four eligibility types, plus unsupported type and missing gender;
  - required document present and absent;
  - blank reason;
  - overlap with each status (blocking and non-blocking), partial overlap, adjacent ranges (end on the day before start does not overlap), and self-exclusion;
  - balance exactly equal to available, balance plus 1, and non-deducting leave type ignoring balance.
- **Financial year:** range inside one year; crossing (Mon 2027-06-28 to Fri 2027-07-02); date outside any configured year.
- **Pipeline:** multiple errors collected in one run; precondition failure short-circuits; `skipped_checks` without a draft ID.
- **References:** format; sequential numbers; independent sequence per financial year; two threads submitting concurrently yield distinct numbers; unique constraint holds; a second submit does not change an existing reference.
- **Submission service:** success persists all fields and the snapshot; failure persists nothing; status guard; another employee's draft returns 404; overlap race (two concurrent submits for overlapping ranges: exactly one succeeds); `on_commit` signal fires once; audit record written; **no balance data changed** for annual and non-annual leave.
- **Historical integrity:** change the provider's leave-type rules after submission; the stored snapshot and `working_days` are unchanged.
- **API:** unauthenticated `401`; extra `employee_id` in the body ignored; `422` shape; `409` shape; validate endpoint writes no rows.

Frontend (Vitest and React Testing Library):

- Review page renders working days, balance card and "nothing is deducted" note for annual leave, and no balance card for non-deducting leave.
- Errors disable Submit and link to fields; the live region announces them.
- A valid draft plus click calls submit once (double-click test) and navigates to the submitted page.
- `422` updates the panel and moves focus; `409` navigates to the submitted page.
- Confirmation page shows the reference, Copy writes to the clipboard and shows the "Copied" state, and it redirects when no reference exists.
- The debounce and abort behaviour of `useLeaveValidation`.

---

## 4. Dependencies

No new packages are required.

- **Backend (already present):** Django, Django REST Framework, PostgreSQL driver (advisory locks and `select_for_update` need Postgres, which is already the project database). Managed with `uv`; nothing to add.
- **Frontend (already present):** Next.js, Tailwind CSS, `lucide-react`, 21st.dev components, Vitest, React Testing Library.
- **Not adding:** a date library (dates come from the server; use `Intl.DateTimeFormat` for display), and no client-side validation library.

Settings to add: `TIME_ZONE`, `LEAVE_RULES_PROVIDER`, `LEAVE_BLOCKING_STATUSES` (Section 3.1). One migration for the model changes in Section 3.6.

---

## 5. Verification checklist

**Working days and dates**
- [ ] Mon 2026-09-28 to Fri 2026-10-02 returns 5 working days.
- [ ] The same range with Wed 2026-09-30 as a holiday returns 4.
- [ ] Fri 2026-10-02 to Tue 2026-10-06 returns 3 working days and 5 calendar days.
- [ ] A range entirely on a weekend or holidays returns `NO_WORKING_DAYS`.
- [ ] Start date equal to today returns `START_ON_SUBMISSION_DATE`; a past date returns `START_IN_PAST`.
- [ ] A Saturday or holiday start returns `START_NOT_WORKING_DAY`.
- [ ] "Today" follows `Africa/Blantyre`, not UTC.

**Rules**
- [ ] Notice: 5 working days required, start Fri 2026-09-25 fails and Mon 2026-09-28 passes.
- [ ] Calendar-day notice and calendar-day maximum duration units behave correctly.
- [ ] Maximum duration passes exactly at the limit and fails at limit plus 1.
- [ ] Eligibility (gender, minimum service, grade range, category) passes and fails correctly; unknown rule types and missing employee data fail closed.
- [ ] A range crossing 30 Jun to 1 Jul (Mon 2027-06-28 to Fri 2027-07-02) returns `CROSSES_FINANCIAL_YEAR`; a date outside every configured year returns `NO_FINANCIAL_YEAR_CONFIGURED`.
- [ ] Required documents and a non-blank reason are enforced on submit.
- [ ] Overlap blocks on `submitted`, `pending`, `correction_required` and `approved`; it ignores `draft`, `rejected` and `cancelled`; adjacent ranges do not overlap; an application does not overlap itself.
- [ ] Annual leave with working days greater than available balance returns `INSUFFICIENT_BALANCE`; working days equal to balance passes.
- [ ] Non-annual leave types (for example maternity and paternity) skip the balance check and never affect annual balance.
- [ ] Several failing rules are all returned in a single response with codes and field mappings.

**Submission**
- [ ] A valid draft submits and returns a reference like `LV-2026-27-000123`.
- [ ] Status becomes `submitted`; `submitted_at`, `working_days`, `calendar_days`, `financial_year_label` and `rules_snapshot` are stored.
- [ ] An invalid draft returns `422` and persists nothing (no reference consumed, status still `draft`).
- [ ] Two consecutive submissions get consecutive, distinct reference numbers; two concurrent submissions never share one.
- [ ] Sequences are independent per financial year.
- [ ] Resubmitting or re-saving never changes an existing reference number.
- [ ] Submitting twice returns `409 ALREADY_SUBMITTED` with the existing reference.
- [ ] Two concurrent overlapping submissions for the same employee: exactly one succeeds.
- [ ] Submitting does not deduct, reserve or modify any balance (annual or non-annual).
- [ ] Changing leave-type rules after submission does not change the stored snapshot.
- [ ] An audit record exists with actor, action, timestamp, previous state and new state.
- [ ] The `leave_application_submitted` signal fires once, after commit.

**Security and architecture invariants**
- [ ] The employee is always derived from the authenticated user; a body `employee_id` is ignored (12.1, 12.2).
- [ ] Another employee's draft returns `404` on both endpoints (12.6).
- [ ] The frontend never computes working days, balance or eligibility; it only renders server results (12.1).
- [ ] The validate endpoint writes no database rows.
- [ ] Validators depend only on the provider interface; no imports of other units' models (D1).
- [ ] The workflow gate stub exists, is documented, and references invariant 12.7.

**Frontend**
- [ ] Review page shows working days, calendar days, financial year, reason, documents and (annual only) balance and "Balance if approved" with the not-deducted note.
- [ ] Submit is disabled while loading or while errors exist; a double-click sends one request.
- [ ] Errors are announced via the live region, and focus moves to the error summary after a failed submit.
- [ ] Success lands on the confirmation screen with the reference in large monospace, working Copy button and "Submitted" badge; reloading it still works; it redirects if the application is not submitted.
- [ ] Light and dark themes both render correctly with the existing tokens, using Lucide icons only, with no gradients.
- [ ] Vitest suites and Django tests all pass.

**Manual end-to-end**
- [ ] Log in as a seeded employee, create a draft (annual leave, valid dates, reason), open Review, submit, and see the reference number on the confirmation screen.
- [ ] Repeat with a start date inside the notice period and confirm submission is blocked with the correct message.
- [ ] Repeat with dates overlapping the application just submitted and confirm `OVERLAPPING_LEAVE` lists its reference number.
