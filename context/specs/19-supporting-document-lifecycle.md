# Unit 19 — Supporting Document Lifecycle

**Depends on:** Unit 13 (Leave Application and Drafts: the `SupportingDocument` model, the Supabase storage abstraction and the nested documents endpoints), Unit 1 (file-storage abstraction and development storage), Unit 16 (approver review, `ApprovalReview.documents`, `ApprovalDocumentDownloadView`), Unit 17 (correction/resubmission and the document `status`/`retire_*`/`replaced_by` schema).
**Connected to Units 2–11:** HR-managed data integration remains behind swappable providers/fixtures until Unit 20. Unit 19 needs no new provider.

---

## 1. Goal

Complete the supporting-document experience attached to a leave application: upload, view, download, required-document validation, replacement during draft **and** after a returned-for-correction, read-only documents while under review and after approval/rejection, and a document replacement/removal history. Employee document actions are restricted to the **editable** statuses; after anything leaves the employee's control the documents become a read-only, auditable record.

---

## 2. Design

### 2.1 Behavioural rules (authoritative on the backend)

| Application status | Upload | Remove | Replace | View / Download |
|---|---|---|---|---|
| `draft` | Yes | Yes (row **hard-deleted**, storage object removed) | Via remove + upload (existing endpoints) | Owner (list/download via signed URL) |
| `correction_required` | Yes | Yes — row **retired** (`removed`, retired_by = employee, retired_at = now); storage object retained so the previous submission's snapshot still resolves | Yes (`replace` endpoint) — old row **retired** (`replaced`, `replaced_by` = new row) | Owner |
| `submitted` / `approved` (under review) | No | No | No | Owner + assigned approver, **active rows only** |
| `rejected` / `cancelled` (terminal) | No | No | No | Owner + approver (read-only), active rows only |

Additional rules:

1. **Editable statuses are exactly `draft` and `correction_required`.** Every mutation on any other status returns `409 application_not_editable`. This is the single source of "read-only while under review / after approval".
2. **Replacement after rejection** — a `rejected` application is terminal (Unit 17). The employee re-applies via a fresh draft, where they attach fresh documents with the normal draft affordances. The rejected record's documents are never mutated; they remain as the historical submission.
3. **Draft mutation is destructive-by-nature**: removal hard-deletes the row and the storage object, because a draft has no audit history worth preserving. In contrast, a `correction_required` application has already been submitted at least once, so its rows are **retired, never deleted** — the previous submission's revision snapshot and the audit record must keep resolving names/URLs (this is the "Document replacement history" foundation, consumed by Unit 24).
4. **Replace is a single, atomic action** valid only when the application is editable **and not a draft** (i.e. `correction_required`): the new file is uploaded, the old row flips to `retired` with `retire_reason = replaced`, `retired_by` = `request.user`, `retired_at` = now, and `replaced_by` points at the new row. During a **draft**, employees replace by Remove + upload, which the shared uploader already expresses. This keeps one uniform `retire_reason = replaced` path and one easy UI story.
5. **Remove** on `correction_required` retires the row with `retire_reason = removed` (same retirement fields). Retiring never deletes the storage object.
6. **File constraints** (unchanged from Unit 13, enforced at every write): `MAX_DOCUMENT_SIZE` = 10 MB after trimming, content type from the existing allowed set (`application/pdf`, Word, JPEG, PNG, WebP, `text/plain`, any `image/*`), name sanitized by the existing `_sanitize_document_name`. No deduplication of identical names.
7. **Required-document validation** (Unit 14 `DOCUMENT_REQUIRED`) keeps counting **active** rows only (`documents.filter(status="active")`). A retirement that empties the set is caught by that validator on the next submission attempt — Unit 19 changes nothing there.
8. **View/download always re-signs** a fresh Supabase signed URL from the stored `file_path` at read time (existing `signed_document_url`); clients never get a URL that lives longer than `SUPABASE_SIGNED_URL_EXPIRY`.
9. **`file_path` is internal.** It stops being serialized to any client (it was only useful for storage debugging). The client type drops it.
10. **Active rows are the working set.** Nested `documents` (application detail, approval review, tracking payload) return active rows only. The document list endpoint can additionally return retired rows with their lifecycle fields for the employee archive view. Approvers keep seeing active rows only (they review, not audit).
11. **Authorization** mirrors the existing rules: employee reads/mutations are owner-scoped through the nested `application_pk`/`request.user` (another employee's application → 404, never 403). Approver view/download stays behind the existing approver-only download path.

### 2.2 Document state model

```text
                       (correction_required)
 uploaded ──▶ active ──┬─ remove ─▶ retired(removed)
                       └─ replace ─▶ retired(replaced) ─▶ new active row
                         (draft)     remove ─▶ (row + storage object hard-deleted)
```

- `status`: `active` | `retired`.
- On `retired`: `retired_at`, `retired_by` (auth user), `retire_reason` (`replaced` | `removed`), and `replaced_by` when the reason is `replaced`.
- A document is never re-activated; there is no update path, only create/retire/hard-delete.

### 2.3 Visual and interaction decisions

Follow `ui-context.md`: LUANAR blue `#0097F0` for interactive elements, neutral slate surfaces, Inter, Lucide icons only, existing 21st.dev component patterns (reuse the existing Dialog/Badge/Panel/Tabs patterns already in the repo — in particular `components/approvals/panel.tsx`), `radius-xl` cards, flat subtle shadows, no gradients or glassmorphism, minimal animation, dark mode supported by the dashboard shell tokens.

**Status colors**
- Retired/archived document rows: slate, with a muted "Replaced on {date}" / "Removed on {date}" line. `replaced` uses the slate "cancelled" tone; `removed` uses the muted neutral tone. Neither is a badge — a small muted subtitle.

**Apply/edit form (`/leave/[id]` + new draft, Unit 13 `LeaveApplicationForm`)**
- Draft: existing uploader unchanged (Removes are immediate; Replace is Remove + upload), with a small destructive-style confirm on each Remove so an accidental click doesn't drop a file.
- Correction edit (`mode="edit"` on a `correction_required` application): the uploader is **enabled** (fixing the current bug where the UI offers mutation but the API rejects it — see §3.5 first bullet). Each row gets **Remove** (retires, confirms first) and, while the message explains "This replaces the copy approvers saw", **Replace** (opens a file picker; the old row is retired).
- Upload errors surface inline as today (`file_too_large`, `file_type_not_allowed` map to friendly messages); `application_not_editable` renders a read-only list with no controls.

**Tracking detail (`/applications/[id]`, Unit 15)**
- A new **Supporting documents** card is rendered whenever the tracking payload includes a `documents` block:
  - Active rows: name, size, uploaded-on, and an **Open** button that opens the server-provided signed URL in a new tab (`noopener,noreferrer`), mirroring the approvals `DocumentsCard` interaction.
  - When the document list endpoint reports retired rows, a collapsed **Archived (N)** section lists them read-only: name, "Replaced/Removed on {date}", and no Open button for `removed` rows (their signed URLs still exist but there is nothing to view for a removed file — see decision note in §3.5).
- The employee dashboard/review-summary list stays as-is.

**Approver (`/approvals/[id]`)**
- The existing `DocumentsCard` is unchanged (active rows, View). No lifecycle indicators on the approver side: they review the current working set.

**Responsive:** cards, rows and the uploader stack naturally at `sm` widths; the uploader dropzone remains full-width.

---

## 3. Implementation

Paths below use the repo layout from `architecture.md`. Align names and helpers with Units 13–18. Reuse existing utilities (API error format, pagination, audit helper, status enums, permission helpers, storage functions). Do not duplicate them.

### 3.1 Backend data model (`backend/leave/`)

**No schema migration is required.** Unit 17 already added `status`, `retired_at`, `retired_by`, `retire_reason`, and `replaced_by` (self-FK) to `SupportingDocument`, plus the `(application, status)` index. This unit only exercises them.

### 3.2 Storage (`leave/services/storage.py`)

Keep `upload_document`, `signed_document_url`, `delete_document`, `_sanitize_document_name`, `is_allowed_document_content_type`, `MAX_DOCUMENT_SIZE` as they are. Add no new storage functions; retirement deliberately keeps the object in the bucket.

### 3.3 Document lifecycle service (`leave/documents/services.py`, new)

Small, unit-testable command layer used by the view:

- `EDITABLE_STATUSES = {LeaveApplication.Status.DRAFT, LeaveApplication.Status.CORRECTION_REQUIRED}`
- `ensure_editable(application)` → raises `DocumentNotEditable` when `application.status not in EDITABLE_STATUSES`.
- `upload(user, application, upload) -> SupportingDocument` — validates size/type (reuse the checks currently in `perform_create`), calls `upload_document(file, app_id)`, creates the active row, audits `document.uploaded`.
- `remove(user, application, document)` — `ensure_editable`; if `application.status == DRAFT`: `delete_document(document.file_path)` (guarded, log-and-continue on storage failure like today) then `document.delete()`; else `document.retire(user, reason=REMOVED)`. Audits `document.removed` (draft) or `document.retired`.
- `replace(user, application, document, upload)` — `ensure_editable`, and `application.status == CORRECTION_REQUIRED` (a draft uses remove+upload; the endpoint rejects a draft with `application_not_editable` — this is correct, the client never calls it on a draft). Validates the file, uploads the new row, then `document.retire(user, reason=REPLACED, replaced_by=new_row)`. Atomic in one transaction; audits `document.replaced`.
- `retire` is a model method on `SupportingDocument`: sets `status=retired`, `retired_at`, `retired_by`, `retire_reason`, optional `replaced_by`, and `save()`. No re-activation path.

**Decision note (Replaced vs Removed archive):** retired docs keep their Supabase object so signed URLs remain resolvable (submitted snapshots/revisions reference the row). The removed-file archive therefore is cheap to render; the UI decides whether to offer an "Open" for a `removed` row (recommended: no — the file was intentionally removed; the active + `replaced` rows carry the meaningful history).

### 3.4 Serializers (`leave/serializers/__init__.py`)

- `SupportingDocumentSerializer`: add `status`, `retired_at`, `retire_reason`, `retired_by` (name), `replaced_by` (id + file_name) to the fields; **drop `file_path`** (internal). `file_url` stays a fresh signed URL.
- `LeaveApplicationSerializer.documents` → return **active rows only** via a `SerializerMethodField` (`documents.filter(status="active")`), so draft/correction working sets stay clean and the review summary shows exactly what will be submitted.
- The approval review (`workflows/approval_payloads.py`) already filters `status="active"` — leave unchanged.

### 3.5 View changes (`leave/views/`)

Move `SupportingDocumentViewSet` into `leave/views/documents.py` (import it back in `leave/views/__init__.py`) so the document logic stops growing inside the package blob, and extend it:

- **Fix the correction-edit bug first**: `perform_create` currently rejects any status other than `DRAFT` (`Cannot upload documents to a submitted application.`). Replace the guard with `ensure_editable` so `correction_required` applications can add documents, and map the guard to `400`/`409` (see error codes). This is the change that unlocks §2.1's correction replacement.
- `perform_destroy` → delegate to `services.remove` (`ensure_editable` + hard-delete in draft / retire otherwise). A draft removal stays hard; correction removal retires with `removed`.
- New `@action(detail=True, methods=["post"]) replace` (URL `.../documents/{pk}/replace/`): multipart `file`, delegates to `services.replace`, returns `201` with the new document payload plus `"retired_document": <pk>`.
- `list` accepts `?include_retired=true`: default returns active rows (unchanged); with the flag it returns active **and** retired rows with lifecycle fields (owner-scoped, newest first as today). No pagination (documents per application are small).
- Keep `permission_classes`/`IsOwner` and the owner-scoped queryset exactly as they are.

### 3.6 Audit

Use the existing audit helper. Record actor, action, timestamp, application and document/file name for: `document.uploaded`, `document.removed` (draft), `document.retired` (removal in correction: reason `removed`), `document.replaced`. Audit rows are written in the same transaction as the change (invariant 12.10).

### 3.7 API (DRF, following the shared API conventions from Unit 1)

**Employee (owner-scoped, existing nested path)**

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/leave-applications/{app}/documents/?include_retired=true` | Active rows by default; retired rows + lifecycle when the flag is set |
| POST | `/api/leave-applications/{app}/documents/` | Upload (editable statuses only) |
| DELETE | `/api/leave-applications/{app}/documents/{pk}/` | Remove (editable statuses only; hard in draft, retire otherwise) |
| POST | `/api/leave-applications/{app}/documents/{pk}/replace/` | Replace (correction_required only) → `201` new row + `retired_document` pk |

**Additive tracking extension (Unit 15 payload):** add a `documents` block of active rows (`id`, `file_name`, `file_size`, `content_type`, `file_url`, `uploaded_at`) to the tracking detail, for the owning employee only. Existing consumers must not break.

**Approver:** unchanged — `ApprovalReview.documents` (active) and `ApprovalDocumentDownloadView` already read-only.

**Error codes:** `document_not_found` (404), `application_not_editable` (409), `document_not_active` (409, replacing/removing an already-retired row), `file_required` (400), `file_too_large` (400), `file_type_not_allowed` (400). Keep the existing `detail` messages for the 400 validation errors so current client parsing keeps working, and use the repo's `{"error": code}` convention for the 409s.

**Regression requirements on existing endpoints:** drafts still list/delete as today; the review summary's `application.documents` still shows the working set; approvals documents/docs-download behave identically; Unit 13–18 tests stay green.

### 3.8 Frontend (`frontend/`)

- `lib/leave-api.ts`: `SupportingDocument` drops `file_path`, adds optional `status`/`retired_at`/`retire_reason`/`retired_by`/`replaced_by`; add `listDocuments(appId, { includeRetired })`, `replaceDocument(appId, docId, file)`. Upload/delete proxies already exist.
- New proxy route `frontend/app/api/leave/leave-applications/[id]/documents/[docId]/replace/route.ts` (multipart passthrough), and thread `include_retired` through the existing documents `GET` proxy.
- `components/leave/SupportingDocumentsUploader.tsx`:
  - New `editable?: boolean` prop wired from the form's context/status (draft or correction edit). When `false` (read-only submitted/approved/rejected/cancelled) render the list without controls — currently the caller toggles a raw `disabled`; unify on `editable`.
  - Remove gains a small confirm step (draft) and, for `correction_required`, Replace per row (file picker → `replaceDocument` → refresh), plus the "replaces the copy approvers saw" hint.
- `components/tracking/` (new `supporting-documents-card.tsx`): renders the tracking `documents` block with **Open** buttons; fetches `listDocuments(id, { includeRetired: true })` for the collapsible **Archived (N)** section. Mount it on `/applications/[id]` when the tracking payload has a `documents` block.
- `LeaveApplicationForm`: pass `editable` from the app status + mode so the correction edit path actually lets employees replace documents (resolves the current UI-vs-API mismatch).
- Tracking fixtures/tests: add `documents` blocks to tracking fixtures; tracking types gain `documents?`.
- Approver `DocumentsCard`: no change.

After a successful upload/remove/replace, refetch from the server. Do not update state optimistically, because the backend owns final state, file names, and signed URLs.

### 3.9 Seed and fixtures

Extend the existing seed command (idempotent, dates relative to today):
- Keep current seeded applications; attach `SupportingDocument` rows to representative ones:
  - A `correction_required` application with one `active` doc plus one `retired`/`replaced` doc (exercises the archive and the replace UI).
  - An `approved` application with one `active` doc (approver view/download).
  - A draft with one active doc (owner view).
- `backend/leave/tests/stubs.py`: keep seeding file objects for the document fixtures used by tests (a small `SimpleUploadedFile`-style helper already exists for document tests).

### 3.10 Tests

**Backend (Django `TestCase`)**
- Editable matrix: upload/remove succeed in `draft` and `correction_required`; every other status returns `409 application_not_editable` for upload, remove and replace.
- Draft semantics: remove hard-deletes the row and calls storage delete; no audit history is preserved; replace is refused on a draft.
- Correction semantics: remove retires (`removed`, retired_by/at set); replace uploads new row, retires old (`replaced`, `replaced_by` set), storage objects preserved for both; no update/delete on the retired row (`document_not_active`).
- Validation: 10MB/type/name-sanitize limits still enforced on the new paths; `file_required` when no file.
- Required-document rule: removing the last active doc of a `requires_document` leave type is rejected at the next validation/submission (unit-level check on the validator's active-count).
- Serializers: `documents` excludes retired; `?include_retired=true` includes them with lifecycle fields; `file_path` is absent.
- Tracking payload: `documents` block present for the owner, absent/present per unit 15 conventions; regression fixtures pass.
- Authorization: another employee's upload/remove/replace → 404; approvers can still download active docs only.
- Audit: rows exist for uploaded/removed/retired/replaced, same transaction.
- Regression: Unit 13–18 suites stay green (especially drafts list, review summary, approvals documents).

**Frontend (Vitest + React Testing Library, `vi.mock` on the document API)**
- Uploader: `editable=false` renders no controls; draft remove confirms then deletes; correction rows offer Replace (calls `replaceDocument`, refreshes list) and show the replaces-hint; `file_too_large`/`type_not_allowed` map to friendly inline errors.
- Tracking documents card: active rows render with Open; archive collapsed section lists replaced/removed with dates when retired rows exist; empty state when no documents.
- `LeaveApplicationForm`: correction edit keeps the uploader editable; submitted/approved/rejected/cancelled render read-only.
- Proxies: `replace` route forwards multipart; `include_retired` passthrough asserted against the mocked fetch.

---

## 4. Dependencies

**No new packages.**
- Backend: Django, DRF, Supabase storage client — unchanged.
- Frontend: Next.js, Tailwind, Lucide, react-dropzone (already used by the uploader) — unchanged; reuse existing panel/format utilities.

**Internal dependencies:** Unit 13 (model, storage, nested endpoints, uploader), Unit 16 (approver documents card + download view), Unit 17 (lifecycle schema, correction edit flow, retirement fields), Unit 14 (required-document validator), Unit 15 (tracking payload/page).

**Out of scope for this unit**
- HR views of document history and the full audit interface (Units 11 and 24).
- Replacing documents after final approval, or mutating a rejected application (Unit 17 decision: terminal).
- Real email/submission notifications for document activity.
- Reconciliation with real units 2–5 rules or the real Unit 6 workflow contract (Unit 20).

---

## 5. Verification checklist

### Editable states
- [ ] Upload and remove work in `draft` and `correction_required`; every other status returns `409 application_not_editable` for all three mutations.
- [ ] Correction editing now allows the employee to replace documents (the previous UI-vs-API mismatch is gone).
- [ ] Draft remove hard-deletes the row and storage object; correction remove retires with `removed`.
- [ ] Replace retires the old row (`replaced`, `replaced_by` set) and returns the new row + `retired_document` id.

### Read-only and history
- [ ] Submitted/approved/rejected/cancelled applications render documents read-only for owners and approvers.
- [ ] Nested `documents` never include retired rows; `?include_retired=true` returns them with lifecycle fields.
- [ ] The tracking detail exposes an active `documents` block; the employee can open/download via signed URLs.
- [ ] Review summary submits exactly the active working set.
- [ ] No mutation path exists for a retired document (`document_not_active`).

### Validation and storage
- [ ] Size/type/name constraints still enforced on upload, remove-replace flow and replace.
- [ ] Required-document validation counts active rows only and still blocks submission when the set becomes empty.
- [ ] `file_path` is no longer serialized to any client; the frontend type drops it.

### Authorization, integrity, audit
- [ ] Another employee's document operations return 404, never 403.
- [ ] Approvers download active documents only through the existing approver-only path.
- [ ] Audit rows exist for uploaded, removed, retired and replaced, written in the same transaction.
- [ ] Domain/UI state is never optimistically mutated; the UI refetches after each action.

### UI
- [ ] Uploader respects `editable`; remove confirms; correction rows show Replace with the explanatory hint.
- [ ] Tracking documents card shows active docs with Open, a collapsible Archived section, and an empty state.
- [ ] Approver `DocumentsCard` is unchanged and still opens active documents.
- [ ] All new UI uses ui-context tokens, works in light/dark mode, is keyboard-accessible and usable on mobile widths.

### Cross-cutting
- [ ] No new dependencies were added.
- [ ] Seed data is idempotent and covers draft/correction/approved scenarios with documents.
- [ ] All Django and Vitest tests pass, including the existing Unit 13–18 suites, and lint/type checks are clean.