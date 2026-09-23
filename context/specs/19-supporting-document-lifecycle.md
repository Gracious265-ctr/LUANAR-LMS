# Unit 19 — Supporting Document Lifecycle

read `context/AGENTS.md` before starting.

## Goal

Give every supporting document attached to a leave application a complete, state-aware lifecycle — upload, view, download, replace (or retire) with full history — enforced by the backend across every application state (draft, under review, rejected, correction required, approved), so a document can be managed exactly when the workflow allows it and becomes read-only the moment the workflow forbids it.

## Design

### Confirmed decisions (developer-approved, 2026-09-21)

| Decision | Choice |
|---|---|
| Unit 17 relationship | **Unit 19 owns the document lifecycle.** All document operations (upload/replace/remove/history/read-only rules) live in one backend service + these endpoints. Unit 17's resubmission document flows call this service instead of re-implementing them. |
| Storage abstraction | Does **not exist yet** (only direct Supabase in `backend/leave/services/storage.py`). Unit 19 builds it: a storage-backend abstraction with a Supabase implementation and a local-filesystem development implementation, selected by a setting (mirrors the existing `LEAVE_RULES_PROVIDER` / `LEAVE_TRACKING_PROVIDER` dotted-path pattern). |
| Draft-phase replacement | Replacing/removing a file **during draft** physically deletes the old file and old row (Unit 13 behavior kept — drafts are transient). From submission onward, files are **retired, never deleted** (Unit 17 rule). |
| Replacement history | No new history model. State lives on `SupportingDocument` (`status`, `retired_at`, `retired_by`, `retire_reason`, `replaced_by`); every document op writes an `AuditEvent` via the existing `audit` app (`audit.services.record_event`); a read endpoint composes the timeline. |

### Scope boundary

Unit 19 covers **supporting documents only**. It does **not** build the rejected/correction/resubmission editing flow (Unit 17), the approver review page (Unit 16), final approved-document generation (Unit 23), or HR's finalized/audit view (Unit 11). It delivers the document subsystem those units consume.

### Status gate

| Application status | Upload / Replace / Remove | View / Download |
|---|---|---|
| `draft` | Editable — old file **deleted** on replace/remove | Owner |
| `submitted` / `pending` (under review) | **Read-only** — rejected with 409 | Owner + authorized approver |
| `rejected` | Editable — old file **retired** on replace/remove | Owner |
| `correction_required` | Editable — old file **retired** on replace/remove | Owner |
| `approved` | **Read-only** | Owner + authorized approver |
| `cancelled` (Unit 18) | **Read-only** | Owner |

`LeaveApplication.Status` currently declares only `draft`/`submitted` (Unit 13). Units 16/17 add `pending`, `rejected`, `correction_required`, `approved`. The gate is implemented against the enum, so the read-only/editable rules above activate automatically as those states merge. See "Assumptions to verify".

### Visual and structural decisions

Follow `ui-context.md` tokens and the existing dashboard shell. LUANAR blue for actions, neutral slate for metadata, `radius-xl` cards, Inter, Lucide icons (`FileText`, `Upload`, `Trash2`, `Eye`, `Download`, `RefreshCw`, `History`), flat shadows, datalist dates in `Africa/Blantyre`. Reuse the existing `SupportingDocumentsUploader` (extended), the Unit 13 form/review pages, and the Unit 15 read-only tracker — no new standalone "documents page"; the experience lives inside the existing application pages.

### Download contract

Signed URLs stored in `file_url` expire and cannot be opened with JWT auth from a new browser tab, so Unit 19 replaces the download mechanism with one authenticated Django streaming endpoint that works identically for both storage backends:

- `GET /api/v1/leave-applications/{application_id}/documents/{document_id}/content/` — streams the file (`FileResponse`), `?download=1` toggles `attachment` vs `inline`, `Content-Disposition` carries the original filename. Authorized for the owner, or any user granted by the shared `documents.can_view_content` helper (the seam where Unit 16's `get_view_access` slots in).
- The frontend opens the **Next.js proxy** path in a new tab with `noopener,noreferrer`; the proxy attaches the JWT server-side and streams the bytes through.
- `SupportingDocument.file_url` is retained (API compatibility with Unit 13) but now stores the content-endpoint URL, set by the view, instead of a storage-signed URL. Supabase signed URLs are no longer stored or used by the UI.

## Implementation

### 1. Assumptions to verify before starting

1. **Status enum.** Verify whether `LeaveApplication.Status` already contains `pending`/`rejected`/`correction_required`/`approved` (Unit 16/17 merged). If not, implement the full lifecycle for `draft` + read-only enforcement now, and implement the `rejected`/`correction_required` editable branch as soon as the states land — the gate is a membership check on the enum, so no later refactor is needed.
2. **Unit 13 document model & serializer.** The `SupportingDocumentViewSet`, `SupportingDocumentSerializer`, and `SupportingDocumentsUploader` exist and are extended, not duplicated.
3. **Unit 14 validator.** `validation/validators/documents.py::count_supporting_documents` is updated to count `status="active"` only.
4. **Unit 16 download-URL contract.** The approver's `GET /api/approvals/{id}/documents/{doc_id}/download-url/` keeps its behavior for the Supabase backend. Unit 19's `content/` endpoint and `can_view_content` are the choke point that Unit 17/21 switch the approver flow onto.
5. **`leave.apps` ready to accept a new `storage` package + service module** (no settings wiring required beyond the new settings below).

### 2. Settings

Add to `backend/config/settings/base.py` (alongside `SUPABASE_*` which stay for the Supabase backend):

```python
# Leave document storage (Unit 19). Storage is abstracted; the dev backend
# writes to local disk so uploads/downloads work without Supabase credentials,
# and the production storage technology stays replaceable per architecture.md.
LEAVE_STORAGE_BACKEND = "leave.storage.development.DevelopmentStorageBackend"
LEAVE_STORAGE_ROOT = environ.Path(BASE_DIR.parent, "storage")                 # /storage/ in the repo
LEAVE_DOCUMENT_MAX_SIZE_BYTES = 10 * 1024 * 1024
LEAVE_DOCUMENT_ALLOWED_TYPES = (
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/gif",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
)
```

Default the backend to the **development** backend so the feature is fully testable and demoable with no external credentials. `SUPABASE_BACKEND` value is configured via `LEAVE_STORAGE_BACKEND = "leave.storage.supabase.SupabaseStorageBackend"` when real storage is configured. Update `backend/.env.example` with `LEAVE_STORAGE_BACKEND` (+ optional `LEAVE_STORAGE_ROOT`).

### 3. Storage backend abstraction (`backend/leave/storage/`)

New package, mirroring the provider factory pattern (`leave/providers/__init__.py::get_provider`):

- **`leave/storage/__init__.py`** — `get_storage_backend()` instantiates the class named by `settings.LEAVE_STORAGE_BACKEND` (dotted path, no arguments).
- **`leave/storage/interface.py`** — `StorageBackend` Protocol:

  ```python
  class StorageBackend(Protocol):
      def put(self, *, path: str, file_obj, content_type: str) -> None: ...
      def remove(self, path: str) -> None: ...
      def exists(self, path: str) -> bool: ...
      def open(self, path: str) -> BinaryIO: ...
  ```

- **`leave/storage/supabase.py`** — `SupabaseStorageBackend`: wraps the existing SDK calls from `services/storage.py` (`create_client`, `storage.from_(BUCKET).upload/remove`). `open()` downloads the object via the SDK and returns `BytesIO`; `exists()` lists/`stat`s the object. Fail loudly with the existing "Supabase credentials are not configured" error when env vars are missing.
- **`leave/storage/development.py`** — `DevelopmentStorageBackend`: root = `settings.LEAVE_STORAGE_ROOT` (create on first use). `put` writes bytes (mkdir parents), `remove` deletes the file (unlink), `exists` checks path, `open` returns `FileIO`. Reject path traversal (`..`/absolute) in `_safe_path`.

**Delete `backend/leave/services/storage.py`** (dead after section 5) and update its only importer (`views/__init__.py`).

### 4. Model + migration (`leave/models.py`)

Extend `SupportingDocument`:

| Field | Notes |
|---|---|
| `status` | `CharField(choices=("active","retired"), default="active", max_length=10)` |
| `retired_at` | `DateTimeField(null=True, blank=True)` |
| `retired_by` | FK `settings.AUTH_USER_MODEL`, `SET_NULL`, null, blank, `related_name="+"` |
| `retire_reason` | `CharField(max_length=10, choices=("replaced","removed"), null=True, blank=True)` |
| `replaced_by` | self-FK `SET_NULL`, null, blank, `related_name="replaced_documents"` |

Add `Meta.constraints` index `(application, status)` and invert ordering to `["-uploaded_at"]` on a filtered queryset rather than the manager. Migration `0007_supporting_document_lifecycle` via `makemigrations leave`; existing rows backfill to `active` via the field default.

Storage path becomes unique per document to survive replacements of same-named files:

```
leave-documents/{application.id}/{document.id}/{sanitized file name}
```

The service generates the document UUID before upload (section 5). `file_url` is set from the view to the content-endpoint URL (section 6).

### 5. Document service (`backend/leave/services/documents.py`)

Single authoritative module for all supporting-document operations. Every function resolves the application through the owner check `application.employee == actor` (anything else → **404**, never 403 — project convention), takes the actor from the authenticated user, and runs in `transaction.atomic()`. No document/`employee_id` is ever read from the client as proof of ownership.

Helpers:

- **`document_path(application_id, document_id, file_name)`** — returns the per-document path above (name `os.path.basename`-normalised).
- **`editing_allowed(application)`** — returns True when `application.status in {"draft", "rejected", "correction_required"}` (enum-driven; see section 1). Raises `DocumentError` (409 `document_read_only`) otherwise.
- **`validate_upload_file(file)`** — trims the name, enforces `file.size <= LEAVE_DOCUMENT_MAX_SIZE_BYTES` and `content_type in LEAVE_DOCUMENT_ALLOWED_TYPES`, rejects empty/`None`. Raises `DocumentError(field, message)` mapped to 400.
- **`can_view_content(user, application)`** — True for the owner; True when `application.current_approver == user` (the Unit 9 spine). Documented seam: Unit 16/17 add approver `get_view_access` calls here.

Operations:

- **`add_document(*, application_id, actor, file)`** — gates `editing_allowed`, validates the file, generates the document UUID, `put`s bytes, saves the row (`status="active"`, `content_type` from `file.content_type`). Audit `document_uploaded`. Returns the row.
- **`remove_document(*, application_id, document_id, actor)`** — gates + ownership (document belongs to this application else 404). If `application.status == "draft"`: `remove` the stored file, delete the row (Unit 13 behavior). Otherwise: set `status="retired"`, `retired_at=now`, `retired_by=actor`, `retire_reason="removed"`; **never delete the file**. Audit `document_removed`. Storage `remove` failure in draft is logged and the row is still deleted (current Unit 13 behavior).
- **`replace_document(*, application_id, document_id, actor, file)`** — gates + ownership + validates the new file. If draft: generate new UUID + row (`active`), `put` + save, then `remove` old file + delete old row (audit `document_replaced`, metadata holds both names). If rejected/correction: generate new row (`active`) + upload; retire the old row (`retire_reason="replaced"`, `replaced_by=new_document`) and keep the old file; audit `document_replaced`. Returns the new row.
- **`get_documents(application_id, actor, *, include_retired=False)`** — owner check; `include_retired=False` returns `status="active"` only (backward compatible with Unit 13 list). `include_retired=True` returns all ordered newest-first.
- **`get_document_history(application_id, actor)`** — owner check; composes `{ active: [...], retired: [...], events: [...] }`: retired rows come from the model (with `retired_at`/`retire_reason`/`replaced_by_name`), events come from `AuditEvent` filtered by `content_type=SupportingDocument`, `object_id` in this application's document ids, `action` in `{document_uploaded, document_removed, document_replaced}`.
- **`delete_draft_documents(application)`** — used by `LeaveApplicationViewSet.perform_destroy`; `remove`s every document's file (best-effort logging) then the caller deletes the application.
- **`get_document_content(document)`** — returns `(backend.open(document.file_path), document.content_type, document.file_name)`.

All ops write audit events with `audit.services.record_event(actor=actor, action=..., target=<document or application>, prev_state=new_state=application.status, metadata={"application_id":..., "file_name":..., ...})`.

### 6. Serializers, permissions, views, routes

- **`SupportingDocumentSerializer`** — add `status`, `retired_at`, `retired_by`, `retire_reason`, `replaced_by`, `replaced_by_name` (`replaced_by.file_name`, read-only) to fields; everything stays read-only.
- **`SupportingDocumentViewSet`** is **rewritten** onto the service. Keep `parser_classes = [MultiPartParser, FormParser]`, `IsOwner`, HTTP verbs list/retrieve/create/destroy + new actions. `get_queryset` returns this application's documents filtered `status="active"` for the default list. `perform_create`/`perform_destroy` call `add_document` / `remove_document` (the service raises 409 `document_read_only` instead of the old 400 string). Add:
  - `@action(detail=True, methods=["post"], url_path="replace")` → `POST .../documents/{doc_id}/replace/` (multipart `file`) → `replace_document`, returns the new document.
  - `@action(detail=True, methods=["get"], url_path="content")` → `GET .../documents/{doc_id}/content/` → authorize via `can_view_content` (else 404), stream `FileResponse(open(...), content_type=..., as_attachment=bool(request.query_params.get("download")), filename=file_name)`.
  - `@action(detail=False, methods=["get"], url_path="history")` → `GET .../documents/history/` → `get_document_history`.
  - `@action(detail=False, methods=["get"], url_path="config")` on a **flat** `LeaveDocumentConfigView` (APIView, `IsAuthenticated`, no model) → `GET /api/v1/leave-documents/config/` returning `{ max_size_bytes, allowed_content_types }`.
- **`only-active` read rule for Unit 17/21:** retired documents never appear in default lists or download endpoints — a single `SupportingDocument.objects.filter(application=..., status="active")` queryset helper keeps this consistent everywhere.
- Routes (in `leave/urls.py`): add the `replace`, `content`, `history` actions, and `leave-documents/config/`.

### 7. Required-document validation (Unit 14 integration)

Update `validation/validators/documents.py::count_supporting_documents`:

```python
return application.documents.filter(status="active").count()
```

so a retired document never satisfies `DOCUMENT_REQUIRED`.

### 8. Audit + history

Reuse `audit.services.record_event` (already exists). Events: `document_uploaded`, `document_removed`, `document_replaced`. Store the application id and both file names in `metadata`. Nothing new in the `audit` app.

### 9. Frontend (`frontend/`)

```
frontend/
├── app/api/leave/leave-applications/[id]/documents/[docId]/content/route.ts  # GET stream (binary pass-through, ?download=1)
├── app/api/leave/leave-documents/config/route.ts                              # GET config proxy
├── lib/documents/
│   ├── types.ts          # SupportingDocumentLifecycle, DocumentHistory, DocumentsConfig, DocumentStatus
│   ├── service.ts        # replaceDocument, getDocumentHistory, contentUrl(), getDocumentsConfig,
│   │                     #   uploadDocument/deleteDocument wrappers over lib/leave-api
│   └── config.ts         # client-safe, server-driven limits
└── components/leave/
    ├── SupportingDocumentsUploader.tsx   # EXTENDED (below); keep the name — no duplicate component
    ├── document-list.tsx                 # read-only list w/ View/Download (reused by ReviewSummary,
    │                                     #   tracker, approvals documents card)
    └── document-history-timeline.tsx     # retired list + replacement chain/audit events
```

- **`SupportingDocumentsUploader`** gains props `mode: "editable" | "readonly"` and `onDocumentReplaced?`. Editable renders the dropzone + per-row **Replace** (file input) and **Remove**; readonly renders rows with **View** / **Download** only. Limits come from `getDocumentsConfig()` (`max_size_bytes`, allowed types) shown as the hint line and enforced client-side as a UX pre-check — the server remains authoritative. Replace optimistically toggles the row to "Replacing…", then replaces local state with the server response (no speculative state beyond pending flags). 409 `document_read_only` renders a banner.
- **`document-list.tsx`** — read-only list: file icon, name, formatted size, uploaded date (`Africa/Blantyre`), View (`Eye`) and Download (`Download`) opening `contentUrl(...)`/`contentUrl(..., download=true)` in a new tab (`noopener,noreferrer`).
- **`document-history-timeline.tsx`** — renders `DocumentHistory`: active files, then retired files with retire reason ("Replaced by {name}" / "Removed") + retired date, then recent audit events (action label + ISO time). Collapsible. Used inside editable sections (draft/resubmission forms) and, read-only, on the tracker.
- **`content/route.ts`** — unlike the JSON `proxy.ts`, this handler fetches Django, forwards the status + `content-type`/`content-disposition` headers and returns `new Response(res.body, { status, headers })`.
- Wire-in: `ReviewSummary`'s "attached documents" list becomes `document-list` (adds View/Download); the draft form keeps the extended uploader (editable, draft mode); the Unit 15 tracker documents block and Unit 16's `documents-card` swap to `document-list` where merged.
- Date/size formatting reuses `lib/tracking/format.ts` where convenient; no new date library.

### 10. Development data

No new seed command. Extend verification instead: wherever Unit 13 fixtures/seed applications exist, one draft with two documents and one replacement is enough to exercise the dev backend locally (`storage/leave-documents/…`). Keep the existing post-Submit seeding (Unit 16 `seed_approvals_dev`) untouched.

### 11. Tests

**Backend (Django `TestCase`)**
- Storage: dev backend put/remove/exists/open round-trip against a temp `LEAVE_STORAGE_ROOT`; Supabase backend mocked (`create_client`) for put/remove/open/credentials-missing error; path-traversal rejection.
- Factory: `get_storage_backend()` returns the class named by `LEAVE_STORAGE_BACKEND` (settings swap test, mirroring `test_tracking_provider`).
- Service ops: add/replace/remove per status; draft replace physically deletes old file + old row; rejected/correction replace retires old file/row and keeps the file; remove in draft deletes, post-submission retires.
- Read-only gate: upload/replace/remove in `submitted`/`pending`/`approved`(+/`cancelled` if present) → 409 `document_read_only`, no storage, no DB change.
- Ownership: another employee, an approver, and anonymous users → 404/401 on every document endpoint; `employee_id`/foreign `document_id` in a request never affects another application.
- Validation: over-limit size and disallowed content-type → 400; allowed types pass; `DOCUMENT_REQUIRED` counts active documents only (retired docs don't satisfy it).
- Content: owner streams bytes with correct `content-type`/`Content-Disposition`; `?download=1` sets `attachment`; `can_view_content` grants `current_approver`; foreign/unapproved → 404; retired documents excluded from default list and content.
- History: `get_document_history` composes active/retired/events correctly after add → replace → remove (draft and rejected paths); exactly one audit event per op with actor and metadata.
- Migration: existing rows default to `active`; model `Meta` index present.
- Config: `GET /leave-documents/config/` returns the settings values; 401 unauthenticated.

**Frontend (Vitest + React Testing Library)**
- Uploader: editable vs readonly rendering; Replace/Remove actions call `replaceDocument`/`deleteDocument` and update from the response; 409 shows the read-only banner; limits hint from config; disabled states while pending.
- Readonly list: View/Download links use `contentUrl` (with and without `download`); file name/size/date render; empty state.
- History timeline: active list, retired rows with "Replaced by" / "Removed", event list; hidden when history is empty.
- Proxy content route: streams status/headers/body through (unit-test the handler with a stubbed `fetch`).

### 12. Documentation updates

- `architecture.md` §4.3/§5.2 and the §13 decision table: record the storage **development implementation decision** (local-filesystem backend behind a `LEAVE_STORAGE_BACKEND` abstraction; production storage remains TBD) and remove the storage-in-vacuum wording that contradicts it. §5.2 note: database keeps `file_path`/`file_url` metadata only.
- Root `README.md` API table: add `…/documents/{id}/replace/`, `…/documents/{id}/content/`, `…/documents/history/`, `…/documents/config/` rows.
- `context/progress-tracker.md`: mark Unit 19 spec drafted + the four confirmed decisions, and note it as the next unit after 18.

## Dependencies

- **Backend:** no new packages. `supabase` stays (behind the abstraction); the development backend is pure stdlib. Django/DRF/Postgres as-is.
- **Frontend:** no new packages — extends the existing `SupportingDocumentsUploader`; uses existing `lucide-react` and Tailwind. Note: the 21st.dev/Radix dependency called for in earlier specs was never installed for the approvals UI (Unit 16), whose `Dialog`/`Tabs`/`Textarea` primitives were hand-rolled in `components/ui/`; follow that same approach here.
- **Unit dependencies:**
  - Unit 13: `SupportingDocument` model, serializer, uploader, storage seams (now abstracted).
  - Unit 14: `validation/validators/documents.py` (active-only count).
  - Unit 16/17: status enum values `rejected`/`correction_required`/`pending`/`approved` — required for the full editable gate; implemented against the enum so it activates when those merge.
  - Units 2–11: consumed only through existing providers/settings until Unit 20 (`current_approver` spine is the only cross-track read, already merged).

## Verification checklist

### Storage abstraction
- [ ] `get_storage_backend()` returns the class named by `LEAVE_STORAGE_BACKEND`; swapping `supabase`/`development` needs no document-logic change.
- [ ] With `LEAVE_STORAGE_BACKEND` = development, upload/download works end-to-end with no Supabase credentials and files appear under `<repo>/storage/leave-documents/…`.
- [ ] Supabase backend rejects upload with the clear "credentials not configured" error when env vars are missing.
- [ ] Path traversal in a file name cannot escape the storage root.

### Lifecycle operations
- [ ] Upload works in `draft`, `rejected`, and `correction_required`.
- [ ] Views/downloads work from any state via `content/` (`inline`) and `content/?download=1` (`attachment`), preserving content type and original filename.
- [ ] Replace during draft: new active row replaces the old; old file + row are deleted; storage holds no orphan.
- [ ] Replace after rejection/correction: old row is `retired` (`retire_reason=replaced`, `replaced_by` set), old file kept; new row active.
- [ ] Remove during draft deletes; remove after submission retires (file kept).
- [ ] Upload/replace/remove are rejected (409 `document_read_only`) in `submitted`/`pending`/`approved` and, where present, `cancelled`.
- [ ] Retired documents appear in `history/` but never in default lists, and `content/` refuses them to everyone.

### Required-document validation
- [ ] `DOCUMENT_REQUIRED` fires when the leave type requires a document and only retired documents exist (active count = 0).
- [ ] A single active document satisfies the rule.

### Authorization
- [ ] Owner, or any `can_view_content` grantee (`current_approver` today), can stream content; everyone else gets 404.
- [ ] Foreign application/document ids and anonymous requests return 404/401; `employee_id`/`document_id` from the body is ignored.
- [ ] The frontend's read-only/editable rendering never bypasses the backend gate (verified by direct API calls).

### History and audit
- [ ] The `history/` payload shows active, retired (with chain/reason/date), and the audit events for each op.
- [ ] `document_uploaded` / `document_removed` / `document_replaced` events carry actor, application id, and file names.
- [ ] No new history model was added; state + audit events only.

### Frontend
- [ ] The uploader renders editable vs read-only according to state; Replace/Remove appear only when editable.
- [ ] View/Download open the content proxy in a new tab and show a clear failure state on error.
- [ ] Limits (10 MB, allowed types) render from the backend config endpoint and are mirrored as the hint line.
- [ ] The history timeline renders correctly incl. the read-only use on the tracker; empty state handled.

### Quality
- [ ] Loading, success, empty, error, 400/404/409 states handled; prior Unit 13 upload/remove behavior preserved for drafts.
- [ ] All backend and frontend tests listed in section 11 pass; `manage.py check`, `makemigrations --check`, `npm run lint`, `tsc --noEmit`, and `npm run build` pass.
- [ ] Architecture, README API table, and progress-tracker updated as specified in section 12.