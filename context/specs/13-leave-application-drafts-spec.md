# Unit 13 — Leave Application and Drafts

read `context/AGENTS.md` before starting.

## Goal

Build the complete employee-facing leave application flow — create/edit/delete multiple drafts, auto-calculated leave days, supporting-document upload, and a review-then-submit step — with the backend as the sole source of truth for calculated days and submission state, so an employee can draft an application over several sessions and submit it with a system-generated reference number.

---

## Design

### Scope boundary (explicit)

Unit 13 ends at **Submitted**. It does **not**:
- Route the application to an approver, or trigger any notification.
- Validate against leave-type eligibility rules, balances, notice periods, or financial-year boundaries — those are Unit 4/5 concerns and are explicitly deferred (see "Deferred integrations" below).
- Implement the approval/workflow state machine beyond `draft` → `submitted`.

This keeps the unit shippable and testable in isolation, with clearly marked seams for later units to plug into.

### Deferred integrations (Units 4 & 5)

Unit 4 (leave-type API) and Unit 5 (calendar/rule API) don't exist yet. Rather than blocking on them, Unit 13 introduces a **service-layer boundary** on the frontend:

- `frontend/lib/services/leaveTypes.ts` — exports `getLeaveTypes(): Promise<LeaveType[]>`. Currently returns a hardcoded mock array.
- `frontend/lib/services/calendarRules.ts` — exports `previewWorkingDays(startDate, endDate, leaveTypeId): Promise<{ days: number }>`. Currently calls the backend's own stub calculation (see below) — not a frontend-only mock, because working-day math must stay authoritative on the backend per the architecture's backend-authority invariant.

When Unit 4/5 land, only the **inside** of `getLeaveTypes()` changes (mock array → real `fetch` call). Every component (`LeaveTypeSelect`, the form, the review page) calls the function, never the mock data directly, so nothing else changes.

On the backend, since there's no real `LeaveType` model yet, `LeaveApplication.leave_type_id` is stored as a **plain integer with no foreign key constraint** — a soft reference. This is a known, documented gap: once Unit 4 ships a real `LeaveType` model, a follow-up migration adds the FK and backfills/validates existing rows. This is called out explicitly in code comments and in this spec so it isn't forgotten.

Working-day calculation on the backend is implemented as an isolated function `leave/services/working_days.py::calculate_working_days()`. It excludes weekends (Sat/Sun) **and configured public holidays**, reading them through the configured `LEAVE_RULES_PROVIDER` (`get_public_holidays`) and delegating the counting itself to the validation pipeline's `leave/validation/working_days.count_working_days()`. There is therefore exactly one counting rule in the product: this entry point for drafts and the preview endpoint, and the pipeline for submission/resubmission. (It shipped weekend-only in Unit 13 as a labeled stub; Unit 5 supplied the holiday source.)

### Application lifecycle (this unit)

```
Draft ──(edit/save)──> Draft
Draft ──(submit)──> Submitted (reference number generated, immutable from here)
Draft ──(delete)──> [removed]
```

Once `submitted`, an application and its documents become read-only. No edit/delete/resubmit logic is built in this unit (resubmission after rejection is a later unit's concern).

### Form flow (structural)

Single shared form component used for both "new" and "edit draft", followed by a separate review step:

1. **`/leave/new`** and **`/leave/[id]/edit`** — both render `<LeaveApplicationForm />`. On "new", first interaction creates a draft immediately (see "Draft creation timing" below) so the draft list is never out of sync with what the user has started.
2. **`/leave/drafts`** — list of the employee's own drafts (status = `draft`), each with Edit / Delete / Continue-to-Review actions.
3. **`/leave/[id]/review`** — read-only summary of a draft (leave type, dates, calculated days, reason, documents), with a **Submit** button. This is the only place that calls the submit endpoint.

**Draft creation timing**: rather than creating a draft only on an explicit "Save Draft" click (which risks losing work on a first-time form if the user navigates away before clicking it), the form creates an empty draft on first field blur/change (debounced autosave), then every subsequent change is a `PATCH`. This directly serves "multiple drafts" — a user who starts several applications without finishing any of them will see all of them in `/leave/drafts`.

### Leave days field

The days field is **always** derived, never an `<input>`. It's a read-only display driven by `previewWorkingDays()`, recalculated whenever start date, end date, or leave type changes. The same value is recomputed and persisted server-side on every save — the frontend never sends a day count to the backend.

### Visual/component notes

- Use existing 21st.dev form primitives and Tailwind tokens from `ui-context.md` (LUANAR blue `#0097F0` for primary actions, institutional green for the "Submit" success state, Inter font, Lucide icons — `CalendarDays`, `FileText`, `Trash2`, `Upload`, `CheckCircle2`).
- Drafts list: card layout, one card per draft, showing leave type (or "Leave type not selected" placeholder), date range, calculated days, and a relative "last edited" timestamp.
- Document uploader: dropzone-style component, shows filename/size, upload progress, and a remove control (removal disabled once submitted).
- Review page: read-only summary sections mirroring the form's sections, plus a persistent "Edit" link back to the form for each section, and the Submit button pinned at the bottom.

---

## Implementation

### 1. Backend — `leave` app models

```python
# backend/leave/models.py
import uuid
from django.db import models
from django.conf import settings

class LeaveApplication(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="leave_applications")

    # Soft reference — no FK until Unit 4 ships a real LeaveType model.
    # TODO(unit-4): replace with FK to LeaveType once available; add migration to validate existing rows.
    leave_type_id = models.PositiveIntegerField(null=True, blank=True)

    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    calculated_days = models.PositiveIntegerField(null=True, blank=True)  # backend-computed only
    reason = models.TextField(blank=True, default="")

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    reference_number = models.CharField(max_length=32, unique=True, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]


class SupportingDocument(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(LeaveApplication, on_delete=models.CASCADE, related_name="documents")
    file_path = models.CharField(max_length=512)   # Supabase storage object path
    file_url = models.URLField()                    # public/signed URL
    file_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField()
    content_type = models.CharField(max_length=100)
    uploaded_at = models.DateTimeField(auto_now_add=True)
```

### 2. Backend — working-days entry point

```python
# backend/leave/services/working_days.py
def holidays_in_range(start, end, provider=None) -> dict[date, str]:
    """Public holidays in the inclusive range, via the configured rules provider."""
    ...

def calculate_working_days(start_date, end_date, *, holidays=None, provider=None) -> int:
    """Weekends and configured public holidays are not working days.

    Delegates to leave.validation.working_days.count_working_days so the draft
    preview and the validation pipeline can never disagree.
    """
    if start_date is None or end_date is None or end_date < start_date:
        return 0
    if holidays is None:
        holidays = set(holidays_in_range(start_date, end_date, provider))
    return count_working_days(start_date, end_date, holidays)
```

`calculated_days` (this unit) and `working_days` (Unit 14, frozen at submission)
are both written from this one rule, so the two columns on an application row
cannot drift apart; the only intended difference is that `working_days` is
frozen at submission and ignores holidays HR configures afterwards.

### 3. Backend — serializers, permissions, viewset

- `LeaveApplicationSerializer`: exposes all fields; `calculated_days`, `status`, `reference_number`, `employee` are **read-only** on write.
- `IsOwner` permission: `request.user == obj.employee`. Applied to every action — never trust a client-supplied employee ID (architecture invariant 12.2).
- `LeaveApplicationViewSet` (DRF `ModelViewSet`, scoped to `self.request.user.leave_applications`):
  - `perform_create`: sets `employee=request.user`, `status=draft`.
  - `perform_update`: **reject** (400) if `instance.status != draft` — submitted applications are immutable in this unit.
  - On create/update, if both `start_date` and `end_date` are present, recompute `calculated_days` via `calculate_working_days()` and store it — the frontend never sends this value, and if it does, it's ignored. Because the column is denormalized, a change to the holiday calendar must also refresh it: `leave/holiday_refresh.py` (wired in `LeaveConfig.ready()`) re-counts the `draft` / `correction_required` applications whose range covers a newly configured public holiday, on both `pre_save` (to remember a moved holiday's old date) and `post_save`. It is a `post_save` receiver rather than view logic so the Django admin and the HR endpoint are both covered. Submitted and approved applications are never recounted (invariant 12.5).
  - `destroy`: **reject** (400) if `instance.status != draft`.
  - Custom action `POST /leave-applications/{id}/submit/`:
    - 400 if already submitted, or if `leave_type_id`/`start_date`/`end_date`/`reason` are missing (minimal completeness check — real eligibility/balance/notice-period validation is out of scope, deferred to Unit 4/5 integration).
    - Generates `reference_number` (format: `LUANAR-{YYYY}-{5-digit sequence}`, sequence derived from a simple per-year counter — e.g. a small `ReferenceSequence` model or `select_for_update` counter row to avoid race conditions).
    - Sets `status=submitted`, `submitted_at=now()`.
  - Custom action `POST /leave-applications/preview-days/` (no instance required): accepts `start_date`, `end_date` in the request body, returns `{ "days": <int>, "holidays_excluded": <int> }` via `calculate_working_days()` — `days` excludes weekends and configured public holidays, and `holidays_excluded` says how many public holidays were dropped so the UI can explain the number. Used by the frontend for live preview before a draft necessarily has both dates saved.

- `SupportingDocumentViewSet` (nested under application, or a flat viewset filtered by `application_id`):
  - `create`: reject if parent application isn't `draft`. Accepts multipart upload, uploads to Supabase Storage (see below), then creates the `SupportingDocument` row.
  - `destroy`: reject if parent application isn't `draft`. Deletes both the Supabase object and the DB row.

### 4. Backend — Supabase Storage integration

- Add `supabase` (or `storage3`) as a backend dependency.
- `backend/leave/services/storage.py`:
  ```python
  from supabase import create_client
  from django.conf import settings

  def get_supabase_client():
      return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)

  def upload_document(file, application_id: str) -> dict:
      client = get_supabase_client()
      path = f"leave-documents/{application_id}/{file.name}"
      client.storage.from_(settings.SUPABASE_BUCKET).upload(path, file.read(), {"content-type": file.content_type})
      url = client.storage.from_(settings.SUPABASE_BUCKET).get_public_url(path)
      return {"path": path, "url": url}

  def delete_document(file_path: str) -> None:
      client = get_supabase_client()
      client.storage.from_(settings.SUPABASE_BUCKET).remove([file_path])
  ```
- Settings additions (`backend/config/settings.py`), sourced from env vars so you can drop in real values later:
  ```python
  SUPABASE_URL = env("SUPABASE_URL", default="")
  SUPABASE_SERVICE_KEY = env("SUPABASE_SERVICE_KEY", default="")
  SUPABASE_BUCKET = env("SUPABASE_BUCKET", default="leave-documents")
  ```
- If the env vars are empty, uploads should fail loudly with a clear error (not silently no-op) so it's obvious in dev that keys are missing.
- Bucket access: private bucket, signed URLs generated per-request rather than a permanently public URL, since supporting documents may contain sensitive info (medical notes for compassionate/maternity leave, etc.). Adjust `get_public_url` call above to `create_signed_url` if you want this from day one — flagging as a decision point rather than assuming.

### 5. Frontend — service layer (mocked, swappable)

```typescript
// frontend/lib/services/leaveTypes.ts
export interface LeaveType {
  id: number;
  name: string;
  requiresDocuments: boolean;
  maxDurationDays: number | null;
}

export async function getLeaveTypes(): Promise<LeaveType[]> {
  // TODO(unit-4): replace with fetch('/api/leave-types/')
  return [
    { id: 1, name: "Annual Leave", requiresDocuments: false, maxDurationDays: null },
    { id: 2, name: "Maternity Leave", requiresDocuments: true, maxDurationDays: 90 },
    { id: 3, name: "Paternity Leave", requiresDocuments: true, maxDurationDays: 14 },
    { id: 4, name: "Compassionate Leave", requiresDocuments: true, maxDurationDays: 7 },
  ];
}
```

```typescript
// frontend/lib/services/calendarRules.ts
export async function previewWorkingDays(startDate: string, endDate: string): Promise<{ days: number }> {
  const res = await fetch("/api/leave-applications/preview-days/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ start_date: startDate, end_date: endDate }),
  });
  if (!res.ok) throw new Error("Failed to calculate working days");
  return res.json();
}
```

### 6. Frontend — data hooks

- `useLeaveApplications()` — fetches the current user's applications; supports filtering by status client-side for the drafts list.
- `useLeaveApplication(id)` — fetches one application + its documents.
- `useAutosaveDraft(application, patchFn)` — debounced (~800ms) autosave hook used by the form; exposes a `saveStatus: 'idle' | 'saving' | 'saved' | 'error'` for a small inline indicator near the form.
- Plain `fetch` wrappers, no new data-fetching library — keeps this unit's footprint small since nothing like SWR/React Query is already in the stack.

### 7. Frontend — pages & components

```
frontend/app/dashboard/leave/
├── new/page.tsx              → renders <LeaveApplicationForm mode="create" />
├── [id]/edit/page.tsx        → renders <LeaveApplicationForm mode="edit" applicationId={id} />
├── [id]/review/page.tsx      → renders <ReviewSummary applicationId={id} /> + Submit button
└── drafts/page.tsx           → renders <DraftsList />

frontend/components/leave/
├── LeaveApplicationForm.tsx
├── LeaveTypeSelect.tsx
├── DateRangeFields.tsx
├── WorkingDaysPreview.tsx     → read-only, calls previewWorkingDays()
├── SupportingDocumentsUploader.tsx
├── DraftsList.tsx
├── DraftCard.tsx
└── ReviewSummary.tsx
```

- `LeaveApplicationForm`: on first meaningful interaction (leave type selected, or a date picked, or reason typed), if no draft exists yet, `POST` to create one and store the returned `id` in local state / URL (redirect `new` → `[id]/edit` after first save, so a refresh doesn't lose the draft). Every subsequent change flows through the autosave hook.
- `SupportingDocumentsUploader`: disabled until a draft exists (can't attach a file to nothing); shows `LeaveType.requiresDocuments` as a hint/required-marker but does not hard-block submission on it in this unit (that eligibility enforcement is deferred, matching the scope boundary above).
- `ReviewSummary`: pure read-only rendering of a fetched application; the Submit button calls `POST /leave-applications/{id}/submit/` and, on success, redirects to a confirmation state showing the reference number.
- `DraftsList` / `DraftCard`: Edit (→ edit page), Delete (confirm dialog → `DELETE`, refetch list), Continue to Review (→ review page, disabled with a tooltip if required fields are missing).

---

## Dependencies

**Backend (add to `pyproject.toml` via `uv add`):**
- `supabase` — Supabase Python client for Storage upload/delete/signed URLs.

**Frontend (add via `npm install` in `frontend/`):**
- `date-fns` — date formatting/comparison for the form and drafts list (lighter than pulling in a full calendar library for what's needed here).
- `react-dropzone` — drag-and-drop file input for `SupportingDocumentsUploader` (skip this if a 21st.dev component already covers file upload — check the component library first before adding it).

No new backend web framework or auth dependencies — reuses Unit 1's DRF setup and auth.

---

## Verification Checklist

**Drafts**
- [ ] Starting a new application without finishing it creates a draft, visible in `/leave/drafts` after navigating away.
- [ ] A user can have multiple simultaneous drafts.
- [ ] Editing a draft's fields persists via autosave (verify with a page refresh mid-edit).
- [ ] Deleting a draft removes it and its documents (DB row + Supabase object).
- [ ] A draft belonging to another employee is not visible or editable (403/404, not just hidden in UI).

**Leave days calculation**
- [ ] There is no manual input for number of days anywhere in the UI.
- [ ] Changing start or end date updates the displayed day count without a full page reload.
- [ ] The day count excludes Saturdays and Sundays.
- [ ] The value stored in the database matches what the backend computed, not anything sent from the client (test by attempting to POST a bogus `calculated_days` value and confirming it's ignored).

**Documents**
- [ ] A file can be uploaded to a draft and appears in the list with correct name/size.
- [ ] A file can be removed from a draft.
- [ ] Upload/removal is blocked once the application is submitted.
- [ ] Uploaded files are retrievable via the stored URL (once real Supabase keys are configured).

**Review & submission**
- [ ] Review page shows leave type, dates, calculated days, reason, and documents matching what was saved.
- [ ] Submitting generates a unique, correctly formatted reference number.
- [ ] After submission, the application is read-only: edit/delete/document-upload attempts are all rejected server-side.
- [ ] Submitting a second time on the same application is rejected.
- [ ] Submitting with missing required fields (leave type, dates, reason) is rejected with a clear error.

**Integration seams (for future units)**
- [ ] `getLeaveTypes()` is the only place leave-type data is read from on the frontend — no component hardcodes the mock list itself.
- [ ] `calculate_working_days()` is the only backend entry point that computes day counts outside the validation pipeline, and it excludes weekends **and** configured public holidays — no duplicate calculation rule anywhere.
- [ ] A public holiday set in the `PublicHoliday` table reduces the draft `calculated_days`, the `preview-days` response, the frozen `working_days`, and the balance deduction by the same amount.
- [ ] Setting a public holiday after a draft was saved updates that draft's stored `calculated_days` without the employee re-saving it, and never touches a submitted or approved application.
- [ ] `leave_type_id` has no FK constraint yet, and this is documented in the model with a `TODO(unit-4)` comment.
