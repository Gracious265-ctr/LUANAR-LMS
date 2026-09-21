# Unit 16 — Approver Review and Decision

## Goal

Give each approver (Supervisor, HOD, Dean, Registrar, DVC) a dashboard where they see only the applications currently assigned to them, review everything their role is permitted to see (application, employee info, balance, leave history, documents, earlier decisions), and record exactly one decision — **Approve**, **Reject**, or **Return for Correction** — enforced by the backend with sequential stages, a mandatory comment for Reject/Return, and an optional comment for Approve.

---

## Design

### Visual and structural decisions

Follow `ui-context.md` tokens and the existing dashboard shell (collapsible sidebar, dark mode toggle). No new colours, no gradients, flat shadows only, Inter font, Lucide icons only, 21st.dev components (Dialog, Tabs, Table, Badge, Textarea, Toast), cards use `radius-xl`.

| Element | Treatment |
|---|---|
| Primary interactive colour | LUANAR blue `#0097F0` (links, active tab, focus ring) |
| Approve button | Institutional green `#009119` |
| Reject button | Semantic red (rejected token) |
| Return for Correction button | Semantic purple (correction token) |
| Status badges | Pending = orange, Approved = green, Rejected = red, Correction Required = purple, Cancelled = slate (reuse the Unit 15 status badge component) |
| Dates | Displayed in `Africa/Blantyre` via `Intl.DateTimeFormat`, e.g. `21 Sep 2026, 14:32`. Stored and transmitted as UTC ISO strings |

### Navigation

- New sidebar item **Approvals** (Lucide `ClipboardCheck`) placed below the employee items, shown **only** when `GET /api/approvals/capabilities/` returns `is_approver: true`.
- The item shows a small blue count badge with `pending_count` when greater than 0. Hiding the item is a usability measure only; the backend authorizes every request.

### Page 1 — Approvals list: `/approvals`

- Page header: title "Approvals", subtitle "Applications waiting for your decision".
- Two tabs: **Pending my decision** (default, with count) and **Decided by me** (read-only history).
- Search input (reference number or employee name), debounced 300 ms, server-side.
- Table columns: Reference, Employee (name + department below in muted text), Leave type, Dates (`start – end`), Working days, Submitted (date), Status badge, and a chevron action. The whole row is a link to `/approvals/[id]`.
- Pending sort: oldest submission first. Decided sort: most recently decided first. Page size 20 with previous/next controls.
- The Decided tab adds a "Your decision" column (Approved / Rejected / Returned) and "Decided on".
- States: loading skeleton rows; empty pending ("No applications are waiting for your decision"); empty decided; error with a Retry button.
- Mobile: table collapses into stacked cards (reference, employee, leave type, dates, badge).

### Page 2 — Review and decide: `/approvals/[id]`

Rendered inside the dashboard shell. Breadcrumb: `Approvals › {reference}`. Header shows the reference number, the status badge, and a "Resubmission #N" badge when the application has been resubmitted.

Two-column layout at `lg` and above (left about 2/3, right about 1/3):

**Left column (stacked cards)**
1. **Application details**: leave type, start date, end date, working days, reason, submitted at.
2. **Supporting documents**: list of files (name, size, uploaded at) with a View/Download action per file. Empty state "No supporting documents were attached". Documents are read-only.
3. **Approval history**: vertical timeline of prior decisions, oldest first. Each entry has the stage role label, approver name, action badge, date/time, and the comment (or "No comment"). The current pending stage appears at the end as "Awaiting your decision", and future stages appear as muted "Not yet reached". Reuse the Unit 15 tracker component in its read-only form where possible.
4. **Leave history**: table of the employee's other leave (type, dates, working days, status) within the role's permitted scope. A scope note appears above the table (for example "Showing leave within the current financial year"). If the role has no permitted history, show "Leave history is not available for your role".

**Right column**
1. **Decision panel** (sticky on `lg+`): three full-width buttons stacked — Approve, Reject, Return for Correction. If `permissions.can_decide` is false, the panel is replaced by a read-only banner explaining why, using the backend's `reason` code:
   - `already_decided`: "You approved/rejected/returned this application on {date}."
   - `not_current_stage`: "This application is currently with {role}." (or "has not reached your stage yet")
   - `application_closed`: "This application is {status}."
2. **Employee information**: name, staff ID, designation, department/faculty, grade, date of appointment (fields per the role matrix below).
3. **Leave balance**: annual leave entitlement, used, available. When the application is annual leave, show "Requested: N days" next to "Available: M days" as information only. If `requested > available`, show an orange informational note ("Requested days exceed the available balance"); the approver's actions are not changed by this. Balance is displayed only — approvers cannot modify it.

On viewports below `lg`, the decision panel moves to a sticky bottom bar containing the three buttons (icon plus short label).

### Decision dialogs

One shared dialog component, three variants. Each dialog shows the reference number, employee name, and leave type/dates as a compact summary.

| Variant | Title | Comment field | Confirm button |
|---|---|---|---|
| Approve | "Approve application" | "Comment (optional)" | Green "Approve" |
| Reject | "Reject application" | "Reason for rejection (required)" | Red "Reject" |
| Return | "Return for correction" | "What needs to be corrected? (required)" | Purple "Return for correction" |

- Approve dialog extra line: "Next stage: {next role label}" from `next_stage`, or, when `is_final_stage` is true, "This is the final approval stage. Approving will finalise this leave application."
- Reject dialog extra line: "The workflow will stop. The employee can edit and resubmit."
- Return dialog extra line: "The employee will be asked to correct and resubmit this application."
- Textarea: 4 rows, character counter `n / 1000`, `maxLength` 1000, trimmed before send.
- The Reject/Return confirm button is disabled until the trimmed comment is non-empty. This is a UX aid only; the backend validates independently.
- On submit: buttons disabled, spinner in the confirm button, dialog cannot be dismissed by outside click while in flight.
- Focus trap and Escape to close (except in flight); the error region uses `aria-live="polite"`; the textarea has a proper `<label>` and `aria-describedby` for its counter/error.

### After a decision

- On success: close the dialog, show a toast ("Application approved" / "Application rejected" / "Application returned for correction"), and re-render the page from the response. The decision panel becomes the read-only banner, and the history timeline now includes the new decision.
- On `409 stage_changed`: inline banner in the dialog "This application has changed since you opened it." with a **Reload** button that refetches and closes the dialog. Nothing is submitted twice.
- On `400` field errors: show `comment` errors under the textarea.
- On `403`: show the read-only banner and refetch.
- On `404` for the page: standard "Application not found" state.

### Scope boundaries (explicitly not in Unit 16)

- Employee edit/resubmit flow, and the "what changed" diff for resubmitted applications (resubmission unit). Unit 16 preserves the pointers needed for resubmission to return to the same stage.
- Annual-leave balance deduction, approved-document generation, and emails (later units). Unit 16 emits a no-op domain event instead.
- Delegation and HR reassignment (later units). Unit 16 centralizes the "may this user act" check so they can extend it.
- HR access to applications, approver-side cancellation-request handling.
- Real Unit 6 workflow wiring (Unit 20). Unit 16 uses the provisional provider described below.

---

## Implementation

### 1. Assumptions to verify before starting

1. **Unit 15 contract.** Reuse the Unit 15 application-status enum, stage/decision field names, and the read-only tracker component. Where Unit 15 already defines a model or serializer for stages or decisions, extend it instead of creating a duplicate.
2. **Unit 14 submission.** If submission already snapshots workflow stages and sets the first stage pending, reuse that. If not, add the `assign_workflow(application)` service in section 3 and call it from Unit 14's submit service inside the same transaction.
3. **Application id type.** Use the same identifier type as the Unit 15 `/applications/[id]` route.
4. **Audit.** If the `audit` app already has a logging helper, use it. If not, add the minimal `AuditEvent` model and `record_event(actor, action, target, before, after, reason)` helper in `backend/audit/` so Invariant 12.10 is met, leaving richer audit features to the audit unit.

### 2. Backend data model (`backend/workflows/`)

**`ApplicationStage`** — one row per stage per application; this **is** the workflow snapshot, so later configuration changes never alter it (Invariant 12.5).

| Field | Notes |
|---|---|
| `id` | primary key |
| `application` | FK to leave application |
| `stage_order` | integer starting at 1; unique together with `application` |
| `role` | one of supervisor / hod / dean / registrar / dvc |
| `role_label` | display label snapshot |
| `assigned_approver` | FK to user, protected on delete |
| `status` | `waiting`, `pending`, `approved`, `rejected`, `correction_requested` |
| `is_final` | boolean, true for the last stage |
| `version` | integer, incremented on every change to this stage (used for optimistic concurrency) |

**`ApprovalDecision`** — append-only; no update or delete via ORM helpers, admin, or API.

| Field | Notes |
|---|---|
| `id`, `application`, `stage` | FKs |
| `approver` | FK to user |
| `approver_name` | snapshot of full name at decision time |
| `role_label` | snapshot |
| `action` | `approve`, `reject`, `return_for_correction` |
| `comment` | text, blank allowed only for approve |
| `submission_cycle` | integer copied from the application (see below) |
| `decided_at` | UTC timestamp |

**Application additions** (only if not already present from Units 13–15): `current_stage` (nullable FK to `ApplicationStage`) and `submission_cycle` (integer, default 1, incremented by the future resubmission unit).

Constraints:
- Database check: `comment` non-blank when `action` is `reject` or `return_for_correction`.
- Unique partial constraint: at most one `pending` stage per application.
- Indexes: `(assigned_approver, status)` on stage; `(approver, decided_at)` on decision.

### 3. Workflow provider (swappable)

`backend/workflows/providers.py`

```python
class WorkflowProvider(Protocol):
    def get_stage_definitions(self, application) -> list[StageDefinition]:
        """Ordered stages: [{order, role, role_label, approver_user_id}]"""
```

- `FixtureWorkflowProvider` (default until Unit 20): resolves stages from a settings/fixture map keyed by employee category and department/faculty, using the seeded users. Supports both example workflows: `Supervisor → HOD → Registrar → DVC` and `HOD → Dean → Registrar → DVC`.
- Provider selected via a settings value (e.g. `WORKFLOW_PROVIDER`) so the real Unit 6 implementation drops in at Unit 20 without touching decision logic.
- `assign_workflow(application)` in `backend/workflows/services/assignment.py`: inside a transaction, calls the provider, validates it returned at least one stage with distinct ascending orders and an active approver on each (Invariant 12.7), creates the `ApplicationStage` rows (first `pending`, rest `waiting`, last `is_final=True`), sets `application.current_stage`. Raises a domain error if the workflow is invalid so submission fails cleanly.

### 4. Authority and visibility policies

`backend/workflows/policies.py` — the **only** place these decisions are made.

**`get_decision_authority(user, application) -> Authority`**
Returns `can_decide` plus a `reason` code. `can_decide` is true only when **all** hold:
1. The application status is submitted/pending.
2. `application.current_stage.status == 'pending'`.
3. `application.current_stage.assigned_approver_id == user.id`.

Otherwise `reason` is one of `application_closed`, `not_current_stage`, `already_decided`. Later units (delegation, reassignment) extend this function only.

**`get_view_access(user, application) -> ViewAccess | None`**
The user may view the application only if they are the assigned approver of at least one of its stages whose status is **not** `waiting` (the application has reached them). Otherwise return `None`, and the API responds **404** so existence is not leaked. The returned object carries the user's `stage` (and its `role`) for that application. The viewer role used for the matrices below is the **stage role**, not the user's global role.

**Employee-information matrix** (all fields come from the backend employee record):

| Field | Supervisor | HOD | Dean | Registrar | DVC |
|---|---|---|---|---|---|
| Full name, staff ID | ✓ | ✓ | ✓ | ✓ | ✓ |
| Designation | ✓ | ✓ | ✓ | ✓ | ✓ |
| Department / faculty | ✓ | ✓ | ✓ | ✓ | ✓ |
| Grade | ✓ | ✓ | ✓ | ✓ | ✓ |
| Date of appointment | ✓ | ✓ | ✓ | ✓ | ✓ |

Fields not in the table (contact details, anything else on the employee record) are never serialized. The matrix is a dictionary keyed by role so it can be tightened later without touching the serializer.

**Balance:** annual leave entitlement, used, and available are returned for all five roles.

**Leave-history scope** (`get_leave_history_scope(view_access, employee)`):

| Role | Scope |
|---|---|
| Supervisor | Employee's full history |
| HOD | Full history, **only if** the employee's department equals the HOD's department; otherwise empty |
| Dean | Full history, **only if** the employee's faculty equals the Dean's faculty; otherwise empty |
| Registrar | Current financial year only |
| DVC | Current financial year only |

History items include the employee's leave with status `approved` or `cancelled`, excluding the application under review, drafts, pending, and rejected ones. Each item has type, start, end, working days, and status. The response includes `history_scope` (`"all"` or `"current_financial_year"`) and `history_available` (boolean) so the UI can show the right note. Financial-year boundaries come from the existing Unit 5 calendar provider (fixture until Unit 20).

Department/faculty scope checks compare the approver's own employee record with the applicant's. If the approver has no employee record or no department/faculty, history is empty (fail closed).

### 5. Decision service

`backend/workflows/services/approval.py`

```python
def decide(*, application_id, actor, action, comment, expected_stage_version) -> Application
```

Runs in `transaction.atomic()`:
1. `select_for_update()` the application, then its current stage.
2. If `stage.version != expected_stage_version` → raise `StageChanged` (409).
3. Call `get_decision_authority`; if not `can_decide` → raise `NotAllowed(reason)` (403).
4. Normalize the comment (strip). Validate: for `reject` and `return_for_correction` it must be non-empty; max 1000 characters for all actions; `action` must be one of the three values.
5. Create the immutable `ApprovalDecision` (snapshot approver name and role label; copy `submission_cycle`).
6. Apply the transition:

| Action | Stage result | Application result |
|---|---|---|
| `approve`, not final | stage → `approved`; next stage (`stage_order + 1`) → `pending` | `current_stage` = next stage; status stays pending |
| `approve`, final | stage → `approved` | status → `approved`; `current_stage` stays on the final stage |
| `reject` | stage → `rejected` | status → `rejected`; workflow stops; no later stage is touched |
| `return_for_correction` | stage → `correction_requested` | status → `correction_required` |

   - A stage is only advanced to the immediately following stage. No code path may skip a stage (Invariant 12.3).
   - For reject and return, `current_stage` is **not** changed, so the resubmission unit can return the application to the same stage.
   - Every touched stage has `version += 1`.
7. Write the audit event: actor, action, application, stage, previous/new application status, and the comment as the reason.
8. `transaction.on_commit(...)` → `emit_approval_event(event)`: a no-op dispatcher (`workflows/events.py`) with a typed payload (`decision_recorded`, `stage_assigned`, `application_finalised`). It is a documented hook where notifications, balance deduction, and document generation attach later. **Unit 16 does not deduct balance or send email.**

Domain errors map to HTTP: validation → 400, `NotAllowed` → 403, `StageChanged` → 409.

### 6. API (Django REST Framework)

All endpoints require authentication, and the user always comes from the authenticated backend identity (Invariant 12.2/12.6). No employee or approver id is accepted from the client.

| Method and path | Purpose |
|---|---|
| `GET /api/approvals/capabilities/` | `{ is_approver, pending_count }`. `is_approver` is true if the user is assigned to at least one stage |
| `GET /api/approvals/?tab=pending\|decided&q=&page=&page_size=` | Paginated list. `pending`: applications whose current stage is `pending` and assigned to the user. `decided`: applications on which the user has a decision record. `q` matches reference (case-insensitive contains) or employee name |
| `GET /api/approvals/{application_id}/` | Full review payload (below). 404 if `get_view_access` is `None` |
| `POST /api/approvals/{application_id}/decision/` | Body `{ action, comment, stage_version }`. Returns the updated review payload |
| `GET /api/approvals/{application_id}/documents/{document_id}/download-url/` | Short-lived signed URL (60 s) via the Unit 13 document service; only after `get_view_access` passes and the document belongs to this application |

List item shape:

```json
{
  "id": "…", "reference": "LV-2026-000123",
  "employee_name": "…", "department": "…",
  "leave_type": "Annual", "start_date": "2026-10-05", "end_date": "2026-10-09",
  "working_days": 5, "submitted_at": "2026-09-21T09:12:00Z",
  "status": "pending",
  "my_decision": null | { "action": "approve", "decided_at": "…" }
}
```

Review payload shape:

```json
{
  "id": "…", "reference": "…", "status": "pending", "submission_cycle": 1,
  "application": { "leave_type": "…", "start_date": "…", "end_date": "…",
                   "working_days": 5, "reason": "…", "submitted_at": "…" },
  "employee": { "full_name": "…", "staff_id": "…", "designation": "…",
                "department": "…", "faculty": "…", "grade": "…",
                "date_of_appointment": "…" },
  "balance": { "entitlement": 24, "used": 10, "available": 14 },
  "leave_history": { "available": true, "scope": "all", "items": [ … ] },
  "documents": [ { "id": "…", "name": "…", "size_bytes": 12345, "uploaded_at": "…" } ],
  "stages": [ { "order": 1, "role_label": "Supervisor", "status": "approved",
                "approver_name": "…", "decided_at": "…", "comment": "…" }, … ],
  "current_stage": { "order": 2, "role_label": "HOD", "version": 3,
                     "is_final": false, "next_role_label": "Registrar" },
  "permissions": { "can_decide": true, "reason": null },
  "my_stage_role_label": "HOD"
}
```

- `stages[].comment` for **all earlier stages** is visible to every approver who can view the application.
- Only the fields in the shapes above are serialized (explicit serializers, no `__all__`).
- Application details for previously decided applications remain viewable in the `decided` tab through the same detail endpoint (read-only, `can_decide: false`).
- Performance: use `select_related`/`prefetch_related` for the list and detail queries; no N+1 on stages or documents.

### 7. Frontend (`frontend/`)

Place routes in the same route group and layout as `/applications/[id]` from Unit 15.

```
frontend/
├── app/(dashboard)/approvals/page.tsx           # list page
├── app/(dashboard)/approvals/[id]/page.tsx      # review page
├── lib/approvals/
│   ├── types.ts                                 # types matching the API payloads
│   ├── service.ts                               # capabilities, list, detail, decide, getDownloadUrl
│   └── format.ts                                # date/status/action label helpers (Africa/Blantyre)
└── components/approvals/
    ├── approvals-list.tsx                       # tabs, search, table/cards, pagination
    ├── application-details-card.tsx
    ├── documents-card.tsx
    ├── approval-history-timeline.tsx            # wraps/reuses Unit 15 tracker read-only
    ├── leave-history-card.tsx
    ├── employee-info-card.tsx
    ├── balance-card.tsx
    ├── decision-panel.tsx                       # buttons or read-only banner
    ├── decision-dialog.tsx                      # shared dialog, three variants
    └── approvals-nav-item.tsx                   # sidebar item + count badge
```

- `service.ts` uses the shared API client and error conventions from Unit 1. It exposes a typed `ApiError` carrying `status` and field errors so components can distinguish 400/403/404/409.
- Pages are client components using a small data hook (`useApprovalDetail(id)`, `useApprovalsList(params)`), each with loading/error/refetch handling. No optimistic updates: state changes only from server responses.
- `decision-dialog.tsx` sends `{ action, comment: comment.trim(), stage_version }` where `stage_version` comes from the last fetched payload. Client validation mirrors the rules (required for Reject/Return, 1000 max) but the server's errors are always displayed.
- The sidebar integration adds `approvals-nav-item.tsx` to the existing shell nav, driven by `capabilities`; refetch the capabilities after a successful decision so the count badge updates.
- Documents: clicking View/Download calls `getDownloadUrl`, then opens the returned URL in a new tab (`noopener,noreferrer`). Show an inline error toast on failure.
- The UI never decides who can act: it renders exactly what `permissions` says.

### 8. Development data and fixtures

Management command `python manage.py seed_approvals_dev` (idempotent):
- Reuse the Unit 1 seeded test users where they exist; add one seeded user per approver role (Supervisor, HOD, Dean, Registrar, DVC) plus at least two employees (one administrative, one academic) in departments/faculties that make the HOD and Dean scope checks testable (include one employee **outside** the HOD's department and one **outside** the Dean's faculty).
- Configure `FixtureWorkflowProvider` for both example workflows.
- Create fixture applications by calling the Unit 14 submit service, then advance them with the Unit 16 `decide` service so stage/decision data is consistent. Cover: pending at each of the five roles, one with earlier approvals and comments, one rejected, one returned for correction, one fully approved, one annual application whose requested days exceed available balance, and one with a supporting document.
- Document seeding uses the real Unit 13 storage integration when Supabase env vars are configured; otherwise it seeds metadata only and the command prints a note that download will not work until storage is configured.
- Print a table of seeded usernames/roles and which applications each can see.

### 9. Tests

**Backend (Django `TestCase`)**
- Decision service: approve advances exactly one stage; final approve sets status `approved`; reject stops the workflow; return sets `correction_required`; `current_stage` is unchanged on reject/return.
- Comment rules: approve with blank/absent comment succeeds; reject and return with blank or whitespace-only comment fail with 400 (also verify the DB check constraint); comment over 1000 characters fails.
- Authority: a user who is not the assigned approver gets 403; an approver of a later (`waiting`) stage gets 404 on detail and 403/404 on decision; an approver of an earlier, already-decided stage gets 403 `already_decided`; an unrelated user gets 404; unauthenticated gets 401; a decision on an already approved/rejected/returned application gets 403 `application_closed`.
- Sequential integrity: no code path can decide stage N+1 while stage N is `pending`.
- Concurrency: stale `stage_version` returns 409; two sequential identical requests produce exactly one decision.
- Visibility: detail payload contains only whitelisted employee fields; history scope per role (Supervisor full, HOD same/different department, Dean same/different faculty, Registrar/DVC current financial year only); balance present for all roles.
- Documents: signed URL only for a document belonging to that application and only for a user with view access.
- Audit: each decision writes exactly one audit event with actor, action, statuses, and reason.
- Immutability: `ApprovalDecision` rows cannot be updated or deleted via the model helpers/API.
- Workflow snapshot: changing the provider/configuration after submission does not alter existing `ApplicationStage` rows.
- No side effects: no balance change and no email is produced by any decision.
- List endpoints: pending vs decided tabs, search by reference and by name, pagination, and ordering.

**Frontend (Vitest + React Testing Library)**
- List: renders tabs, rows, empty and error states; search debounces; rows link to `/approvals/[id]`.
- Detail: renders all cards; timeline order; history-unavailable note; read-only banners for each `reason`.
- Dialog: Approve allows empty comment; Reject/Return confirm disabled until non-empty trimmed comment; counter and max length; sends the trimmed comment and `stage_version`; disables controls while pending.
- Error handling: 409 shows the reload banner; 400 shows the comment error; success shows the toast and read-only state.
- Sidebar: item hidden when `is_approver` is false; badge shown when `pending_count` > 0.

---

## Dependencies

- **Backend:** no new packages. Uses the existing Django, Django REST Framework, PostgreSQL, and the Unit 13 document service. No Celery/Redis/queue usage in this unit (the event hook is synchronous and a no-op).
- **Frontend:** no new packages expected. Uses the existing `lucide-react`, Tailwind, and the 21st.dev components already in the project. If the chosen 21st.dev Dialog/Tabs/Table/Textarea components are not yet present, add them via the 21st.dev copy-in flow; install only the Radix primitives those components declare (e.g. `@radix-ui/react-dialog`, `@radix-ui/react-tabs`) if missing.
- **Unit dependencies:**
  - Unit 13: application model, supporting-document model and storage service.
  - Unit 14: submitted applications, reference numbers, balance/rules providers, submit service (`assign_workflow` is called from it).
  - Unit 15: status enum, tracker component, provisional stage/decision contract, `/applications/[id]` layout.
  - Unit 6: workflow configuration contract, consumed only through `WorkflowProvider` (fixture until Unit 20; Units 2–11 are built in parallel and connected from Unit 20).

---

## Verification checklist

### Access and assignment
- [ ] Each seeded approver (Supervisor, HOD, Dean, Registrar, DVC) sees only applications currently pending at their own stage in "Pending my decision".
- [ ] An approver cannot see, by URL or API, an application that has not yet reached their stage (404).
- [ ] An approver whose stage is already decided sees the application read-only under "Decided by me" and cannot decide again (403).
- [ ] A user who is not an approver has no Approvals nav item, and `/api/approvals/` returns empty lists; direct decision calls fail.
- [ ] Changing an id in the URL or request body never grants access to another approver's application.
- [ ] Unauthenticated requests return 401.

### Review information
- [ ] Application details show leave type, dates, working days, reason, and submitted time.
- [ ] Employee information shows only the whitelisted fields for every role.
- [ ] Annual leave balance (entitlement, used, available) is displayed and cannot be edited by the approver.
- [ ] The "requested exceeds available" informational note appears only when applicable and does not block actions.
- [ ] Leave history follows the role matrix: Supervisor full; HOD full only within their department; Dean full only within their faculty; Registrar/DVC current financial year only; out-of-scope employees show "not available".
- [ ] Previous decisions and comments from all earlier stages are visible, in stage order, with role, approver, action, and date/time.
- [ ] Supporting documents can be viewed/downloaded via short-lived signed URLs, and cannot be modified or replaced.
- [ ] A document ID from a different application is rejected.

### Decisions
- [ ] Approve with no comment succeeds; with a comment stores it.
- [ ] Reject with an empty or whitespace-only comment is blocked in the UI and rejected by the API (400).
- [ ] Return for Correction with an empty or whitespace-only comment is blocked in the UI and rejected by the API (400).
- [ ] Comments over 1000 characters are rejected.
- [ ] Approve at a non-final stage moves the application to exactly the next stage, and that approver's Pending tab shows it.
- [ ] Approve at the final stage sets the application to Approved and the dialog shows the final-stage warning.
- [ ] Reject sets status Rejected, stops the workflow, and leaves later stages untouched.
- [ ] Return sets status Correction Required, and the same stage remains the recorded current stage.
- [ ] No stage can be skipped or decided out of order.
- [ ] Double-clicking a confirm button or replaying a request records only one decision (second request returns 409).
- [ ] A stale page (another decision recorded in the meantime) shows the reload banner and never submits a second decision.
- [ ] Decision records are immutable and each stores approver name, role label, action, comment, cycle, and UTC time.
- [ ] Every decision writes an audit event (actor, action, before/after status, reason).
- [ ] No annual-leave balance is deducted and no email is sent by any decision in this unit.

### Integrity
- [ ] Changing the fixture workflow configuration after submission does not change an existing application's stages.
- [ ] `WorkflowProvider` can be swapped through settings without changes to the decision service.
- [ ] The frontend performs no authorization or workflow logic beyond rendering `permissions` and `current_stage`.

### UI and quality
- [ ] List and detail pages render inside the dashboard shell in light and dark mode using existing tokens only.
- [ ] Loading, empty, error, read-only, 403/404/409 states all render correctly.
- [ ] Mobile layout: list becomes cards; decision buttons appear in a sticky bottom bar; no horizontal scroll.
- [ ] Dialogs trap focus, close on Escape when idle, announce errors via `aria-live`, and labels are associated with fields.
- [ ] Dates display in `Africa/Blantyre` format; status colours match the tokens.
- [ ] `seed_approvals_dev` runs idempotently and prints usernames/roles and visible applications.
- [ ] Backend tests and frontend Vitest tests listed in section 9 all pass; lint and type checks pass.
