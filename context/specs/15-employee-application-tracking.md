# Unit 15 — Employee Application Tracking

read `context/AGENTS.md` before starting.

## Goal

Give an employee a tracking page at `/applications/[id]` that shows exactly where a submitted leave application is in its approval workflow: status, every stage, the current responsible approver, past decisions and comments, rejection or correction details, and resubmission state. The page is backed by a read-only, owner-only Django endpoint whose stage/decision data comes from a swappable provider (fixture-backed until Unit 20 connects the real workflow engine).

---

## Design

### Scope decisions (agreed)

| Decision | Choice |
|---|---|
| Unit 6 workflow contract | Not available. Unit 15 defines a **provisional tracking contract** (below). Unit 20 must reconcile it with the real Unit 6 contract; the frontend depends only on this response shape. |
| Backend | Read-only `GET /api/leave/applications/{id}/tracking/` behind a tracking-provider interface. Fixture provider now; real provider at Unit 20. |
| Page location | `/applications/[id]` inside the authenticated dashboard shell. Reached from the Unit 13 applications list and the Unit 14 submission-confirmation screen. |
| Resubmit | Display-only. An "Edit & resubmit" link shows only when the backend returns `resubmission.can_resubmit: true`. The resubmit endpoint is out of scope. |
| Future stages | Shown greyed out with their role and, if resolved, the approver's name. |

### Principles this unit must respect

- **Backend authority (architecture 12.1).** The frontend never computes status, current stage, current approver, or `can_resubmit`. It maps enum values to labels, icons and colors, and formats dates.
- **Not hard-coded (architecture section 7).** Stage count, roles and role labels come from the response. Fixtures include both the administration workflow (Supervisor → HOD → Registrar → DVC) and the academic workflow (HOD → Dean → Registrar → DVC). No component may reference "HOD", "Dean" etc. by name.
- **Historical integrity (12.5).** Stages shown are the workflow the application was submitted with, never the current configuration. The provider contract requires this.
- **Ownership (12.2 / 12.6).** Only the owning employee can read a tracker. Everyone else gets 404, never 403, so the existence of another employee's application is not revealed.

### Page layout

Rendered inside the Unit 1 dashboard shell (collapsible sidebar, dark-mode toggle). Content column uses the same page padding as other dashboard pages.

```
┌───────────────────────────────────────────────────────────────┐
│ ← My applications                                  [↻ Refresh] │
│ LV-2026-000123   [● Pending Approval]                          │
│ Annual Leave · 2 Nov – 13 Nov 2026 · 10 working days           │
│ Submitted 12 Oct 2026, 10:32                                   │
├───────────────────────────────────────┬───────────────────────┤
│ CURRENT STATUS CARD (full width, above)                        │
│ 🕒 Awaiting HOD review — Dr. Grace Mwale, assigned 14 Oct 09:10│
├───────────────────────────────────────┬───────────────────────┤
│ Approval progress (col-span-2)        │ Needs your attention  │
│  ✔ 1 Supervisor  Mr. C. Banda         │ (rejection/correction │
│  │   Approved 13 Oct 2026, 15:02      │  panel, only when     │
│  │   “Fine by me.”                    │  relevant)            │
│  🕒 2 HOD  Dr. G. Mwale               ├───────────────────────┤
│  │   Awaiting decision                │ Resubmission          │
│  ○ 3 Registrar  Not yet reached       │ (only if count > 0    │
│  ○ 4 DVC        Not yet reached       │  or can_resubmit)     │
│                                       │                       │
│ Activity history (col-span-2)         │                       │
│  newest first timeline                │                       │
└───────────────────────────────────────┴───────────────────────┘
```

- `lg` and up: two columns (`grid-cols-3`, left `col-span-2`, right `col-span-1`).
- Below `lg`: single column in this order: header, current status card, attention panel, resubmission note, approval progress, activity history.
- Cards: `rounded-xl`, 1px slate border, flat subtle shadow only. No gradients, no glassmorphism. Inter throughout. Lucide React icons only.

### Status badge mapping

Use the semantic status tokens from `ui-context.md` (already in `globals.css`). Do not add new hex values.

| `status` | Label | Color token | Icon |
|---|---|---|---|
| `pending` | Pending Approval | pending (orange) | `Clock` |
| `approved` | Approved | approved (green) | `CheckCircle2` |
| `rejected` | Rejected | rejected (red) | `XCircle` |
| `correction_required` | Correction Required | correction (purple) | `RotateCcw` |
| `cancelled` | Cancelled | cancelled (slate) | `Ban` |

Every badge shows icon **and** text, never color alone.

### Stage item states

| `state` | Marker | Meta line |
|---|---|---|
| `approved` | green filled circle, `Check` | "Approved {datetime}" |
| `awaiting` | orange ring, `Clock`, `aria-current="step"` | "Awaiting decision · assigned {datetime}" |
| `rejected` | red filled circle, `X` | "Rejected {datetime}" |
| `returned` | purple filled circle, `RotateCcw` | "Returned for correction {datetime}" |
| `upcoming` | slate outline circle, empty | "Not yet reached" (whole item at reduced emphasis) |

- Connector line between markers: solid slate for completed segments, dashed for segments leading to `upcoming` stages.
- Each item shows: `Stage {order}` label, `role_label`, approver name, approver designation (secondary text), decision time.
- If `approver.is_delegate` is true, show a small chip "Acting for {on_behalf_of}".
- If `comment` is non-null, show it in a quoted block (slate-tinted background, left border). For `rejected` the block is red-tinted and prefixed "Reason"; for `returned` it is purple-tinted and prefixed "Correction requested". When a comment is null, render no block.
- When `status` is `rejected`, stages after the rejected one stay `upcoming` and the list shows a one-line note beneath the rejected stage: "Workflow stopped."

### Current status card copy

Composed in the frontend purely from response fields:

| `status` | Text |
|---|---|
| `pending` | "Awaiting **{role_label}** review" + "with {approver.name}" (+ "acting for {on_behalf_of}" if delegate) + "Assigned {assigned_at}" |
| `approved` | "Fully approved on {approved_at}" |
| `rejected` | "Rejected at the **{rejection.role_label}** stage on {rejection.decided_at}" |
| `correction_required` | "Returned for correction by **{correction.role_label}** — action needed from you" |
| `cancelled` | "This application has been cancelled" |

### Attention panel (right column)

Rendered only when `rejection` or `correction` is non-null.

- Title: "Rejection details" or "Correction details".
- Fields: stage role, approver name, decision date/time, full reason/comment text (preserve line breaks with `whitespace-pre-line`).
- Footer text: "When you resubmit, this application returns to **{returns_to_stage.role_label}**." (only if `resubmission.returns_to_stage` is set).
- Button "Edit & resubmit" (primary LUANAR blue) rendered **only** if `resubmission.can_resubmit` is true. It links to the Unit 13 edit route. This spec assumes `/applications/{id}/edit`; confirm against Unit 13 before wiring.
- Rejected and correction states use "no annual leave has been deducted" helper text only if the backend later supplies it; Unit 15 does not add balance copy.

### Resubmission note

Rendered when `resubmission.count > 0`: "Resubmitted {count} time(s) · last on {last_resubmitted_at}". Same reference number is displayed throughout; the header never changes on resubmission.

### Activity history

A vertical timeline, newest first, in a card titled "Activity history". Each entry:

| `type` | Title |
|---|---|
| `submitted` | "Application submitted" |
| `approved` | "{role_label} approved" |
| `rejected` | "{role_label} rejected" |
| `correction_requested` | "{role_label} returned for correction" |
| `resubmitted` | "You resubmitted (#{resubmission_number})" |
| `reassigned` | "Application reassigned" |
| *anything else* | "Workflow update" (neutral fallback so new event types from later units never break the page) |

Each entry shows actor name and role label, `<time>` element with the formatted date/time, and the comment if present.

### Date and time

- Backend returns ISO 8601 UTC. Frontend formats in `Africa/Blantyre` (CAT, UTC+2) using `Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone: "Africa/Blantyre", hour12: false })`, e.g. `12 Oct 2026, 10:32`.
- Leave dates (`start_date`, `end_date`) are calendar dates and are formatted without time zone conversion, e.g. `2 Nov 2026`.
- One shared `formatDateTime` / `formatDate` helper. No date library.

### Dark mode, responsiveness, accessibility

- Dark mode: reuse the dark surface/text/border classes already used by the Unit 1 shell. Status colors use the same `dark:` tint pattern as the shell (for example `dark:bg-orange-900/20`). Introduce no new dark colors.
- Stage list is an `<ol>`; each item is an `<li>`; the current stage has `aria-current="step"`.
- Timestamps use `<time dateTime="…">`.
- Status is never conveyed by color alone (icon + text always present).
- Refresh button and "Edit & resubmit" have visible focus rings and a minimum 44px touch target on mobile.
- Long names and comments wrap (`break-words`); no horizontal scrolling at 320px.
- Motion: only a `motion-safe:animate-pulse` on skeleton loaders.

### Page states

| State | UI |
|---|---|
| Loading | Skeleton: header block, status card, 4 stage placeholders |
| 404 | "Application not found" with link back to My applications |
| 409 `application_not_submitted` | "This application is still a draft" with link to the Unit 13 draft editor |
| 401 | Handled by the shared API client / auth guard from Unit 1 (redirect to sign-in) |
| Network/5xx | Inline error card with "Try again" button |
| Success | Full layout above |

---

## Implementation

### 1. Tracking contract (provisional)

`GET /api/leave/applications/{id}/tracking/` returns the shape below. The `{id}` type is whatever primary key type Unit 13 uses for applications.

```json
{
  "application": {
    "id": "…",
    "reference_number": "LV-2026-000901",
    "leave_type": "Annual Leave",
    "start_date": "2026-11-02",
    "end_date": "2026-11-13",
    "working_days": 10,
    "submitted_at": "2026-10-12T08:32:11Z"
  },
  "status": "rejected",
  "approved_at": null,
  "current_stage": null,
  "stages": [
    {
      "order": 1,
      "role": "supervisor",
      "role_label": "Supervisor",
      "state": "approved",
      "approver": {
        "name": "Mr. Chikondi Banda",
        "designation": "Senior Technician",
        "is_delegate": false,
        "on_behalf_of": null
      },
      "assigned_at": "2026-10-12T08:32:11Z",
      "decided_at": "2026-10-13T13:02:40Z",
      "comment": "Fine by me."
    },
    {
      "order": 2,
      "role": "hod",
      "role_label": "HOD",
      "state": "rejected",
      "approver": { "name": "Dr. Grace Mwale", "designation": "Head of Department", "is_delegate": false, "on_behalf_of": null },
      "assigned_at": "2026-10-13T13:02:40Z",
      "decided_at": "2026-10-14T07:15:03Z",
      "comment": "Overlaps with the exam period. Please choose later dates."
    },
    {
      "order": 3,
      "role": "registrar",
      "role_label": "Registrar",
      "state": "upcoming",
      "approver": null,
      "assigned_at": null,
      "decided_at": null,
      "comment": null
    }
  ],
  "events": [
    {
      "id": "…",
      "type": "rejected",
      "occurred_at": "2026-10-14T07:15:03Z",
      "stage_order": 2,
      "actor": { "name": "Dr. Grace Mwale", "role_label": "HOD" },
      "comment": "Overlaps with the exam period. Please choose later dates.",
      "resubmission_number": null
    }
  ],
  "rejection": {
    "stage_order": 2,
    "role_label": "HOD",
    "approver_name": "Dr. Grace Mwale",
    "decided_at": "2026-10-14T07:15:03Z",
    "reason": "Overlaps with the exam period. Please choose later dates."
  },
  "correction": null,
  "resubmission": {
    "count": 0,
    "last_resubmitted_at": null,
    "can_resubmit": true,
    "returns_to_stage": { "order": 2, "role_label": "HOD" }
  }
}
```

**Field rules**

- `status`: one of `pending | approved | rejected | correction_required | cancelled`. Drafts are never tracked.
- `current_stage`: object `{ order, role, role_label, approver_name, is_delegate, on_behalf_of, assigned_at }` when a stage is `awaiting`; otherwise `null` (rejected, correction required, approved, cancelled).
- `approved_at`: timestamp of the final approval; `null` unless `status == "approved"`.
- `stages`: ascending by `order`, contains every stage of the workflow snapshot the application was submitted with. `role` is an opaque key; `role_label` is the display string. `approver` is `null` when not yet resolved.
- `events`: newest first (`occurred_at` desc, then `id` desc). Types: `submitted | approved | rejected | correction_requested | resubmitted | reassigned`. `resubmission_number` is set only on `resubmitted`.
- `rejection` is non-null only while `status == "rejected"`. `correction` (same shape, with `comment` instead of `reason`) is non-null only while `status == "correction_required"`. Once resubmitted, both become `null` and the history lives in `events`.
- `resubmission.can_resubmit` is true only for `rejected` and `correction_required`. `returns_to_stage` is non-null only when `can_resubmit` is true.

**Stage-state invariants** (enforced in provider tests and serializer output, relied on by the UI):

| `status` | Stage states |
|---|---|
| `pending` | exactly one `awaiting` (matches `current_stage.order`); earlier stages `approved`; later stages `upcoming` |
| `approved` | all `approved`; no `awaiting`; `current_stage` null |
| `rejected` | exactly one `rejected`; earlier `approved`; later `upcoming`; no `awaiting` |
| `correction_required` | exactly one `returned`; earlier `approved`; later `upcoming`; no `awaiting` |
| `cancelled` | any; frontend renders whatever stages are returned |

### 2. Backend: package layout

Inside the existing `backend/leave/` Django app:

```
backend/leave/
├── tracking/
│   ├── __init__.py
│   ├── contracts.py          # dataclasses: WorkflowTracking, TrackedStage, TrackedEvent,
│   │                         #   TrackedApprover, TrackedOutcome, ResubmissionInfo
│   ├── provider.py           # TrackingProvider ABC + get_tracking_provider()
│   ├── fixture_provider.py   # FixtureTrackingProvider
│   ├── fixtures/
│   │   ├── assignments.json  # reference_number -> scenario name
│   │   └── scenarios/        # one JSON file per scenario
│   ├── services.py           # get_application_tracking(user, application_id)
│   ├── serializers.py        # read-only DRF Serializer classes (not ModelSerializers)
│   ├── views.py              # ApplicationTrackingView
│   └── urls.py
├── management/commands/seed_tracking_scenarios.py
└── tests/test_tracking_*.py
```

Field and model names for the application (`reference_number`, status, owner, leave type, dates, working days, submitted timestamp) follow what Units 13 and 14 defined. Adjust the service to the real names; do not add fields to the application model in this unit.

### 3. Backend: provider interface

`contracts.py` defines plain dataclasses mirroring the contract in section 1. They contain no Django imports.

`provider.py`:

```python
class TrackingProvider(ABC):
    @abstractmethod
    def get_workflow_tracking(self, application) -> WorkflowTracking:
        """Return workflow state for an already-authorized, already-submitted application.

        Must use the workflow snapshot the application was submitted with,
        never the current workflow configuration.
        """

def get_tracking_provider() -> TrackingProvider:
    # import_string(settings.LEAVE_TRACKING_PROVIDER)()
```

Wire the provider the same way Unit 14 wires its rules provider (a dotted-path setting resolved once through a small factory). Add `LEAVE_TRACKING_PROVIDER = "leave.tracking.fixture_provider.FixtureTrackingProvider"` to the base settings, with a comment stating that Unit 20 replaces it.

`WorkflowTracking` carries: `status`, `approved_at`, `current_stage`, `stages`, `events`, `rejection`, `correction`, `resubmission`.

### 4. Backend: fixture provider

`FixtureTrackingProvider.get_workflow_tracking(application)`:

1. Looks up `application.reference_number` in `fixtures/assignments.json` to get a scenario name.
2. If not found, uses scenario `pending_first_stage`, so any real application submitted through Unit 14 is trackable in dev.
3. Loads `fixtures/scenarios/{name}.json` and returns a `WorkflowTracking`.

Scenarios (each a JSON file; timestamps are absolute so tests are deterministic):

| Scenario | Workflow | Shows |
|---|---|---|
| `pending_first_stage` | administration | Stage 1 awaiting, rest upcoming |
| `pending_mid_workflow` | administration | Stage 1 approved with comment, stage 2 awaiting |
| `pending_with_delegate` | academic | Awaiting stage held by a delegate (`is_delegate: true`, `on_behalf_of` set) |
| `approved` | administration | All four stages approved, `approved_at` set |
| `rejected_at_stage_2` | academic | Rejection at stage 2 with reason; `can_resubmit` true; `returns_to_stage` = stage 2 |
| `correction_required_at_stage_3` | administration | Stage 3 `returned` with correction comment; `can_resubmit` true |
| `resubmitted_after_correction` | administration | Status `pending`, `resubmission.count` 1, awaiting stage 3 again; events include `correction_requested` then `resubmitted` |
| `resubmitted_after_rejection` | academic | Status `pending`, count 1, awaiting the rejecting stage; events include `rejected` then `resubmitted` |

`cancelled` has no backend scenario (cancellation is a later unit) but the frontend supports and tests the badge.

`seed_tracking_scenarios` management command:

- For the seeded dev employee, creates one **submitted** application per scenario using the Unit 13 application model and the Unit 14 reference-number generator, reserving sequence numbers 900001–900008 for fixtures.
- Writes the reference-to-scenario mapping into `fixtures/assignments.json`.
- Idempotent: re-running does not create duplicates; it re-uses existing fixture applications by reference number.
- Refuses to run unless `settings.DEBUG` is true.

### 5. Backend: service, serializers, view, URL

`services.get_application_tracking(user, application_id)`:

1. Load the application filtered by `id == application_id` **and** owner == the employee record of `user` (from the authenticated backend user, never from request input). Not found → raise `Http404` (`NotFound`). This covers other employees, HR and approvers, who get 404 until their own views exist.
2. If the application is a draft → raise a 409 API error with code `application_not_submitted`, using the shared error format from Unit 1.
3. Build the application summary from the application record.
4. Call `get_tracking_provider().get_workflow_tracking(application)`.
5. Return one composed object for serialization.

`serializers.py`: read-only `Serializer` classes matching the contract exactly (`ApplicationSummarySerializer`, `ApproverSerializer`, `StageSerializer`, `CurrentStageSerializer`, `EventSerializer`, `OutcomeSerializer`, `ResubmissionSerializer`, `TrackingSerializer`). Datetimes serialize as ISO 8601 UTC; dates as `YYYY-MM-DD`.

`views.py`: `ApplicationTrackingView(APIView)`, `permission_classes = [IsAuthenticated]`, `GET` only (other methods return 405). Authentication is the DRF token/JWT auth set up in Unit 1.

`urls.py`: `applications/<pk>/tracking/`, named `application-tracking`, included from the leave app's URL config under `/api/leave/`.

Query behavior: one query for the application (select the related leave type and owner), no per-stage queries. The fixture provider does no database access.

Audit: viewing a tracker is not a significant action; no audit record is written.

### 6. Frontend: files

```
frontend/
├── app/(dashboard)/applications/[id]/page.tsx     # use the route group Unit 13 used
├── components/tracking/
│   ├── TrackingView.tsx            # client component: fetch, states, layout
│   ├── TrackingHeader.tsx
│   ├── CurrentStatusCard.tsx
│   ├── ApprovalStepper.tsx
│   ├── StageItem.tsx
│   ├── OutcomePanel.tsx            # rejection + correction variants
│   ├── ResubmissionNote.tsx
│   ├── ActivityTimeline.tsx
│   ├── StatusBadge.tsx
│   ├── TrackingSkeleton.tsx
│   └── TrackingError.tsx
└── lib/tracking/
    ├── types.ts                    # types matching the contract
    ├── service.ts                  # getApplicationTracking(id)
    ├── format.ts                   # formatDateTime, formatDate
    ├── labels.ts                   # status/event -> label, icon, color-class maps
    └── __fixtures__/*.json         # one per scenario, same JSON as the backend fixtures
```

Notes:

- `types.ts`: `ApplicationStatus`, `StageState`, `EventType` are string unions. `role` and `role_label` are plain `string`, never a union of role names.
- `service.ts` calls the real endpoint through the shared API client from Unit 1. No frontend mock is needed because the backend fixture provider serves every scenario. It surfaces errors as typed results distinguishing 404, 409 `application_not_submitted`, and other failures.
- `TrackingView` is a client component (auth token lives client-side). It fetches on mount and on Refresh; no polling. The header shows "Last refreshed {time}" next to the Refresh button.
- `labels.ts` is the only place mapping enum values to icons and color classes. Unknown `EventType` values fall back to the neutral "Workflow update" entry.
- `ApprovalStepper` renders `stages` in the order received. `ActivityTimeline` renders `events` in the order received (already newest first).
- The "Edit & resubmit" button is a link to the Unit 13 edit route, shown only when `resubmission.can_resubmit` is true.
- Add links: Unit 13's applications list row (submitted applications) and Unit 14's submission-confirmation screen both link to `/applications/{id}`. Draft rows continue to open the draft editor. Make these minimal edits only; do not restructure those screens.

### 7. Tests

**Backend (Django `TestCase`)**

- Owner gets 200 with the full contract shape.
- Another employee gets 404; a user with the HR role gets 404; unauthenticated gets 401.
- A draft application returns 409 with code `application_not_submitted`.
- Unknown id returns 404.
- POST/PUT/PATCH/DELETE return 405.
- For every fixture scenario: response validates against the serializer, and the stage-state invariants table holds (parametrized assertion helper).
- Stages ascend by `order`; events are newest first.
- `resubmission.can_resubmit` is true only for `rejected` and `correction_required`; `returns_to_stage` is null otherwise.
- `rejection` and `correction` are null once the application is resubmitted.
- Application with no assignment falls back to `pending_first_stage`.
- Provider swap: override `LEAVE_TRACKING_PROVIDER` with a stub provider and assert the view uses it.
- Query count bounded with `assertNumQueries`.

**Frontend (Vitest + React Testing Library)**

- Each scenario fixture renders the correct status badge, current status card text, stage markers and stage count.
- `pending_with_delegate` shows the "Acting for" chip.
- Rejected scenario shows the reason block, "Workflow stopped", the attention panel, and the button only when `can_resubmit` is true (test both true and false).
- Correction scenario shows the correction panel.
- Resubmitted scenarios show the resubmission note and no attention panel.
- Approved scenario shows the approval date and no attention panel.
- `cancelled` status renders the slate badge.
- Unknown event type renders "Workflow update" without throwing.
- Loading skeleton, 404, 409 and network-error states render their messages.
- `formatDateTime` converts a UTC instant to `Africa/Blantyre` (for example `2026-10-14T07:15:03Z` → `14 Oct 2026, 09:15`); `formatDate` does not shift calendar dates.
- Stage list exposes exactly one `aria-current="step"` for pending scenarios and none otherwise.

### 8. Contract with other units

- **Unit 14:** relies on a submitted application having a reference number and a submitted (non-draft) state. Field names follow Unit 14.
- **Unit 6:** the provisional contract in section 1 must be reconciled at Unit 20. If Unit 6 differs, adapt the real provider to emit this shape, or change the contract and frontend types together in one change.
- **Unit 20 handoff:** replace `LEAVE_TRACKING_PROVIDER` with a real provider reading approval stages, decisions and workflow snapshots from Units 7-11 tables; delete `fixtures/` and the seed command; keep serializers, view, tests (re-pointed at real data) and all frontend code unchanged.
- **Later approver/HR views:** they will need their own endpoints with their own scope rules. This endpoint stays owner-only.

### 9. Out of scope

- Resubmit endpoint and edit flow (Unit 13 edit route is only linked to).
- Cancellation requests and approved-leave cancellation UI.
- Approved leave document download.
- Approver, HR and delegation views of applications.
- Balance display or balance-restoration copy.
- Email notifications, in-app notifications, real-time updates or polling.
- Showing "what changed" between submissions (approver-facing).
- Supporting-document lists.
- Audit logging of tracker views.

---

## Dependencies

No new packages.

- Backend: uses Django and Django REST Framework already installed in Unit 1 (managed with `uv`). No `uv add` needed.
- Frontend: uses Next.js, Tailwind CSS, `lucide-react`, Vitest and React Testing Library already installed in Unit 1. Date formatting uses the built-in `Intl` API; do not add a date library.

Prerequisites that must already exist from earlier units:

- Unit 13: application model, applications list, draft editor route, edit route.
- Unit 14: submit endpoint, reference-number generator, submission-confirmation screen.
- Unit 1: DRF token/JWT auth, shared API client and error format, dashboard shell with dark mode, design tokens in `globals.css`, test infrastructure, seeded test employee.

---

## Verification checklist

### Backend

- [ ] `GET /api/leave/applications/{id}/tracking/` returns 200 with the exact contract shape for the owning employee.
- [ ] Another employee, an HR user and an approver all receive 404 for that application.
- [ ] Unauthenticated request returns 401.
- [ ] Draft application returns 409 with `application_not_submitted`.
- [ ] Non-GET methods return 405.
- [ ] Employee identity comes from the authenticated user; no client-supplied employee id is read anywhere.
- [ ] All 8 fixture scenarios serialize correctly and satisfy the stage-state invariants.
- [ ] `stages` ascend by `order`; `events` are newest first.
- [ ] `current_stage` is populated only when a stage is `awaiting`.
- [ ] `rejection`/`correction` populated only in their own statuses and `null` after resubmission.
- [ ] `can_resubmit` true only for `rejected` and `correction_required`.
- [ ] `LEAVE_TRACKING_PROVIDER` can be swapped without touching the view or serializers.
- [ ] `seed_tracking_scenarios` is idempotent and refuses to run when `DEBUG` is false.
- [ ] `uv run python manage.py test` passes.

### Frontend

- [ ] `/applications/{id}` renders inside the dashboard shell for every seeded scenario.
- [ ] Header shows the reference number, status badge, leave type, dates, working days and submitted time.
- [ ] Current status card text matches the copy table for each status.
- [ ] Stepper shows every stage in order with the correct marker, approver, role, decision time and comment.
- [ ] Upcoming stages are visibly de-emphasized and labelled "Not yet reached".
- [ ] Delegate stage shows the "Acting for" chip.
- [ ] Rejected: red reason block, "Workflow stopped", rejection panel with stage, approver, date/time and reason.
- [ ] Correction required: purple correction block and panel.
- [ ] "Edit & resubmit" appears only when `can_resubmit` is true and links to the Unit 13 edit route.
- [ ] Resubmitted applications keep the same reference number and show the resubmission note.
- [ ] Activity history is newest first with actor, role, time and comments; unknown event types show "Workflow update".
- [ ] All times display in Africa/Blantyre (for example `07:15Z` shows as `09:15`); leave dates show without time shift.
- [ ] Loading, 404, 409 and network-error states behave as specified; Refresh refetches.
- [ ] Links from the applications list (submitted rows) and submission confirmation reach the tracker; draft rows still open the editor.
- [ ] No component contains hard-coded role names or a fixed stage count.
- [ ] `npm run test` and `npm run lint` pass and `npx tsc --noEmit` reports no errors.

### Visual and accessibility

- [ ] Status colors come only from the existing semantic tokens; no new hex values, gradients or glassmorphism.
- [ ] Dark mode renders all cards, badges, quotes and markers legibly using the shell's existing dark classes.
- [ ] Layout is single column below `lg` in the specified order and has no horizontal scroll at 320px.
- [ ] Status is understandable without color (icon + text everywhere).
- [ ] Stage list is an `<ol>` with exactly one `aria-current="step"` on pending applications.
- [ ] Refresh and "Edit & resubmit" are keyboard-reachable with visible focus and 44px touch targets on mobile.
- [ ] Only the skeleton uses animation, and it respects reduced motion.

### Integrity

- [ ] The frontend derives no status, current stage, approver or resubmit eligibility on its own.
- [ ] Stages come from the application's submitted workflow snapshot, not current configuration (documented in the provider contract and asserted in the stub-provider test).
- [ ] No architecture invariant (12.1, 12.2, 12.5, 12.6) is weakened by this unit.
