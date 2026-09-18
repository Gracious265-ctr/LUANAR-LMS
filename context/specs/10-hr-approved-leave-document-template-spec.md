# Unit 10 — HR Approved Leave Document Template

## Goal

Create HR's management experience for the one official approved-leave document
template (build-plan §4, Unit 10):

- Official template.
- Logo/branding (as text; see assumptions).
- Official wording.
- Fields.
- Signature areas.
- Layout configuration.
- Template preview.
- Template update.

HR may customize the template but must never alter actual approved application
data through the template system.

## Assumptions made (flag if wrong)

- **Domain home: the `documents` app.** architecture.md assigns the `documents`
  app "Approved leave document generation". Unit 10 builds the *template
  configuration* this app owns; the renderer that fills it with a real approved
  application is Unit 23. The template is configuration, not a document.

- **One official template (singleton).** project-overview.md says "one official
  leave-document template" and "Allow HR to customize one official
  leave-document template". There is exactly one row. No list/create/delete, no
  multiple templates, no version history (audit is Unit 24).
  API: `GET`/`PATCH` on the singleton — an `APIView` pair (no `{pk}` detail
  routes), which is the smallest contract for a singleton and a documented
  divergence from the `ViewSet` CRUD used for list-shaped resources.

- **Branding is text only in V1.** Uploading a logo/emblem requires the
  file-storage infrastructure that architecture.md marks TBD. The template's
  branding is therefore a header **text** field (e.g. the university name).
  Image/logo upload is deferred to the unit that owns the storage decision —
  the same reasoning that kept public-holiday and document-storage sources TBD.

- **The field set is fixed; values are never stored in the template.** The
  approved-leave document's data rows come from the approved application record
  (code-standards: "Template customization must modify presentation only",
  "Generated documents must contain the correct employee, leave, approval, and
  balance information"). The template therefore stores a *field catalog* where
  HR controls each row's **label**, **inclusion**, and **order** but never a
  value. The catalog keys are fixed and owned by this unit:

  | key            | default label |
  |----------------|---------------|
  | reference      | Reference     |
  | employee_name  | Employee      |
  | employee_grade | Grade         |
  | designation    | Designation   |
  | department     | Department    |
  | leave_type     | Leave type    |
  | start_date     | Start date    |
  | end_date       | End date      |
  | working_days   | Working days  |
  | request_reason | Reason        |

- **`fields` and `signature_areas` are validated JSON columns, not relational
  inline rows.** Ordering and optionality here are light config for one
  singleton; a relational `TemplateField`/`TemplateSignature` join (like
  `WorkflowStage`) would triple the models/serializers/inline formsets for no
  behavior gain. Server-side validation enforces the same invariants a formset
  would (valid keys, unique keys, non-empty labels). Documented divergence.

- **Field catalog is backend-owned and served to the frontend.** The catalog
  (key, default label, preview sample) lives once in `documents/services.py` and
  is returned as read-only `available_fields` on the template resource, so the
  frontend never duplicates keys/labels/samples.

- **Preview is a presentation mock driven by the editor form.** Rendering the
  configured document with *sample* values so HR sees layout/labels live while
  editing. This is a client-side React component; there is no separate backend
  preview endpoint (a stored-block contract would be dead weight — Unit 23 owns
  the authoritative render with real application data). By definition there is
  no approved application data to render yet.

- **Default template materializes on first access.** A `get_or_create` in
  `documents/services.py` returns an editable default (all catalog fields at the
  defaults above, one Employee + one Registrar signature area) when none exists
  yet. No change to `seed_dev_users`; no data migration. If the singleton is
  later reset, HR edits in place.

- **HR-only.** Template management is HR administration (Unit 2 `IsHRRole`).
  No notifications (Unit 22) and no audit records (Unit 24) are introduced.

## Visible result

An HR document-template page under HR administration: HR sees the current
official template, edits the official wording, the field labels/inclusion/order,
and the signature areas, and sees a live preview of the configured document —
all saved through the API proxy.

## Dependencies

- Unit 2 (`IsHRRole`, HR-only view patterns, proxy conventions, seed infra).
- Units 3–4 (serializer validation conventions, split server-safe/client-safe
  lib pattern, table/form component conventions).
- The `documents` app is already registered in `INSTALLED_APPS`.

## API contract

Namespace: `/api/v1/leave-document-template/`. Authentication required; HR-only.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/leave-document-template/` | Retrieve the single template configuration plus the read-only field catalog |
| PATCH | `/api/v1/leave-document-template/` | Update wording, field labels/inclusion/order, signature areas |

Object shape (snake_case, DRF conventions):

```json
{
  "title": "APPROVED LEAVE",
  "header": "LILONGWE UNIVERSITY OF AGRICULTURE AND NATURAL RESOURCES",
  "intro": "This is to certify that the under-listed employee has been granted the following leave:",
  "fields": [
    { "key": "employee_name", "label": "Employee" },
    { "key": "reference", "label": "Reference" }
  ],
  "closing": "The approved leave is granted subject to the university leave regulations.",
  "signature_areas": [
    { "label": "Employee signature" },
    { "label": "For: Registrar" }
  ],
  "footer": "LUANAR",
  "available_fields": [
    { "key": "reference", "label": "Reference", "sample": "LV-2026-000123" }
  ],
  "updated_at": "2026-09-17T12:00:00Z"
}
```

`available_fields` is read-only and identical on every response (GET and PATCH);
it is ignored on input.

Validation summary:

- `title` required, trimmed, non-empty, ≤ 200 chars.
- `header`, `intro`, `closing`, `footer` optional, trimmed, ≤ their field bounds.
- `fields` required, non-empty, ≤ catalog size; each row `key` must be a catalog
  key and unique; `label` trimmed and non-empty. Order in the array is document
  order.
- `signature_areas` optional list, ≤ 8 rows; each `label` trimmed and non-empty;
  order preserved. No role catalog is invented — the caption text is the
  configuration; Unit 23 prints the actual signer.

Errors follow Unit 1 conventions (`{"field": ["..."]}`).

## Implementation

Work backend first; verify before frontend work begins.

### 1. Service (`documents/services.py`)

- `FIELD_CATALOG: list[dict]` — the one authoritative definition of the fixed
  data fields as `{key, label, sample}` (sample is presentational preview data;
  the frontend consumes the catalog from the API).
- `ALLOWED_FIELD_KEYS` and `DEFAULT_FIELDS` derived from `FIELD_CATALOG`.
- `max` bounds shared with the serializer (text length, signature-area count).
- `get_template() -> LeaveDocumentTemplate` — `get_or_create` the singleton with
  the default configuration (all catalog fields at default labels + two default
  signature areas). Documented as the place a future "reset" would write.

### 2. Model (`documents/models.py`)

- `LeaveDocumentTemplate` (singleton; `id` PK used only by admin/ORM):
  - `title` `CharField(max_length=200)`.
  - `header` `TextField(blank=True)`.
  - `intro` `TextField(blank=True)`.
  - `fields` `JSONField(default=list)` (ordered `{key, label}` rows).
  - `closing` `TextField(blank=True)`.
  - `signature_areas` `JSONField(default=list)` (ordered `{label}` rows).
  - `footer` `TextField(blank=True)`.
  - `created_at`/`updated_at` auto timestamps; `Meta.ordering = ["-updated_at"]`
    isn't meaningful for a singleton — omit.
  - `__str__` returns the title.
- Migration `0001_initial` via `makemigrations documents`.

### 3. Serializer + views (`documents/serializers.py`, `documents/views.py`)

- `LeaveDocumentTemplateSerializer` (ModelSerializer over the service
  constants): applies the validation summary, exports read-only
  `available_fields` (the catalog) on every response. `updated_at` read-only.
- `LeaveDocumentTemplateView(APIView)` — `permission_classes =
  [IsAuthenticated, IsHRRole]`; `get` returns the serializer over
  `get_template()`; `patch` runs `is_valid` → partial update.
- `documents/urls.py` + route registration in `config/urls.py`
  (`path("api/v1/", include("documents.urls"))`).

### 4. Admin (`documents/admin.py`)

- Register `LeaveDocumentTemplate` as a fully view-only inspector: every field
  read-only (the app UI is the management surface), no add/change/delete.

### 5. Seed

- No changes. The default template materializes on first access.

### 6. Frontend

- `lib/leave-document-template.ts` (server-safe): `AvailableField`,
  `LeaveDocumentTemplate`, `TemplateField`, `TemplateSignatureArea` types and
  `getLeaveDocumentTemplate()` (read via `apiClient`). Catalog keys/labels/
  samples come from the response's `available_fields`.
- `lib/leave-document-template-client.ts` (client-safe):
  `updateLeaveDocumentTemplate(input)` PATCHing
  `/api/hr/leave-document-template` — split exactly like `workflows` so the form
  never pulls `next/headers` into the bundle.
- Route-handler proxy: `/api/hr/leave-document-template/route.ts` PATCH.
- Components under `components/hr/`:
  - `leave-document-template-editor.tsx` (client): loads the template, edits
    title/header/intro/closing/footer, edits the ordered field list
    (add/remove/reorder/edit label, key fixed from `available_fields`), edits
    signature areas (add/remove/reorder/edit label), saves via the proxy showing
    backend errors in the standard error block, and renders a live preview from
    current form state on the right.
  - `document-template-preview.tsx` (client): renders the document from the
    current form state, using the catalog's `sample` values + the configured
    order/labels.
- Page under `app/(dashboard)/dashboard/hr-admin/leave-document-template/`:
  `page.tsx` guarding with `getCurrentUser()` → `/login` and
  `user.role !== "hr"` → `/dashboard`, server-fetches the template into the
  editor.
- Add a sidebar item ("Document Template", lucide `FileText`) and an HR index
  card; update the HR index footer note (template is now built; remaining
  HR-track items are later units that need applications).

### 7. Tests

- `backend/documents/tests.py`: service `get_template` default shape +
  idempotency; serializer validation (missing/blank title, invalid/duplicate
  field key, blank field label, empty fields, ordering preserved); endpoint 401
  unauthenticated, non-HR 403, GET default + `available_fields`, PATCH update
  round-trip, values never stored; admin all-read-only and no add/change/delete.
- Frontend: `leave-document-template-editor.test.tsx` (renders saved config,
  edits label, add/remove/reorder field and signature rows, save shape from the
  client lib, backend error rendering), `document-template-preview.test.tsx`
  (renders catalog sample values, configured order/labels, signature captions).

### 8. Docs

- `context/specs/10-hr-approved-leave-document-template-spec.md` (this file).
- `context/progress-tracker.md`: Unit 10 complete; note Unit 9 deferred until
  applications exist, and the formatting decisions above.
- Root `README.md` API table: add the `/api/v1/leave-document-template/` rows
  and drop "documents" from the HR-area later-units phrasing if present.

## Verification

- `uv run manage.py test --noinput` green.
- `npm test` green, `npm run lint` and `npm run build` green.
- `npm run dev` against a seeded backend: HR opens the Document Template page
  (default template shown), edits a field label, adds a signature area, sees the
  preview update, saves, reloads (changes persist), non-HR is redirected.

## Implementation notes (2026-09-17)

- **Unit 9 deferred by project decision.** HR Emergency Reassignment operates on
  pending applications, which do not exist until Unit 13+ (consumed in Unit 21).
  The developer chose to build Unit 10 next; Unit 9 resumes once application
  rows exist. progress-tracker documents the reorder.
- Singleton `APIView`; approved application data is never stored or edited in
  the template (label/inclusion/order only).
- Branding is header *text*; logo image upload waits for the storage decision.
- One authoritative `FIELD_CATALOG` in `documents/services.py`, served as
  `available_fields`; an earlier draft duplicated keys/labels/samples in the
  frontend and exposed a backend `preview/` endpoint that nothing consumed —
  both were removed in review (client-side preview only).