# Unit 23b — Approved Leave Document (Detailed Design)

**Status: DRAFT — awaiting developer approval. Contains a new third-party
dependency (`reportlab`) that requires explicit sign-off (see §2 D1).**

## 1. Context recap

The build plan's Unit 23 ("Final Approval, Balance, and Document Generation")
was committed as `eb7361d`, but only its **balance** half was ever real. The
document half was written as an unused function and never built. Unit 25
(`6f9474e`) has since wired the balance half, so the document half is all that
remains — hence this unit.

The build plan (§Unit 23, `context/specs/luanar-build-plan.md:767-812`) requires
that on final approval the system generates an official approved-leave document
from the configured template, and that the employee, HR and the assigned
approver can read it. The deferred design lives in
`context/specs/23-final-approval-balance-and-document-spec.md` (D2, D4–D8); this
unit adopts those decisions unchanged and resolves them against the current
code.

### 1.1 Verified current state (Phase-1 recon, 2026-09-25)

| Area | Reality |
|---|---|
| `documents/models.py` | Only `LeaveDocumentTemplate`. **No `ApprovedLeaveDocument`** — so no `application`/`status`/`file_path` row exists to guard a render against. |
| `documents/services.py` | Only `get_template()`, the 10-key `FIELD_CATALOG`, `ALLOWED_FIELD_KEYS`, `DEFAULT_FIELDS`, `DEFAULT_SIGNATURE_AREAS`, `MAX_SIGNATURE_AREAS = 8`, `MAX_TEXT_LENGTH = 2000`. **No `enqueue_approved_document_render`.** |
| `documents/urls.py` | One route only: `leave-document-template/`. |
| `documents/views.py` | Only `LeaveDocumentTemplateView` (GET/PATCH, `IsHRRole`). |
| `finalise.py` | `finalise_approved_application` is the **only** remaining unimplemented function. It calls `record_deduction`, `ApprovedLeaveDocument.objects.get_or_create(..., status=PENDING)` and `enqueue_approved_document_render`. It is unwired: `decide()` calls `record_deduction` directly (Unit 25 D4). |
| `LeaveApplication` | **No `approved_on` column** (Unit 23 D4 wants it on the document). |
| Audit vocabulary | `Action` has `DOCUMENT_ADDED/REPLACED/REMOVED/RETIRED` but **no `DOCUMENT_GENERATED` / `DOCUMENT_FAILED`**. `TargetType` has `DOCUMENT_TEMPLATE` but no approved-document code. |
| Storage seam | `upload_document(file, application_id)` hard-wires `leave-documents/{application_id}/...`. `signed_document_url(file_path)` and `delete_document(file_path)` already take an arbitrary path. |
| Background tasks | `django_q` is in `INSTALLED_APPS`; `Q_CLUSTER` is configured (`orm: "default"`, 4 workers, 60s timeout). `users/tasks.py` holds a single `ping()` task. **No render task exists and nothing has ever called `async_task`.** |
| Balance at render time | `leave/providers/database.py::get_available_balance` is already **ledger-backed** (resolved entitlement + `_ledger_net`), so a post-commit render sees the deduction. |
| Approver read gate | `workflows.policies.get_view_access(user, application)` exists and returns `ViewAccess | None` — reusable as-is. |
| Frontend | Employee surface `leave/[id]/submitted/page.tsx` has **no** document affordance. HR surface is `hr-admin/audit/applications/`. The signed-URL fetch pattern already exists at `frontend/lib/approvals/service.ts:154`. |
| Dependencies | **`reportlab` is neither installed nor declared** in `backend/pyproject.toml`. |

### 1.2 What this unit must not become

Unit 25 proved that a "wiring" unit hides dead code: `finalise.py` referenced
three exception classes that existed nowhere, a wrong field lookup, and a
non-deducting-leave-type crash — all invisible because nothing called it. So
Unit 23b's acceptance criterion is that the whole path is **executed by tests**,
not merely importable. The E2E happy path in `backend/tests/test_end_to_end.py`
gains one assertion (a document reaches `ready`), which forces the render to
actually run in-process.

## 2. Decisions (D1–D12)

| # | Decision |
|---|---|
| D1 | **The `reportlab` dependency requires explicit developer approval and is the only new dependency.** It is added to `backend/pyproject.toml` and installed via `uv`. No `python-docx` (DOCX stays deferred), no `pypdf` (no read-back), no font package (the two PDF core fonts are built in). If approval is withheld, this unit does not proceed. |
| D2 | **`ApprovedLeaveDocument` is a new model in the `documents` app** — one row per application, append-only on the file fields. Fields: `application` (OneToOne, `PROTECT`), `status` (`pending`/`ready`/`failed`), `file_path`, `file_url`, `file_name`, `file_size`, `content_type`, `approved_on`, `rendered_at`, `error_message`, `created_at`. Migration `documents/0002_*.` Its `save()` mirrors the Unit 24/Unit 18 discipline: a `pending`/`failed` row may become `ready`, but a `ready` row's file fields and `status` are immutable (a re-render is refused, not silently overwritten). `get_or_create(application=...)` in `finalise.py` therefore yields **exactly one document row per application**, which is the idempotency anchor D5 relies on. |
| D3 | **`LeaveApplication.approved_on` is added** (nullable `DateTimeField`, set once on the first final approval), so the document can state *when* the leave was approved rather than re-deriving it. Second migration in this unit (`leave/0012` is taken by Unit 25; this becomes `0013`). It is set inside `decide()`'s existing transaction, so it cannot disagree with the status. |
| D4 | **The document is rendered from the persisted application only.** Data source: reference number, employee name / grade / designation / department (from `EmployeeProfile`), leave type name, start/end dates, working days, reason, `approved_on`, and `remaining_balance` read from `get_available_balance(employee_id, financial_year_label)` **at render time** (the render runs on commit, so the deduction is already in the ledger). `FIELD_CATALOG` gains `approved_on` and `remaining_balance` — **purely additive**, so every existing template row stays valid; `ALLOWED_FIELD_KEYS` derives from the catalog, so the template API accepts the new keys with no serializer change. Catalog `sample` values are for the HR preview only and are **never** substituted into a real document: a field with no value renders blank. |
| D5 | **Rendering is a Django-Q2 task enqueued via `transaction.on_commit`.** `documents/tasks.py::render_approved_document(document_id)` reads the row, renders with ReportLab, uploads, and flips `pending → ready`; a failure flips `pending → failed` with a **sanitized** `error_message` (no traceback, no internals) and is logged. A render failure **never rolls back the approval and never raises into the caller** — the balance is transactional business state, the document is a retryable derived artifact. The task is idempotent: a row already `ready` is a no-op, and `ApprovedLeaveDocument.objects.get_or_create` in `finalise.py` means re-running finalisation re-enqueues the *same* row rather than creating a second one. |
| D6 | **Storage uses a distinct `approved/{application_id}/` prefix.** `storage.upload_document` gains an optional `prefix` argument (defaulting to the existing `leave-documents`, so Unit 19/18 callers are untouched) and a bytes-friendly sibling `upload_bytes(data, file_name, *, prefix, application_id, content_type)` for the in-memory PDF. `signed_document_url` / `delete_document` already accept arbitrary paths and need no change. |
| D7 | **Access is GET-only, with three legitimate readers.** (a) The **owner** reads it; a non-owner gets **404**, never 403 (Units 15/18/19 discipline — do not leak existence). (b) **HR** reads via an `IsHRRole`-guarded endpoint; a non-HR role gets 403. (c) An **assigned approver** may read when `workflows.policies.get_view_access(user, application)` returns access. Everyone else 404/403. There are no create/update/delete endpoints; non-GET returns 405. A `pending`/`failed` document is reported as such (`available: false`, no signed URL minted) rather than 404-ing the whole resource, so the owner can tell "not generated yet" from "not allowed". **Amendment (implemented):** the endpoints are keyed by **application id**, not document id — every surface that shows the document already holds the application id, so keying by application avoids making three payload serializers carry a document id they would otherwise never use. |
| D8 | **`finalise_approved_application` becomes the single finalisation entry point.** `decide()` currently calls `record_deduction` directly (Unit 25 D4). This unit changes that call to `finalise_approved_application(app)`, which itself calls `record_deduction` — so the deduction stays inside the same transaction (Unit 25 D4 is preserved, not duplicated) and the document is created in the same atomic block. The D4 rollback guarantee is re-pinned by a test that fails the document step and asserts the approval still rolls back with the deduction. This removes the duplicated `consume_deduction_decision` branch in the orchestrator rather than adding a second one. |
| D9 | **Audit vocabulary gains two actions, and no new target type.** `DOCUMENT_GENERATED` and `DOCUMENT_FAILED` are added to `AuditEntry.Action`; both target `TargetType.APPLICATION` with the application's `reference_number` as the summary, because the document is a derived artifact of the application and the audit log's target vocabulary is already pinned by Unit 24. **No `TargetType` is added** — the audit vocabulary is deliberately not grown for a derived row. **Amendment (implemented):** the spec originally claimed that adding `TextChoices` values generates no migration; that is wrong — Django emits an `AlterField` for the changed `choices`, so this unit's third migration is `audit/0008_alter_auditentry_action_alter_auditentry_actor`. That same migration makes `AuditEntry.actor` **nullable**, because a background render has no human actor and attributing it to a person would be a fabrication in the authoritative log; a null actor means "system action", and `AuditEntrySerializer` renders it as `System`. |
| D10 | **The frontend adds a read-only affordance at three points**, reusing the existing signed-URL pattern (`frontend/lib/approvals/service.ts:154`): the employee tracking view (`/dashboard/applications/[id]`, where an approved leave is actually viewed — `leave/[id]/submitted/` is the pre-approval confirmation and redirects away for any other status), the HR `hr-admin/audit/applications/` detail, and the approver detail. All three are **link-to-signed-URL only** — the PDF is never proxied through Next, and no viewer component, iframe or download-token logic is built. A `pending`/`failed` state renders an inline status, not a broken link. |
| D11 | **Field-catalog rendering is data-driven and total.** The renderer walks `template.fields` in order, resolves each `key` through one `_document_values(application)` mapping, and renders `label: value` with a blank value when unresolved. An unknown `key` (e.g. a template edited by a future catalog version) renders blank rather than raising — HR's template must never be able to break the render task. Signature areas are rendered as a fixed caption grid, capped by the existing `MAX_SIGNATURE_AREAS = 8`. |
| D12 | **Out of scope.** Document invalidation when leave is later cancelled (recorded as a follow-up — the document stays as the historical record of what was approved); carry-forward; DOCX; email attachment (Unit 22 stays as-is and is not extended); a document version history; `pypdf` read-back assertions in tests (tests assert the row's metadata and that the PDF is non-empty, not its byte content). No new tracking event type (the `EVENT_ICONS` vocabulary is pinned by Unit 21 D11). |

## 3. Verification plan (Phase 2)

Backend:
- `ApprovedLeaveDocument` tests: one row per application via `get_or_create`;
  `ready` rows reject file-field mutation; `pending → ready` and `pending → failed`
  are the only legal transitions.
- Render task tests: a real ReportLab render of a template with all 12 catalog
  keys produces a non-empty PDF and a `ready` row; a forced failure produces a
  `failed` row with a **sanitized** message and **no** traceback in
  `error_message`; a second run on a `ready` row is a no-op.
- Idempotency: two calls to `finalise_approved_application` yield one row and one
  deduction.
- Rollback: a failure in the document step still rolls back the approval **and**
  the deduction (Unit 25 D4 preserved).
- Access matrix: owner 200 / non-owner 404 / HR 200 / non-HR 403 / assigned
  approver 200 / unassigned approver 403-or-404 / non-GET 405; `pending` and
  `failed` never mint a signed URL.
- Storage prefix: the uploaded path starts with `approved/{application_id}/`.
- `FIELD_CATALOG` grew additively: all 10 original keys still validate, the 2 new
  keys are accepted by the template API.
- `backend/tests/test_end_to_end.py`: the happy-path journey asserts a document
  reaches `ready` with a file path, so the whole render path executes in-process.
- Gates: `uv run manage.py check`; `uv run manage.py makemigrations --check
  --dry-run`; `uv run manage.py test` (673 + new, all OK).

Frontend:
- `npm test`, `npm run typecheck:test`, `npm run lint` — all clean. New tests
  cover the three affordances' `pending` / `ready` / `failed` states and the
  non-owner 404 handling.

## 4. Open question for the developer

**D1 needs an explicit yes/no: may this unit add `reportlab` to
`backend/pyproject.toml`?** It is the only new dependency. Everything else in
this spec is implementation inside the existing stack (`django_q`,
`django.core.files`, the existing Supabase storage seam, ReportLab-free PDF
generation is not practical for a template-driven document). If `reportlab` is
declined, this unit is blocked and the document feature stays unbuilt.
