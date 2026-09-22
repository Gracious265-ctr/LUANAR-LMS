# Unit 17 — Rejection, Correction, and Resubmission

## Goal

Let an employee whose application was **rejected** or **returned for correction** read the approver's comment, edit the application (including its documents), and resubmit it under the **same reference number** so it returns to the **same stage and approver** — where the approver sees exactly what changed before deciding again.

---

## Design

### Visual and structural decisions

Follow `ui-context.md` tokens and the existing dashboard shell (light and dark mode). LUANAR blue `#0097F0` is used for primary actions and focus; status colours come from the existing tokens (Rejected = red, Correction Required = purple, Pending = orange, Approved = green). No gradients, flat shadows only, Inter, Lucide icons only, 21st.dev components, `radius-xl` cards. Dates are shown in `Africa/Blantyre` and transmitted as UTC ISO strings.

### Employee — tracker page (`/applications/[id]`, Unit 15)

Additions only; the tracker remains display-only.

- When status is **Rejected** or **Correction Required**, a **feedback banner** sits directly under the header:
  - Rejected: red accent border-left, Lucide `XCircle`, title "Application rejected", then "{role label} · {approver name} · {date/time}" and the rejection reason in full.
  - Correction Required: purple accent, Lucide `RotateCcw`, title "Correction requested", same layout with the correction comment.
- The banner contains the **Edit & resubmit** primary button (blue), linking to `/applications/[id]/edit`. It is rendered only when the backend returns `can_resubmit: true` (Unit 15 rule retained).
- The stage tracker shows the rejecting/correcting stage in its red/purple state. After resubmission it returns to the orange "Pending" state with a "Resubmitted (cycle N)" marker.
- The decision history is **grouped by cycle** ("Original submission", "Resubmission 1", …), each cycle separated by a small divider that shows the submission or resubmission date/time.

### Employee — edit page (`/applications/[id]/edit`)

Rendered inside the dashboard shell. Breadcrumb: `My applications › {reference} › Edit`. Header: reference number, status badge, and "Resubmission #N" when the cycle is greater than 1.

Layout (single column, max-width matching the Unit 13 form; on `lg+` a narrow right rail):

1. **Approver feedback card** (top, always visible, not collapsible): the same content as the tracker banner, so the employee sees what to fix while editing. On `lg+` it sits in a sticky right rail; on smaller screens it stays at the top.
2. **Returns-to note**: "After you resubmit, this application goes back to **{role label} — {approver name}**. Earlier approvals are kept."
3. **Application form** — the Unit 13 form in "resubmission mode", pre-filled: leave type, start date, end date, live working-days calculation, reason. The employee's identity is never a form field.
4. **Supporting documents** section:
   - Lists **active** documents (name, size, uploaded date) with **Replace** and **Remove** actions plus an **Add document** control.
   - A collapsed "Replaced or removed documents" list shows the retired history (name, retired date, "Replaced by {name}" or "Removed").
   - Remove and Replace ask for a one-line confirmation ("Remove {name}? The file is kept in the application history.").
5. **Validation errors panel** (appears only after a failed Resubmit, above the form actions, `aria-live="polite"`): a list of backend rule errors, each with a code-derived label; field-linked errors also appear inline on the field.
6. **Footer actions** (sticky bottom bar on mobile, inline on desktop):
   - **Save changes** (secondary) — saves in place; the application stays Rejected/Correction Required. Shows "Saved {time}" after success and an "Unsaved changes" indicator when dirty.
   - **Resubmit** (primary blue).
   - **Cancel** link back to the tracker (with a discard warning if dirty; a `beforeunload` guard while dirty).

### Resubmit confirmation dialog

Opened by **Resubmit** (auto-saves first if dirty; aborts with an error banner if the save fails).

- Title: "Resubmit application {reference}".
- Body: a compact list of **what you changed** (from `changes_preview`): field label with before → after values, and documents added/removed/replaced.
- If nothing changed: an orange note "You haven't changed anything since it was last submitted. The approver will see that no changes were made." Resubmission is still allowed.
- Line: "This will return to {role label} — {approver name} for a new decision."
- Buttons: Cancel, and blue **Resubmit**. In flight: spinner, controls disabled, no dismiss by outside click. Focus trap; Escape closes when idle.

On success: navigate to `/applications/[id]`, toast "Application resubmitted", and the tracker shows the stage as Pending again.

### Approver — review page (`/approvals/[id]`, Unit 16)

- New **"Changes since your decision"** card at the **top of the left column** whenever the application is a resubmission (`submission_cycle > 1`) and the viewer has view access:
  - Header: "Resubmitted on {date/time}" plus "Resubmission #N".
  - The viewer's own earlier decision quoted above the changes: "{Rejected/Returned} by you on {date}: {comment}" (or "by {role label} — {name}" if the viewer is not that approver).
  - Field-level rows: **Field**, **Before** (muted, strikethrough for short values), **After**. Fields: Leave type, Start date, End date, Working days, Reason (before and after shown as two stacked text blocks), Documents (Added / Removed / Replaced lists with file names).
  - If there are no changes: "No changes were made to the application content."
- The **approval history timeline** is grouped by cycle, using a chronological `decisions[]` list (see section 7), so a stage that decided twice (for example rejected in cycle 1, then approved in cycle 2) shows both decisions.
- The list page shows a small **Resubmitted** badge (neutral slate, Lucide `RefreshCw`) next to the reference for `submission_cycle > 1`.
- The Decided tab excludes applications currently pending for the same approver, so a resubmitted application appears only in the Pending tab.

### Scope boundaries (explicitly not in Unit 17)

- Emails and any notification delivery (a no-op domain event is emitted).
- Rejected-leave carry-forward calculation and any balance change (a Rejected or Correction Required application never deducts balance — Invariant 12.4).
- Withdraw/close of a rejected application; a free-text "note to approver"; HR reassignment and delegation (an unavailable approver blocks resubmission with a clear error until those units exist).
- Real Unit 6 workflow wiring (Unit 20). The stage snapshot from Unit 16 is reused unchanged.

---

## Implementation

### 1. Assumptions to verify and adjustments to earlier units

Verify against the codebase before starting:

1. **Unit 13**: the application form component can run in a "resubmission mode" (pre-filled, no draft creation) and the document model and upload service are reusable.
2. **Unit 14**: the validation service can accept `exclude_application_id` (to ignore the application itself in overlap checks) and `as_of` (the date used for notice/future-date/financial-year checks). Add these parameters backwards-compatibly if missing. The submit service will call `create_revision` (section 5).
3. **Unit 15**: the tracker payload already exposes `can_resubmit`, rejection/correction details and history; this unit extends it additively (section 8).
4. **Unit 16**: as specified — `ApplicationStage`, immutable `ApprovalDecision` with `submission_cycle`, `Application.current_stage` unchanged on reject/return, stage `version`.

Changes to Unit 16 (small, listed so nothing is missed):

| Area | Change |
|---|---|
| Stage transitions | Allow `rejected → pending` and `correction_requested → pending`, **only** through the resubmit service |
| Documents in review payload | Return only documents with `status = active` |
| Decided tab query | Exclude applications where the user's stage is currently `pending` |
| Review payload | Add `decisions[]` (chronological, all cycles) and a `resubmission` block (section 7); keep `stages[]` for progress |
| List item | Add `submission_cycle` and `is_resubmission` |
| Download-URL endpoint | Allow only `active` documents |

### 2. Status and stage transitions

| From | Trigger | To |
|---|---|---|
| Application `rejected` | Employee saves changes | stays `rejected` |
| Application `correction_required` | Employee saves changes | stays `correction_required` |
| Application `rejected` / `correction_required` | Employee resubmits successfully | `pending` |
| Stage `rejected` / `correction_requested` (the current stage) | Resubmit | `pending` (same stage, same assigned approver, `version += 1`) |
| Earlier stages (`approved`) and later stages (`waiting`) | Resubmit | unchanged |

Editing is impossible in every other status (draft editing stays in Unit 13; pending, approved and cancelled are read-only).

### 3. Data model

**`ApplicationRevision`** (`backend/leave/` — immutable, no update/delete)

| Field | Notes |
|---|---|
| `application` | FK; unique together with `revision_number` |
| `revision_number` | integer, equals the application's `submission_cycle` at that time (1 = original submission) |
| `leave_type` | FK plus `leave_type_name` snapshot |
| `start_date`, `end_date`, `working_days`, `reason` | content snapshot |
| `documents` | JSON list of `{document_id, name, size_bytes, content_type}` active at that moment |
| `changes` | JSON diff against the previous revision (null for revision 1), computed once at creation |
| `created_by`, `created_at` | actor and UTC timestamp |

**Application additions:** `row_version` (integer, default 1, incremented on every saved edit and document operation). `submission_cycle` already exists from Unit 16 and is incremented by resubmission.

**Document additions** (Unit 13 model): `status` (`active` / `retired`), `retired_at`, `retired_by`, `retire_reason` (`replaced` / `removed`), `replaced_by` (nullable self-FK). Retired files are **never deleted** from storage.

Indexes: `(application, revision_number)` unique; `(application, status)` on documents.

### 4. Diff engine

`backend/leave/diff.py` — a pure function `compute_changes(previous_snapshot, current_snapshot) -> Changes` used for both the resubmit revision and the pre-submit preview.

Output shape:

```json
{
  "has_changes": true,
  "fields": [
    { "field": "start_date", "label": "Start date", "before": "2026-10-05", "after": "2026-10-12" },
    { "field": "reason", "label": "Reason", "before": "…", "after": "…" }
  ],
  "documents": {
    "added":    [ { "name": "medical-note.pdf" } ],
    "removed":  [ { "name": "old-letter.pdf" } ],
    "replaced": [ { "old_name": "scan-1.pdf", "new_name": "scan-2.pdf" } ]
  }
}
```

Rules:
- Compared fields: leave type (by id, labelled by name), start date, end date, working days, reason (compared after trimming; internal whitespace is significant).
- Documents are matched by document id. A document in the previous snapshot that is no longer active is **replaced** if its `replaced_by` chain (followed to the end) ends on a currently active document; otherwise **removed**. An active document absent from the previous snapshot and not the end of a replacement chain is **added**.
- `has_changes` is true if any field differs or any document list is non-empty.
- No external diff library; text before/after is returned whole and rendered as two blocks in the UI.

### 5. Services (`backend/leave/services/resubmission.py`)

All services run in `transaction.atomic()`, take the actor from the authenticated user, and resolve the application through the owner check `application.employee.user_id == actor.id` (anything else → 404). No employee or approver id is ever read from the request.

**`create_revision(application, actor)`** — writes the snapshot for the current `submission_cycle` (`changes` computed against the previous revision, if any). Called by:
- Unit 14's submit service, at initial submission (revision 1).
- `resubmit` (below).

**`ensure_baseline_revision(application)`** — if no revision exists for the current `submission_cycle`, create one from the application's current content (which is still the last submitted content because no edit has happened yet). Called at the start of every edit and document operation, **before** any mutation, so applications submitted before Unit 17 also get a valid baseline.

**`get_edit_context(application_id, actor)`** — returns the payload described in section 6.

**`save_changes(application_id, actor, payload, expected_row_version)`**
1. Lock the application; require status in (`rejected`, `correction_required`), else 409 `not_editable`.
2. `expected_row_version` must equal `row_version`, else 409 `version_conflict`.
3. `ensure_baseline_revision`.
4. Validate basic shape only: date formats, `end_date >= start_date`, leave type exists and is available to the employee, reason within Unit 13's length limit. Full rule validation happens at resubmit.
5. Apply the fields, recompute `working_days` through the Unit 5/14 calculator (for display and diff), `row_version += 1`.
6. Return the updated context with `changes_preview`.

**Document operations** (`add_document`, `replace_document`, `remove_document`) — same status/version/baseline checks; upload through the Unit 13 storage service; `replace` creates the new active document and retires the old one with `retire_reason = replaced` and `replaced_by` set; `remove` retires with `removed`. Each writes an audit event (actor, action, document names, application) and bumps `row_version`. A document that belongs to a different application returns 404.

**`resubmit(application_id, actor, expected_row_version)`**
1. Lock the application and its `current_stage`. Owner check (404 otherwise).
2. Status must be `rejected` or `correction_required`, else 409 `not_resubmittable`. The current stage must be in the matching state (`rejected` / `correction_requested`), else 409 `workflow_inconsistent`.
3. `expected_row_version` must match, else 409 `version_conflict`.
4. The stage's `assigned_approver` must be an active user; otherwise 409 `approver_unavailable` with the message "Your approver is currently unavailable. Please contact HR." (Invariant 12.7.)
5. Run the Unit 14 validation service on the saved content with `as_of = today (Africa/Blantyre)` and `exclude_application_id = application.id`. Rules used are those **effective on the resubmission date**. Any critical failure → 400 with `errors: [{code, message, field}]` and **no state change**.
6. `submission_cycle += 1`; `create_revision` (its `changes` is what approvers see).
7. Transition per section 2: application `pending`, current stage `pending`, `stage.version += 1`. The reference number, workflow stages, earlier decisions and `current_stage` pointer are untouched.
8. Audit event `application_resubmitted`: actor, application, stage, before/after status, new cycle.
9. `transaction.on_commit` → `emit_approval_event('application_resubmitted', …)` — the existing no-op dispatcher from Unit 16. **No email and no balance change.**

### 6. API (Django REST Framework)

Authenticated; ownership enforced server-side. All error bodies use the shared Unit 1 error convention.

| Method and path | Purpose |
|---|---|
| `GET /api/applications/{id}/resubmission/` | Edit context |
| `PATCH /api/applications/{id}/resubmission/` | Save changes `{ leave_type_id, start_date, end_date, reason, row_version }` |
| `POST /api/applications/{id}/resubmission/documents/` | Upload (multipart), body includes `row_version` |
| `POST /api/applications/{id}/resubmission/documents/{document_id}/replace/` | Upload replacement (multipart) plus `row_version` |
| `DELETE /api/applications/{id}/resubmission/documents/{document_id}/` | Remove (retire); `row_version` as a query/body field |
| `POST /api/applications/{id}/resubmit/` | `{ row_version }` — validate and resubmit |
| `POST /api/applications/validate/` (Unit 14) | Extended, backwards-compatibly, with optional `application_id` (owner-checked) so overlap ignores the application itself |

Edit context shape:

```json
{
  "id": "…", "reference": "LV-2026-000123", "status": "rejected",
  "submission_cycle": 1, "row_version": 4, "can_edit": true,
  "feedback": {
    "action": "reject",
    "role_label": "HOD", "approver_name": "…",
    "comment": "…", "decided_at": "2026-09-22T08:14:00Z"
  },
  "returns_to": { "role_label": "HOD", "approver_name": "…" },
  "content": {
    "leave_type_id": "…", "leave_type_name": "Annual",
    "start_date": "…", "end_date": "…", "working_days": 5, "reason": "…"
  },
  "documents": {
    "active":  [ { "id": "…", "name": "…", "size_bytes": 12345, "uploaded_at": "…" } ],
    "retired": [ { "id": "…", "name": "…", "retired_at": "…", "retire_reason": "replaced", "replaced_by_name": "…" } ]
  },
  "changes_preview": { "has_changes": false, "fields": [], "documents": { "added": [], "removed": [], "replaced": [] } }
}
```

- `feedback` is the most recent `reject` / `return_for_correction` decision of the current cycle (from the Unit 16 `ApprovalDecision` table).
- Error codes: 400 (validation errors list), 401, 404 (not the owner or not found), 409 `not_editable` / `not_resubmittable` / `version_conflict` / `approver_unavailable` / `workflow_inconsistent`.
- Explicit serializers only (no `__all__`). Signed document URLs continue to use the Unit 13 document service.

### 7. Approver payload extensions (Unit 16 endpoints)

Additive changes to `GET /api/approvals/{application_id}/`:

```json
{
  "decisions": [
    { "cycle": 1, "stage_order": 2, "role_label": "HOD", "approver_name": "…",
      "action": "reject", "comment": "…", "decided_at": "…" },
    { "cycle": 2, "stage_order": 2, "role_label": "HOD", "approver_name": "…",
      "action": "approve", "comment": "", "decided_at": "…" }
  ],
  "resubmission": {
    "is_resubmission": true,
    "cycle": 2,
    "resubmitted_at": "…",
    "previous_decision": { "role_label": "HOD", "approver_name": "…", "action": "reject", "comment": "…", "decided_at": "…" },
    "changes": { "has_changes": true, "fields": [ … ], "documents": { … } },
    "history": [ { "cycle": 2, "resubmitted_at": "…", "changes": { … } } ]
  }
}
```

- `resubmission` is `null` for cycle 1.
- Visibility: the block uses the same `get_view_access` policy as the rest of the review payload; no new access rules. Every approver who can view the application sees the change summary. Employee-supplied text is rendered as plain text (escaped).
- `stages[]` keeps its current meaning (progress); `decisions[]` is the history source for the timeline.

### 8. Employee tracker payload extensions (Unit 15 endpoint)

Additive: `submission_cycle`, `resubmissions: [{ cycle, resubmitted_at }]`, decisions carrying `cycle`, and `can_resubmit` computed as: caller is the owner **and** status is `rejected` or `correction_required`. Approver availability is checked only at resubmit time.

### 9. Frontend — employee (`frontend/`)

Place routes in the same route group as `/applications/[id]`.

```
frontend/
├── app/(dashboard)/applications/[id]/edit/page.tsx
├── lib/applications/resubmission-service.ts     # getContext, save, addDocument, replaceDocument,
│                                                # removeDocument, resubmit, validate
├── lib/applications/resubmission-types.ts
└── components/applications/resubmission/
    ├── approver-feedback-card.tsx               # also reused by the tracker banner
    ├── resubmission-form.tsx                    # Unit 13 form in resubmission mode
    ├── resubmission-documents.tsx               # active list, retired history, add/replace/remove
    ├── resubmit-confirm-dialog.tsx
    ├── validation-errors-panel.tsx
    ├── changes-summary.tsx                      # before/after rows, shared with the approver card
    └── use-unsaved-changes-guard.ts             # beforeunload plus in-app navigation warning
```

Behaviour:
- The edit page fetches the context and redirects to the tracker if `can_edit` is false.
- The form uses the existing Unit 13 working-days calculation hook and validate endpoint (debounced) for live feedback; server validation on Resubmit remains authoritative.
- Every mutation sends the last known `row_version` and replaces local state with the response. `409 version_conflict` shows the banner "This application was changed in another window." with **Reload**.
- **Resubmit** flow: save if dirty → open the confirmation dialog using `changes_preview` → `POST /resubmit/` → on success navigate to the tracker with a toast. On 400 the dialog closes and the validation errors panel is populated and scrolled into view. `approver_unavailable` shows an inline banner with the backend message.
- The client never decides eligibility, the return stage, or the resulting status; it renders `can_edit`, `returns_to` and server errors.
- Documents: uploads show progress and per-file errors (type/size limits come from Unit 13); Replace/Remove confirmations as described in Design.

### 10. Frontend — approver

- `components/approvals/changes-since-decision-card.tsx` renders `resubmission` using the shared `changes-summary.tsx`, placed at the top of the left column on `/approvals/[id]`.
- Update `approval-history-timeline.tsx` to consume `decisions[]` grouped by cycle, with a divider per cycle showing the resubmission date.
- Update `approvals-list.tsx` to show the **Resubmitted** badge from `is_resubmission`.
- After the approver decides on a resubmitted application, the existing Unit 16 behaviour (read-only state, toast, capabilities refetch) is unchanged.

### 11. Development data

Extend `seed_approvals_dev` (idempotent) so it also creates, through the real services (`submit`, Unit 16 `decide`, then Unit 17 `save_changes` / `resubmit`):
- an application **rejected at HOD** (cycle 1, with a reason);
- an application **returned for correction at the Supervisor** (cycle 1, with a comment);
- an application **already resubmitted once** and pending again at the same stage with a non-empty diff (date, reason and a replaced document);
- an application **resubmitted with no changes**;
- an application **rejected a second time** (cycle 2, editable again);
- an application whose **start date is now in the past**, so Resubmit fails validation;
- an application whose returning approver is **inactive**, so Resubmit returns `approver_unavailable`.

The command prints usernames and which application each scenario belongs to.

### 12. Tests

**Backend (Django `TestCase`)**
- Reject → save changes → resubmit: same reference number, `submission_cycle` 2, stage back to `pending` with the same `assigned_approver`, application `pending`, earlier stages `approved`, later stages `waiting`.
- Return for correction → save changes → resubmit: same expectations.
- No stage skipping, no new stage created, workflow snapshot unchanged even if the provider configuration changes between decision and resubmission.
- Ownership: another employee, an approver, and unauthenticated users cannot read/edit/resubmit (404/401); an `employee_id` in a body is ignored.
- State guards: editing or resubmitting in `pending`, `approved`, `draft`, `cancelled` → 409/404 as specified; Unit 13's draft endpoints refuse non-draft applications.
- Version handling: stale `row_version` on save, document ops and resubmit → 409; double-clicking Resubmit yields exactly one resubmission.
- Validation on resubmit: past start date, insufficient notice as of resubmission date, over max duration, insufficient annual balance, overlap with another leave (but **not** with itself), financial-year crossing, missing required documents → 400 with error codes and **no** state or revision change.
- Baseline: application submitted without a revision gets a baseline on first edit; the revision-1 snapshot equals the content at the time of rejection.
- Diff engine: unit tests for each field, whitespace-only reason change, added/removed/replaced documents, replace-then-remove, chained replacements, no changes.
- Documents: replace retires the old file (never deleted from storage), preserves history, and cross-application document ids return 404; retired files are excluded from the approver's document list and download-URL endpoint.
- Approver payload: `resubmission` and `decisions[]` correct across two cycles; view access rules unchanged; Decided-tab exclusion for currently-pending applications; `is_resubmission` on list items.
- Audit: exactly one `application_resubmitted` event per resubmission and one event per document replace/remove, each with actor and statuses.
- Balance: no balance change on reject, correction, edit or resubmission. No email is produced.
- Inactive approver → 409 `approver_unavailable` with no state change.

**Frontend (Vitest + React Testing Library)**
- Tracker: feedback banner per status; **Edit & resubmit** only when `can_resubmit`; history grouped by cycle.
- Edit page: prefilled from context; redirects when not editable; dirty indicator; Save changes updates `row_version`; unsaved-changes guard.
- Documents: add, replace, remove flows; retired history list.
- Resubmit dialog: shows change list from `changes_preview`; shows the no-changes warning; auto-saves when dirty; blocks on save failure; shows `returns_to`.
- Error handling: 400 populates the validation panel and inline fields; 409 `version_conflict` shows Reload; `approver_unavailable` shows the message.
- Approver: "Changes since your decision" card renders fields, documents and the earlier decision; hidden for cycle 1; timeline grouped by cycle; Resubmitted badge in the list.

---

## Dependencies

- **Backend:** no new packages (Django, Django REST Framework, PostgreSQL, existing Unit 13 storage service). The diff engine is plain Python. No queue or Redis usage.
- **Frontend:** no new packages expected — `lucide-react`, Tailwind and the 21st.dev components already in the project (Dialog, Badge, Textarea, Toast, Card). If any of these are missing, add them via the 21st.dev copy-in flow and install only the Radix primitives they declare.
- **Unit dependencies:**
  - Unit 16: stage/decision models, decision service, approver review page and list, event dispatcher.
  - Unit 15: tracker page and payload, `can_resubmit`.
  - Unit 14: validation service (with `exclude_application_id` and `as_of`), submit service, reference numbers.
  - Unit 13: application form, document model and storage service.
  - Units 2–11 (rules, calendar, workflow, employee data): still consumed through the existing providers until they are connected from Unit 20.

---

## Verification checklist

### Rejection and correction states
- [ ] After a Reject decision the application shows status Rejected, the stage is red on the tracker, and the rejection reason, role, approver and date/time are shown to the employee.
- [ ] After a Return decision the application shows Correction Required with the correction comment, role, approver and date/time.
- [ ] No balance is deducted while an application is Pending, Rejected or Correction Required.

### Editing
- [ ] **Edit & resubmit** appears only for the owner, only in Rejected/Correction Required, and only when the backend returns `can_resubmit`.
- [ ] The edit page is prefilled, shows the approver feedback at all times, and states which approver it returns to.
- [ ] The employee can change leave type, dates and reason, and working days recalculates live.
- [ ] Documents can be added, replaced and removed only in these two states; replaced/removed files appear in the retired history and are never deleted from storage.
- [ ] Save changes keeps the application in its Rejected/Correction Required state, invisible to the approver's pending list.
- [ ] Editing or resubmitting a Pending, Approved, Draft or Cancelled application is refused; another employee, an approver or an anonymous user cannot access the edit endpoints.
- [ ] Changing an id or `employee_id` in a request never affects another employee's application.
- [ ] Two windows editing the same application produce a version-conflict banner, not silent overwrites.

### Resubmission
- [ ] Resubmit revalidates working days and all rules as of the resubmission date: notice, max duration, eligibility, balance, overlap (excluding itself), financial-year boundary, required documents.
- [ ] A failed validation shows the errors list and changes nothing (status, stage, revisions, cycle).
- [ ] A successful resubmission keeps the **same reference number**, increments the cycle, and creates a new immutable revision.
- [ ] The application returns to the **same stage and the same assigned approver** for both rejection and correction; earlier approvals remain approved and later stages remain waiting.
- [ ] No stage is skipped and no stage or workflow is recreated; changing workflow configuration afterwards does not alter the application's stages.
- [ ] Double-clicking Resubmit records a single resubmission.
- [ ] Resubmission with no changes is allowed, is confirmed with a warning, and the approver sees "No changes were made".
- [ ] An inactive assigned approver blocks resubmission with the "contact HR" message and changes nothing.
- [ ] A resubmission writes one audit event; document replace/remove each write an audit event; no email is sent and the no-op domain event fires.

### Approver visibility
- [ ] The returning approver sees the application again in **Pending my decision** with a Resubmitted badge, and it is absent from Decided by me.
- [ ] The review page shows "Changes since your decision" with the earlier decision quoted and correct before/after values for type, dates, working days, reason and documents (added/removed/replaced).
- [ ] The approval history is grouped by cycle and shows both decisions when a stage decided twice.
- [ ] Retired documents are not listed or downloadable in the approver's document list; the change summary still names them.
- [ ] Other approvers with view access see the change summary; users without view access still get 404.
- [ ] The approver can approve, reject or return the resubmitted application using the unchanged Unit 16 rules (optional approval comment, mandatory rejection/correction comment).

### Complete flows
- [ ] Reject → edit → resubmit → approver decides again works end to end for the seeded HOD scenario.
- [ ] Correction → edit → resubmit → approver decides again works end to end for the seeded Supervisor scenario.
- [ ] A second rejection after resubmission is editable again and increments the cycle on the next resubmit.

### Quality
- [ ] Employee tracker, edit page and approver card render in light and dark mode using existing tokens only, with loading, empty, error, 400/404/409 states.
- [ ] Mobile layout: sticky footer actions on the edit page, no horizontal scroll, feedback card stays at the top.
- [ ] Dialogs trap focus, close on Escape when idle, announce errors via `aria-live`, and inputs have labels.
- [ ] Employee-supplied text is rendered escaped; dates show in `Africa/Blantyre`.
- [ ] `seed_approvals_dev` creates all seven Unit 17 scenarios idempotently.
- [ ] All backend and frontend tests listed in section 12 pass; lint and type checks pass.
