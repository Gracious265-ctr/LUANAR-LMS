# Unit 23 — Final Approval, Balance, and Document Generation

> **DETAILED OUTLINE — expand to a full spec when Wave 2 starts.** Read `context/AGENTS.md` before implementation. This unit connects an `application_finalised` approval event to (a) the annual-leave balance deduction, (b) generation of the official approved leave document as **PDF** stored through the Unit 19 storage abstraction, and (c) authorized access to that document.
> Depends on Units 10, 14, 16, 19, 20, 21, 22.

## Goal

Make a fully approved leave application deduct the correct days from the
employee's annual balance (via the existing ledger) and produce an official
approved leave document (PDF) rendered from the `LeaveDocumentTemplate` config,
stored through the Unit 19 storage backend and served to authorized users.

## Design (to define in full spec)

- **Trigger:** subscribe to `emit_approval_event` `kind == "application_finalised"` (same dispatch seam Unit 22 hooks). One subscriber performs the balance deduction + document generation inside one transaction; a failure must not leave the application half-processed.
- **Balance deduction:** reuse the `LeaveBalanceTransaction` ledger + `FixtureBalanceProvider`/`DatabaseRulesProvider` balance logic (Unit 20 `_ledger_net_used` = `Σ deductions − Σ restorations`). Deduct based on the **actual** `LeaveApplication.working_days` (that is what was validated/approved), only for leave types that `deducts_annual_balance` (from the `rules_snapshot`, invariant 12.5). Special-leave (non-deducting) behavior = no ledger write, per snapshot flag. Use the employee+financial-year the application was approved in. Reuse `leave/cancellations/balance.py` restore logic as the inverse (its `get_ledger_deduction` guidance matters — deduct only the exact approved days, keep Σ consistent).
- **Document generation:** new service in `documents/` (e.g. `documents/generator.py`) reading the single `LeaveDocumentTemplate` (`documents/services.py::get_template`), populating its `fields` with values from the approved `LeaveApplication` (reference, employee name/grade/designation/department, leave type, dates, working days, reason) and its `signature_areas`, rendering **PDF only** (ReportLab — PDF is the V1 commitment; DOCX explicitly out of scope). Store the PDF bytes (with the source employee_name/date/title header) through `leave.storage.get_storage_backend()` (Unit 19 `DevelopmentStorageBackend` local-disk default; Supabase backend when configured).
- **Persistence:** a new model in `leave` or `documents` linking the generated document to the application (one per approved application, replaceable on subsequent finalised events — e.g. resubmission/re-approval overrides it). Alternatively store a `SupportingDocument`-style row reusing the Unit 19 content endpoint; decide in the full spec.
- **Authorized access:** authenticated streaming endpoint mirroring the Unit 19 `content/` pattern, restricted to the employee + workflow members + HR (reuse `get_view_access`/role checks from `workflows/policies.py`). Store/stream the PDF, never expose storage URLs to the client.
- **Balance read surfaces:** the employee dashboard `my/overview` balance must reflect the deduction (it already reads the ledger via `DatabaseRulesProvider.get_leave_balance`), and the approvals review payload's balance block for the approved application must stay honest.

## Implementation (to expand)

1. `documents/generator.py` — PDF renderer using `LeaveDocumentTemplate` + approved `LeaveApplication`; `generate_approved_document(application) -> bytes`.
2. New storage-backed record model + migration; ORM row for the generated PDF (kept under `documents` app).
3. Approval-finalised subscriber (in `workflows/events.py` or a small `balance_document.py` service) wiring deduction (`create_ledger_deduction`) + generation + persistence in one transaction after commit.
4. Streaming content endpoint + permission wiring (owner/approver/HR) and a Next proxy route if the frontend needs it.
5. Tests (full spec): final approval deducts `working_days` for deducting types; non-deducting (special) leave writes no ledger row; balance stays consistent with `Σ deductions − Σ restorations`; resubmission/re-approval overrides the prior document; unauthorized access 404/403; PDF is valid (ReportLab bytes, magic-number check `%PDF`).
6. Frontend (optional): a "view approved document" affordance on the tracking/review page — decide in full spec.

## Dependencies

- **New packages:** `reportlab` (just-in-time rule permits). `python-docx` explicitly **not** required for V1.
- Existing: `documents` app (Unit 10), ledger + `FixtureBalanceProvider` (Unit 18), storage abstraction (Unit 19), `DatabaseRulesProvider` (Unit 20), workflow routing (Unit 21), notification seam (Unit 22).

## Verification checklist (to expand)

- After final approve: `LeaveBalanceTransaction` has a `DEDUCTION` of exactly `working_days` for deducting types; dashboard balance drops accordingly; `get_leave_balance`/`get_available_balance` reflect it.
- PDF generated, stored via storage backend (file exists under `storage/` in dev), served to the employee + approvers + HR, denied to others.
- Special-leave types create no deduction.
- Full backend `manage.py test` + frontend suites green; `tsc`/`eslint`/`build` clean.