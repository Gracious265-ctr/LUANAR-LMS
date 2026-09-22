# Leave Validation Pipeline

Backend-authoritative validation for leave applications (Unit 14). The frontend
*never* recomputes working days, balances, or eligibility — it renders whatever
this pipeline returns.

## Entry points

- `POST /leave/validate/` — `leave.views.validation.LeaveValidateView`. Runs the
  pipeline for an authenticated user. Accepts `leave_type_id`, `start_date`,
  `end_date`, and optionally `draft_id` (the draft is needed for the overlap,
  document and reason checks).
- `POST /leave-applications/<uuid>/submit/` — runs the pipeline against the
  stored draft, then records the submission, issues a reference number and
  writes an `AuditEntry` (`record_audit`, action `submitted`).

Both live behind JWT auth. The response shape is

```json
{
  "valid": true,
  "errors": [
    { "code": "MIN_NOTICE_NOT_MET", "field": "start_date", "message": "…", "detail": {} }
  ],
  "warnings": [],
  "skipped_checks": [],
  "working_days": 5,
  "calendar_days": 5,
  "financial_year": "2026-27",
  "available_balance": "24.00",
  "balance_after_if_approved": "19.00"
}
```

## Pipeline order

`leave.validation.pipeline.run_validation` runs checks in this order:

1. **Preconditions** (all-or-nothing): stop the run if any holds. Errors here are
   emitted and every later check is skipped.
   - `EMPLOYEE_PROFILE_MISSING` — no employee profile for the user, or a disabled
     status (`LEAVE_BLOCKING_STATUSES`) blocks leave.
   - `LEAVE_TYPE_UNAVAILABLE` — missing, inactive or not-yet-effective leave type.
   - `END_BEFORE_START` — incomplete dates or end before start.
2. `start_date` — `START_IN_PAST`, `START_ON_SUBMISSION_DATE`,
   `START_NOT_WORKING_DAY`, and (via the working-days engine) `NO_WORKING_DAYS`.
3. `financial_year` — `NO_FINANCIAL_YEAR_CONFIGURED`,
   `CROSSES_FINANCIAL_YEAR`.
4. `notice` — `MIN_NOTICE_NOT_MET` (holidays inside the notice window extend it;
   weekends are excluded per the unit).
5. `duration` — `MAX_DURATION_EXCEEDED`.
6. `eligibility` — `NOT_ELIGIBLE`, `ELIGIBILITY_RULE_UNSUPPORTED`,
   `ELIGIBILITY_DATA_MISSING`.
7. `documents` — `DOCUMENT_REQUIRED`.
8. `reason` — `REASON_REQUIRED`.
9. `overlap` — `OVERLAPPING_LEAVE` (only when a `draft_id` is supplied).
10. `balance` — `INSUFFICIENT_BALANCE` (only for leave types that deduct the
    annual balance).

`valid` is `false` when any error exists. Checks that could not be evaluated
(a raw value was unavailable, the submission gate blocked the run, or no draft
was supplied for the draft-only checks) are listed in `skipped_checks`, not
errored — so calling the endpoint from the Unit 13 form with just dates yields a
useful result without a draft.

## Error codes (`ValidationIssue.code`)

| Code | Check |
| --- | --- |
| `EMPLOYEE_PROFILE_MISSING` | preconditions |
| `LEAVE_TYPE_UNAVAILABLE` | preconditions |
| `END_BEFORE_START` | preconditions |
| `START_IN_PAST` | start_date |
| `START_ON_SUBMISSION_DATE` | start_date |
| `START_NOT_WORKING_DAY` | start_date |
| `NO_WORKING_DAYS` | start_date |
| `NO_FINANCIAL_YEAR_CONFIGURED` | financial_year |
| `CROSSES_FINANCIAL_YEAR` | financial_year |
| `MIN_NOTICE_NOT_MET` | notice |
| `MAX_DURATION_EXCEEDED` | duration |
| `NOT_ELIGIBLE` | eligibility |
| `ELIGIBILITY_RULE_UNSUPPORTED` | eligibility |
| `ELIGIBILITY_DATA_MISSING` | eligibility |
| `DOCUMENT_REQUIRED` | documents |
| `REASON_REQUIRED` | reason |
| `OVERLAPPING_LEAVE` | overlap |
| `INSUFFICIENT_BALANCE` | balance |

Submission-only codes (not produced by the pipeline itself):
`ALREADY_SUBMITTED` (409) and `APPLICATION_NOT_SUBMITTABLE` (409).

## Working days

`leave.validation.working_days` counts Mon–Fri, excluding public holidays. A
holiday on a weekend day is *not* moved and simply has no effect; a range that
lands entirely on a weekend yields `NO_WORKING_DAYS`.

## Tests

`leave/tests/` — working days, each validator, the pipeline, reference
generation, submission and the API surface all use a stub provider with explicit
data and a fixed "today" of 2026-09-21 (a Monday). See
`tests/stubs.py` (`StubRulesProvider`, `StubProviderMixin`).