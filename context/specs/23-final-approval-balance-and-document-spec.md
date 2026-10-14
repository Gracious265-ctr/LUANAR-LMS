# Unit 23 — Final Approval, Balance, and Document Generation

read `context/AGENTS.md` before starting. Depends on the finalisation spine +
approval events (Units 16/17/18/21), the balance ledger (Units 18/20), the
leave-document template singleton + field catalog (Units 10/11), Supabase
storage + signed URLs (Unit 13/19 storage seam), and the HR/approver/employee
role vocabulary (Units 4, 14–17, 21). Build-plan §7 Unit 23
(final-approval cascade → balance update → approved document).

## 1. Goal

Close the submission-to-outcome loop. When the **final** approval of an
application succeeds, the system — inside the same committed transaction, and
idempotently:

1. **Updates the annual-leave balance** — writes exactly one append-only
   `DEDUCTION` ledger row for the application's calculated working days in the
   application's financial year, but **only** for leave types that consume
   annual entitlement (decided from the immutable `rules_snapshot`, never from
   the current `LeaveRule`). Special/allocated leave writes **no** ledger row.
2. **Records the outcome** — an audit entry for the finalisation, and (on a
   separate background path) entries for document generated / failed. No new
   tracking event type is added (the vocabulary is pinned in Unit 21 D11).
3. **Generates the approved leave document** — populates the official LUANAR
   template with the **real** approved-application fields (reference, employee,
   grade, designation, department, leave type, dates, working days, reason,
   approved-on, remaining balance) — never the HR-preview `sample` values.
4. **Renders it to PDF** (ReportLab) and stores it through the existing
   Supabase storage seam under a distinct `approved/` prefix.
5. **Exposes it** via short-lived signed URL, read-only, to the approved
   employee, to HR, and to assigned approvers who pass Unit 16
   `get_view_access`.

The approved application row is the single authoritative source for every field
on the approved document; the catalog `sample` values remain HR-preview-only.

## 2. What it builds

- **Finalisation service in the existing `leave/services/finalise.py`** (no new
  `leave/balance/` package): the idempotent annual deduction, called by
  `workflows/services.py::decide()` inside its `transaction.atomic()`. Today
  that file is a non-functional forward-draft — it calls non-existent APIs
  (`LeaveBalanceTransaction.objects.create_ledger_row`, a non-existent
  `submission_cycle` column, `application.leave_type_consumes_annual_entitlement()`,
  `application.is_finalised`, `workflows.events._consumers`) and nothing wires
  it. Unit 23 replaces it with a working implementation.
- **An idempotency migration**: add a partial unique constraint
  `(application)` where `type = 'deduction'` on `LeaveBalanceTransaction`
  (not present today; the only existing ledger constraint is
  `one_restoration_per_cancellation`).
- **`documents/render.py` (or an extension of `documents/services.py`)**:
  template population from a real approved `LeaveApplication`, ReportLab PDF
  rendering, and storage upload through the Unit 19/13 storage seam.
- **`documents.storage` helper** (extension of `leave/services/storage.py`):
  PDF upload under a distinct prefix + signed-URL read (`SUPABASE_SIGNED_URL_EXPIRY`).
- **A `documents.ApprovedLeaveDocument` model**: `application` (unique
  OneToOne), `status` (`pending | ready | failed`), `file_path`,
  `generated_at`, sanitized `error`, timestamps.
- **A Django-Q2 task** for PDF render + upload, enqueued via
  `transaction.on_commit`; idempotent and retry-safe.
- **Read-only endpoints**: owner-scoped employee document read, HR document
  read, and approver document read (assigned approvers through Unit 16
  `get_view_access`). No create/update/delete.
- **Wiring**: `workflows/events.py::APPLICATION_FINALISED` — the render enqueue
  hooks there on commit; the balance deduction call is made directly by the
  decision service inside `decide()`'s transaction (it must not be deferred to
  a background job — the deduction is part of the approval's atomic state).
- **Minimal frontend**: an "Approved leave document" card with a download
  button on `/applications/[id]` when status is `approved` (states
  pending / ready / failed), and the same on the HR finalized-leave detail.
  A Next.js proxy route for the download URL following
  `app/api/_lib/api-fetch.ts`.

## 3. Decisions

| # | Decision |
|---|---|
| D1 | **Annual deduction inside the final-approval transaction.** `decide()` calls a finalisation service (in the existing `leave/services/finalise.py`, no new package) inside the same `transaction.atomic()` as the final approve. It writes exactly one `DEDUCTION` `LeaveBalanceTransaction` for `application.working_days` in `application.financial_year_label`. Whether to deduct is decided from `application.rules_snapshot` — `rules_snapshot["leave_type"]["deducts_annual_balance"]`, which Unit 14 §3.6 already records at submission — *not* from the current `LeaveRule`, because HR may have edited it since submission (invariant 12.5). If the deduction fails the approval rolls back; an approved application without its deduction must be impossible. Idempotent: a partial unique constraint on `(application)` where `type='deduction'` (added by migration in this unit). The existing append-only manager discipline is preserved. |
| D2 | **Non-annual leave writes no ledger row.** Leave types that do **not** consume annual entitlement (maternity, paternity, compassionate, ...) get no `LeaveBalanceTransaction` at all — no new special-leave balance model (matches Unit 18 `balance_restored_days = 0` and project-overview). `get_available_balance` stays annual-only. |
| D3 | **Restoration remains owned by Unit 18.** Unit 23 only guarantees the written `DEDUCTION` row carries exactly `days = application.working_days` and `financial_year = application.financial_year_label` — the same two values the Unit 18 `LedgerBalanceProvider.get_deduction` reports (it derives the deduction from the application record, not from a ledger lookup) — so a later cancellation restoration nets the balance to zero. A round-trip test covers it: finalise → approve a cancellation → balance returns to the pre-deduction value, with exactly one deduction and one restoration. |
| D4 | **Document data comes only from the persisted approved application** (reference, employee name/grade/designation/department, leave type, dates, working days, reason, plus the new `approved_on` and `remaining_balance`). `FIELD_CATALOG` gains `approved_on` and `remaining_balance` (**additive** — existing templates stay valid; `ALLOWED_FIELD_KEYS` derives from the catalog). Catalog `sample` values are **never** used in an approved document; template fields with no value render blank. `remaining_balance` is read from `get_available_balance(employee_id, application.financial_year_label)` at render time (the render task runs on commit, so the ledger already includes the deduction). |
| D5 | **Rendering runs in Django-Q2**, enqueued via `transaction.on_commit`. The task is idempotent and retry-safe (guarded by the `ApprovedLeaveDocument` row: `pending` → `ready`/`failed`). A render failure records a sanitized error (no stack trace to clients) and is logged; it never rolls back and never raises into the approval. Balance is transactional business state; the document is a retryable derived artifact. |
| D6 | **Storage:** the PDF goes through the existing storage seam under the distinct prefix `approved/{application_id}/`; access only by short-lived signed URL (`SUPABASE_SIGNED_URL_EXPIRY`). Today `leave/services/storage.py::upload_document(file, application_id)` hard-wires the path `leave-documents/{application_id}/...` and cannot take a custom prefix — this unit extends it minimally (an optional prefix / bytes-friendly entry point) so the approved document can live under `approved/`. `signed_document_url(file_path)` and `delete_document(file_path)` already accept an arbitrary path and need no change. |
| D7 | **Access, all GET-only:** the owner-scoped employee endpoint returns 404 for non-owners (per Units 15/18/19 discipline, never 403); the HR endpoint is guarded by `IsHRRole` (non-HR 403); an assigned approver who passes Unit 16 `workflows.policies.get_view_access` may read the approved document. Everyone else gets 404 or 403 as appropriate. There are no create/update/delete endpoints; non-GET returns 405. |
| D8 | **Out of scope:** emails (Unit 22 stays deferred), DOCX (deferred — PDF only, no `python-docx`), invalidation of the document when the leave is later cancelled (recorded as a follow-up, not built), carry-forward. No new tracking event type (the payload vocabulary is pinned in Unit 21 D11 / the frontend `EVENT_ICONS` set); instead the unit records an `audit` entry for finalisation (`application.finalised` style) and for `document_generated` / `document_failed`. Found-in-Phase-1 correction: no fixture balance/document provider exists or is deleted — `LedgerBalanceProvider` is already ledger-backed, and `leave/providers/fixture*.py` are the **rules** provider (still imported by tests and the Unit 18 fallback) and are left untouched. |

### Schema

New `documents.ApprovedLeaveDocument` model — `application` unique
FK/OneToOne → `leave.LeaveApplication`, `status` (`pending | ready | failed`),
`file_path`, `generated_at`, sanitized `error` (text, blank), `created_at` /
`updated_at` — plus the D1 partial unique constraint
(`LeaveBalanceTransaction`, `type='deduction'`, per-`application`). Both need
migrations. Nothing else changes.

### Dependency

`uv add reportlab` if not already present (it is **not** today — not in
`backend/pyproject.toml`, not referenced anywhere). No other new packages;
DOCX (`python-docx`) is explicitly deferred.

### Frontend (minimal)

An "Approved leave document" card with a download button on
`app/(dashboard)/applications/[id]/` (the Unit 15 tracking page) when tracking
status is `approved` (states: pending / ready / failed), and the same on the HR
finalized-leave detail (`/dashboard/hr-admin/audit/applications/[id]`). Reuse
existing panel/badge components and `ui-context.md` tokens only. Add a Next.js
proxy route for the download URL following `app/api/_lib/api-fetch.ts` and the
`app/api/leave/**` proxy pattern.

### Corrected references from the old draft

- Removed "HR Unit 12 credit-line" (Unit 12 is the **employee dashboard**) and
  "HR Units 8–9 special-leave balance" (Units 8–9 are **delegation /
  reassignment**). The template singleton is Unit 10; the HR finalized-leave +
  audit view is Unit 11.
- Removed the claim that a fixture balance/document provider must be deleted
  (none exists; `LedgerBalanceProvider` is already ledger-backed; the
  `leave/providers/fixture*.py` rules provider is retained).
- Removed the suggestion to read `context/specs/documents/vocabulary.md` (does
  not exist) and the pinned tracking-event vocabulary cargo from the old text.

## 4. Verification

Backend-first, checked off as implemented. All from `backend/`:

- [ ] Final approval of an annual-leave application (`rules_snapshot` says
      `deducts_annual_balance: true`) writes **exactly one** `DEDUCTION` ledger
      row with `days = working_days` and the correct `financial_year`.
- [ ] Replaying the finalisation (re-calling the service / a second commit
      event) is a no-op — still exactly one deduction row (partial unique
      constraint).
- [ ] A deduction failure inside the final-approval transaction rolls the
      approval back — no approved application without its deduction.
- [ ] Special / non-deducting leave types write **no** ledger row (no
      `DEDUCTION`, no `RESTORATION`).
- [ ] The stored `rules_snapshot` wins: editing the current `LeaveRule`
      afterwards does not change whether/which deduction was written.
- [ ] Finalise-then-cancel round trip: final approval deducts
      `working_days`; an approved cancellation restores them; net effect zero,
      exactly one deduction and one restoration.
- [ ] `render_approved_document()` produces a PDF uploaded under
      `approved/{application_id}/` and returns a signed URL; the PDF contains
      the real approved values (reference, employee, grade, dates, approved_on,
      remaining_balance) and **no** `sample` text; missing fields render blank.
- [ ] A render/upload failure does not affect the approval (approval already
      committed) and is recorded as a sanitized `failed` document state + audit
      `document_failed`, with no stack trace surfaced.
- [ ] Access matrix: owner → 200; HR → 200; assigned approver passing
      `get_view_access` → 200; unrelated authenticated user → 403/404; anonymous
      → 401; POST/PUT/DELETE → 405.
- [ ] `uv run manage.py makemigrations --check` shows a diff containing **only**
      the two expected migrations (`ApprovedLeaveDocument` + the deduction
      uniqueness constraint).
- [ ] Full backend suite green (`uv run manage.py test --noinput`),
      `uv run manage.py check` clean.
- [ ] Frontend: `npm test`, `npx tsc --noEmit -p tsconfig.test.json`,
      `npm run lint`, `npm run build` all green.

## 5. Dependencies

- Units 16/17/18/19/20/21 — finalisation/decision spine (`decide()`), the
  append-only ledger + `LedgerBalanceProvider`, the storage seam
  (`leave/services/storage.py`), the document template + `FIELD_CATALOG`
  (Unit 10/11), `DatabaseRulesProvider.get_available_balance` (Unit 20), and
  the routing/tracking spine (Unit 21).
- ReportLab — to be added (`uv add reportlab`); not present today. DOCX is
  deferred (no `python-docx`).
- No other new packages.