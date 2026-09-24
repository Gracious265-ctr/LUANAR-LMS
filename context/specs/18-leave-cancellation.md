# Unit 18 — Leave Cancellation

read `context/AGENTS.md` before starting.

**Depends on:** Unit 16 (Approver Review and Decision), Unit 14 (Leave Validation and Submission, including its balance logic)
**Connected to Units 2–11:** not until Unit 20. This unit builds against swappable providers with fixture implementations (see §3.2 and §3.3).

---

## 1. Goal

Let an employee cancel their own leave: a **pending** application is withdrawn immediately, and an **approved** application whose start date has not yet arrived goes through a Supervisor/HOD cancellation approval. Approved cancellation flips the application to `Cancelled` and restores the previously deducted annual-leave days through an append-only, idempotent balance transaction that never feeds carry-forward.

---

## 2. Design

### 2.1 Behavioural rules (authoritative on the backend)

| Situation | Who can act | Approval needed? | Result |
|---|---|---|---|
| Application is **pending** (any approval stage, per Unit 16's pending statuses) | Owning employee | No | Withdrawn immediately: application → `Cancelled`, open approval stage(s) closed, no balance change (nothing was ever deducted) |
| Application is **approved** and `start_date > today` (LUANAR local time, `Africa/Blantyre`) | Owning employee | Yes: Supervisor/HOD stages | Cancellation request created; application stays `Approved` with a "Cancellation requested" indicator until decided |
| Application is **approved** and `start_date <= today` | — | — | Not cancellable (`leave_already_started`) |
| Application is **Draft, Rejected, Correction Required, Cancelled** | — | — | Not cancellable here (`not_cancellable_status`). Unit 17 explicitly has no withdraw. |
| Approved application already has an open cancellation request | — | — | Blocked (`open_request_exists`) |

Additional rules:

1. **A reason is mandatory** for every cancellation, withdrawal included: 10–1000 characters after trimming.
2. **A confirmation step is mandatory.** The client sends `confirm: true` and the server rejects the request without it.
3. **Approver actions:** `Approve` (comment optional) and `Reject` (comment mandatory, max 1000 chars). There is no Return for Correction.
4. **Approval stages** are built from the application's *original workflow snapshot*, keeping only stages whose role is `Supervisor` or `HOD`, in their original order. Administration workflow → Supervisor → HOD. Academic workflow → HOD only. If the snapshot has no Supervisor/HOD stage the request is refused with `no_cancellation_approvers` (invariant 12.7). There is no silent fallback.
5. **Sequential:** the next cancellation stage opens only after the previous one is approved (invariant 12.3). Rejection at any stage ends the request.
6. **Rejected cancellation:** the leave stays `Approved`, the balance is untouched, and the employee may file a new request later (one open request at a time). The employee cannot withdraw an open cancellation request.
7. **Start-date guard at decision time:** the final approving decision is re-checked. If `start_date <= today` by then, approval returns `409 leave_already_started`; the approver can only reject. No background expiry job.
8. **Balance restoration** happens only on final approval of an approved-leave cancellation, only for leave that had an annual-leave deduction. Maternity, paternity and compassionate leave restore nothing (`balance_restored_days = 0`).
9. **Restoration target:** the financial year that was originally debited (equal to the current financial year in the normal case), by the exact deducted days. The restoration is idempotent.
10. **Carry-forward:** cancelled applications and their restoration transactions are flagged `carry_forward_eligible = false`. This unit builds no carry-forward logic. It only guarantees the exclusion.
11. **Action-drift protection:** the client sends `expected_action` (`withdraw` | `request`) taken from the eligibility response. If the server-side state has changed so the action would differ (e.g. an application was finally approved between page load and submit), return `409 action_changed` with fresh eligibility. A withdrawal must never silently turn into an approval-based request.

### 2.2 Application state model

```text
Pending ──(employee withdraws)──────────────────────────▶ Cancelled

Approved ──(employee requests cancellation)──▶ Approved + open request
              │                                   │
              │                                   ├─ all Supervisor/HOD stages approve ─▶ Cancelled (+ balance restored)
              │                                   └─ any stage rejects ────────────────▶ Approved (request Rejected)
```

Cancellation request states: `pending` → `approved` | `rejected`. A withdrawal is recorded as a request with `kind = withdrawal` created directly in `approved` (no approver stages).
Cancellation stage states: `waiting` → `pending` → `approved` | `rejected`, plus `not_reached` for stages after a rejection.

### 2.3 Visual and interaction decisions

Follow `ui-context.md`: LUANAR blue `#0097F0` for interactive elements, neutral slate surfaces, Inter, Lucide icons only, 21st.dev components (reuse the existing Dialog/Textarea/Badge/Tabs patterns already in the repo), `radius-xl` cards, flat subtle shadows, no gradients or glassmorphism, minimal animation, dark mode supported by the dashboard shell tokens.

**Status colors**
- `Cancelled` badge: slate (existing "cancelled slate" token).
- "Cancellation requested" indicator on an Approved badge: pending orange, secondary pill next to the green Approved badge.
- "Cancellation rejected": rejected red, shown in the cancellation card only. The application badge stays green Approved.

**Employee (`/applications/[id]`, Unit 15 tracking page)**
- Header action area: one button whose label is driven by the backend `cancellation_action`:
  - `withdraw` → **Withdraw application**
  - `request` → **Request cancellation**
  - `null` → no button. If `cancellation_blocked_reason` is present, show a small muted line explaining why (e.g. "Leave has already started").
- Cancel dialog (two steps, `Dialog`, focus-trapped, Esc/overlay closes unless submitting):
  1. **Details:** read-only summary (reference number, leave type, dates, working days), a reason `Textarea` with live character counter (10–1000) and inline validation, and a plain-language note of what will happen. Withdraw: "This application will be withdrawn immediately." Request: "Your Supervisor/HOD must approve this. Your leave stays active until then." When `estimated_restoration_days > 0`: "About N annual leave days will be restored to your FY balance if approved."
  2. **Confirm:** read-only recap of the reason and consequences, a **Back** button, and a primary confirm button ("Yes, withdraw application" / "Submit cancellation request"). The button shows a spinner and is disabled while submitting to prevent a double submit.
- **Cancellation card** on the tracking page (shown only when at least one cancellation request exists):
  - Header with a status badge: Pending (orange), Cancelled (slate), Rejected (red).
  - Compact stage stepper: role, approver name, stage state, decision date-time, comment.
  - Reason submitted by the employee and submission time.
  - **Outcome banner** (the employee-visible "notification state" surface):
    - Approved: "Leave cancelled. N annual days restored to FY {label} balance." (or "No annual leave balance was affected." when 0).
    - Rejected: "Your leave remains approved." plus the rejecting approver's comment.
  - **Outcome notification** chip: `Pending` / `Sent` / `Failed` / `Not required`, shown as small muted text.
  - Collapsible "Cancellation history" for earlier rejected requests.
- Cancelled application: the tracker is read-only, the "Edit & resubmit" link never shows, and a slate "Cancelled on {date}" line appears.

**Approver**
- `/approvals` gets a top-level segmented control: **Applications** (existing Unit 16 tabs unchanged) | **Cancellation requests**. The cancellation view has the tabs **Pending** and **Decided by me**.
- Cancellation list table columns: reference, employee, leave type, leave dates, working days, requested on, current stage (role), "starts in N days" (turns orange within 3 days, red "Started" if already started). Sorted oldest request first; pagination follows the Unit 16 convention. Empty states: "No cancellation requests are waiting for you." / "You haven't decided any cancellation requests yet."
- Detail is `/approvals/[applicationId]?cancellation={requestId}`, inside the existing review page. When a `cancellation` parameter resolves to a request the viewer is assigned to, show a **Cancellation request** panel at the top of the page:
  - Cancellation reason, requester, requested at.
  - Original leave details card (reuses the Unit 16 review sections, unchanged).
  - **Balance impact** card: "Approving restores N days to FY {label}" or "No annual leave balance impact".
  - Cancellation stage tracker.
  - "Leave has started; this request can only be rejected" warning banner when applicable (Approve button disabled with tooltip).
  - Decision panel: **Approve** (optional comment) and **Reject** (comment required, inline error, 1000-char counter). Each opens a small confirmation dialog because both are irreversible.
  - When the viewer has already decided or is not the current approver, the panel is read-only and shows the recorded decision.
- On `409`, show a toast ("This request changed. Refreshing…") and refetch.

**Responsive:** dialogs go full-width on mobile, the stage stepper stacks vertically below `md`, and tables scroll horizontally inside their own container.

---

## 3. Implementation

Paths below use the repo layout from `architecture.md`. Align names and helpers with what Units 13–17 already established. Reuse existing utilities (API error format, pagination, audit helper, status enum, permission helpers). Do not duplicate them.

### 3.1 Backend data model (`backend/leave/`)

Create `leave/cancellations/` (models, services, serializers, views, permissions, events, tests) and a migration.

**Existing model changes**
- Application status enum: add `CANCELLED`. Import pending/approved status groups from the Unit 16 enum. Do not redefine them.
- `LeaveApplication`: add nullable `cancelled_at` (datetime).
- Unit 16 approval stage/decision record: add a stage state for applications withdrawn while pending (use the existing enum; add `CANCELLED` if absent) so withdrawn applications drop out of approver queues.

**`CancellationRequest`**
| Field | Notes |
|---|---|
| `id` | PK, same style as other models |
| `application` | FK → LeaveApplication |
| `requested_by` | FK → auth user (from `request.user` only) |
| `kind` | `withdrawal` \| `approved_leave` |
| `reason` | text, 10–1000 chars (validated) |
| `status` | `pending` \| `approved` \| `rejected` |
| `stage_version` | positive int, starts at 1, incremented on every stage transition |
| `requested_at`, `decided_at` | datetimes; `decided_at` is set on the terminal state |
| `application_status_at_request` | snapshot of the application status |
| `balance_restored_days` | numeric, same type as Unit 14's balance days, default 0 |
| `restored_financial_year` | nullable, same representation Unit 14 uses in reference numbers |
| `employee_notification_state` | `not_required` \| `pending` \| `sent` \| `failed` |
| `created_at`, `updated_at` | standard |

Constraints: partial unique constraint `(application)` where `status = 'pending'` (one open request per application).

**`CancellationApprovalStage`**
`request` FK, `order` int, `role` (Supervisor/HOD), `approver` FK user (assigned specific user, as in Unit 16), `status` (`waiting` | `pending` | `approved` | `rejected` | `not_reached`), `decided_at`, `comment`. Unique `(request, order)`. Exactly one stage is `pending` on an open request.

**`LeaveBalanceTransaction`** (append-only; define it here unless Unit 14 already owns one, in which case extend that model instead of creating a duplicate)
`employee`, `financial_year`, `leave_type`, `application` FK, `cancellation_request` FK (nullable), `type` (`deduction` | `restoration`), `days` (> 0), `carry_forward_eligible` (bool), `created_at`. Constraint: unique `(cancellation_request, type)` where `type = 'restoration'`. No updates or deletes through the API or admin (no `save()` on existing rows beyond creation; override to enforce).

### 3.2 Workflow provider extension (fixture-backed until Unit 20)

Extend Unit 16's swappable workflow provider interface with:
- `get_cancellation_stages(application) -> list[StageSpec(order, role, approver_user_id)]`: derived from the application's *original workflow snapshot*, filtered to Supervisor/HOD roles, original order preserved.
- `get_workflow_member_user_ids(application) -> list[int]`: everyone in the snapshot, used as event recipients.

The fixture implementation reads the seeded snapshot on fixture applications. Record in a code comment and in `docs/` that reconciliation with the real Unit 6 contract happens at Unit 20.

### 3.3 Balance provider and Unit 14 balance logic

Add a `BalanceProvider` interface:
- `get_deduction(application) -> DeductionInfo | None` (days, financial year), returning `None` for leave types that do not deduct annual leave.
- `record_restoration(application, cancellation_request, days, financial_year) -> LeaveBalanceTransaction` (idempotent).

Ship a ledger-backed implementation using `LeaveBalanceTransaction`.

**Unit 14 balance integration:** inspect Unit 14's available-balance function.
- If it derives deductions from approved applications directly, switch the calculation to `entitlement − Σ deductions + Σ restorations` from the ledger, keeping one code path and existing Unit 14 tests green (seed ledger deductions in those fixtures).
- If it already reads a ledger, add restoration to the net calculation.

Either way, the employee dashboard balance and the Unit 14 validation must reflect a restoration immediately after commit. Pending applications still do not affect the balance.

### 3.4 Eligibility service (`cancellations/services.py`)

`get_eligibility(application, user) -> Eligibility` returning:
`cancellation_action` (`withdraw` | `request` | `null`), `cancellation_blocked_reason` (code or null), `estimated_restoration_days`, `restoration_financial_year`.

"Today" is computed once through a single helper in `Africa/Blantyre`, and it is injectable for tests. Blocked-reason codes: `not_cancellable_status`, `leave_already_started`, `open_request_exists`, `no_cancellation_approvers`.

### 3.5 Commands (all inside `transaction.atomic()`)

Lock order is always **application row first, then request, then stages** (`select_for_update`) to avoid deadlocks.

**`submit_cancellation(user, application_id, reason, confirm, expected_action)`**
1. Resolve the application through the owner-scoped queryset (another user's application → 404, never 403, to avoid leaking existence). The employee identity comes from `request.user` only. Ignore or reject any client-supplied employee id (serializer refuses unknown fields).
2. Lock, then recompute eligibility. If the computed action differs from `expected_action` → `409 action_changed` (with fresh eligibility).
3. Validate the reason (10–1000, trimmed) and `confirm is True`.
4. **Withdraw path:** create `CancellationRequest(kind=withdrawal, status=approved, employee_notification_state=not_required, decided_at=now)`; set the application to `CANCELLED` with `cancelled_at`; close the open Unit 16 stage record(s); make no balance transactions.
5. **Request path:** build stages via the provider; if empty → `422 no_cancellation_approvers`. Create the request (`pending`, `stage_version=1`) and the stages (first `pending`, rest `waiting`).
6. Write audit records, then emit the domain event on `transaction.on_commit`.

**`decide_cancellation(user, request_id, decision, comment, stage_version)`**
1. Lock application, request and stages. The request must be `pending` (`409 request_not_pending`). `stage_version` must match (`409 stale_stage_version`). The user must be the assigned approver on the current `pending` stage (`403 not_current_approver`).
2. `reject`: the comment is required (`400 comment_required`). Mark the stage `rejected`, later stages `not_reached`, the request `rejected` with `decided_at`, `employee_notification_state = pending`. The application stays `Approved` and no balance transaction is written.
3. `approve` on a non-final stage: mark the stage `approved`, open the next stage as `pending`, increment `stage_version`.
4. `approve` on the final stage: re-check `start_date > today` (else `409 leave_already_started`). Mark the stage and request `approved`, set the application `CANCELLED` with `cancelled_at`, then call `BalanceProvider.get_deduction`. If a deduction exists, record the restoration (`type=restoration`, same financial year, same days, `carry_forward_eligible=false`) and store `balance_restored_days` / `restored_financial_year` on the request. Set `employee_notification_state = pending`.
5. Increment `stage_version` after every transition. Write audit records. Emit the event on commit.

### 3.6 Domain events and notification state

`cancellations/events.py` defines `emit(event_name, payload)` with a **no-op** default handler (no emails in this unit, consistent with Units 16 and 17). Events: `cancellation.requested`, `cancellation.withdrawn`, `cancellation.stage_approved`, `cancellation.approved`, `cancellation.rejected`. Payload: `application_id`, `request_id`, `outcome`, `recipient_user_ids` (the employee plus workflow members from §3.2).

Expose `set_notification_state(request_id, state)` as the single entry point the future notifications app will call to move `pending → sent | failed`. Add a small test that exercises it.

### 3.7 Audit

Use the existing audit helper. Record actor, action, timestamp, previous and new state, and reason/comment for: `cancellation.requested`, `cancellation.withdrawn`, `cancellation.stage_approved`, `cancellation.approved`, `cancellation.rejected`, `balance.restored`. Audit rows are written in the same transaction as the state change (invariant 12.10).

### 3.8 API (DRF, following the shared API conventions from Unit 1)

**Employee**
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/applications/{id}/cancellation-eligibility/` | Eligibility, blocked reason, estimated restoration |
| POST | `/api/applications/{id}/cancel/` | Body `{reason, confirm, expected_action}`. Returns `200` (withdrawn) or `201` (request created), with `kind` in the payload |
| GET | `/api/applications/{id}/cancellations/` | Requests newest first, with stages and notification state |

**Extend Unit 15's tracking payload** additively with `cancellation_action`, `cancellation_blocked_reason`, `has_open_cancellation_request`, `latest_cancellation` (summary), and `cancelled_at`. Existing consumers must not break.

**Approver**
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/approvals/cancellations/?tab=pending\|decided` | Paginated list scoped to the requesting approver |
| GET | `/api/approvals/cancellations/{request_id}/` | Detail: request, stages, original application summary, balance impact, `leave_started` flag, `stage_version` |
| POST | `/api/approvals/cancellations/{request_id}/decision/` | Body `{decision, comment, stage_version}` |

**Unit 16 read-permission extension:** an approver assigned to any stage of a cancellation request may read that application's Unit 16 review payload (with the same role-based visibility matrix for employee info, leave history and balance), even though the application is `Approved` and no longer in their normal pending queue.

**Error codes:** `application_not_found` (404), `not_cancellable_status` (409), `leave_already_started` (409), `open_request_exists` (409), `action_changed` (409), `request_not_pending` (409), `stale_stage_version` (409), `no_cancellation_approvers` (422), `not_current_approver` (403), `confirmation_required` (400), `reason_too_short` / `reason_too_long` (400), `comment_required` (400).

**Regression requirements on existing endpoints:** the Unit 16 pending queue and Unit 15 tracker must treat `CANCELLED` correctly: withdrawn applications never appear in pending queues, and decisions on them return `409`.

### 3.9 Frontend (`frontend/`)

- `lib/services/cancellation/`: `types.ts`, `cancellationService.ts` (real API client using the existing fetch/auth wrapper), one function per endpoint above. No mocked layer is needed because the backend ships in this unit.
- `components/cancellation/`:
  - `CancelApplicationButton.tsx`: renders from `cancellation_action` / `cancellation_blocked_reason`.
  - `CancelApplicationDialog.tsx`: the two-step flow, with validation mirroring backend limits for UX only (the backend stays authoritative). It maps `action_changed` to a refreshed dialog with a message, and other error codes to inline or toast errors.
  - `CancellationCard.tsx`: status, stage stepper, reason, outcome banner, notification chip, history.
  - `CancellationStageStepper.tsx`.
  - `CancellationRequestsTable.tsx` and `CancellationDecisionPanel.tsx` with the approve/reject confirmation dialogs.
- Update `/applications/[id]` to render the button and card, and to add the `Cancelled` badge variant and "Cancellation requested" pill.
- Update `/approvals` with the Applications | Cancellation requests switch. Update `/approvals/[id]` to show the panel when `?cancellation=` is present and the viewer is assigned.
- After a successful submit or decision, refetch tracking or list data. Do not update state optimistically, because the backend owns final state.
- No client-side date or balance logic beyond display formatting. "Starts in N days" uses the server-provided `leave_started` flag plus the date only for the label.

### 3.10 Seed and fixtures

Extend the existing seed command with an idempotent block. Dates are relative to today so fixtures never rot:
- Employee A (administration workflow): pending application at stage 2; approved annual leave starting in 14 days with a 5-day seeded deduction; approved annual leave starting tomorrow; approved annual leave starting today (blocked); approved annual leave that started yesterday (blocked); approved maternity leave (no deduction); a rejected application (not cancellable).
- Employee B (academic workflow, HOD-only cancellation): approved annual leave starting in 10 days with a deduction.
- An approved application with an open cancellation request at stage 1 of 2, for approver UI testing.
- Reuse the seeded Supervisor and HOD users per role from Unit 16. Add no new roles.

### 3.11 Tests

**Backend (Django `TestCase`)**
- Eligibility matrix: every status × start-date-boundary combination (today, tomorrow, yesterday) × open-request state.
- Withdrawal: status change, stage closure, no ledger rows, audit written, event emitted after commit.
- Request creation: stage derivation for admin vs academic workflows; `no_cancellation_approvers`; one-open-request constraint.
- Sequential approval; rejection at stage 1 and stage 2 (later stages `not_reached`); rejection leaves the application Approved and the balance unchanged.
- Final approval: application `CANCELLED`, restoration equals the deduction, same financial year, `carry_forward_eligible=false`; special-leave types restore 0.
- Idempotency: replaying the final approval or forcing a duplicate restoration cannot create a second row.
- Guards: `action_changed`, stale `stage_version`, start-date re-check at final approval, `comment_required`, reason length boundaries, `confirmation_required`.
- Authorization: another employee's application → 404; a non-assigned approver → 403; an approver on a later stage cannot act early; a client-supplied employee id is refused.
- Concurrency: an approver decision racing an employee withdrawal (thread-based test or a simulated lock) results in exactly one winner and a `409` for the other.
- Balance integration: the Unit 14 balance and validation reflect the restoration; pending applications still don't affect the balance.
- Regression: withdrawn applications are absent from Unit 16 queues; existing Unit 14–17 tests stay green.

**Frontend (Vitest + React Testing Library, `vi.mock` on the service module)**
- Dialog: reason validation (9/10/1000/1001 chars), the two-step flow, Back preserves the text, double-submit prevention, `action_changed` handling.
- Button visibility for each `cancellation_action` / blocked reason.
- Card states: pending, approved (with and without restoration), rejected, history, notification chip values.
- Approver panel: Approve/Reject flows, mandatory reject comment, disabled Approve when the leave has started, `409` refetch behaviour, read-only mode.

---

## 4. Dependencies

**No new packages.**
- Backend: Django, DRF, and the existing Django-Q2/Postgres setup are unchanged. Add no dependencies. Use the standard library `zoneinfo` for `Africa/Blantyre`.
- Frontend: reuse existing Next.js, Tailwind CSS, Lucide React and 21st.dev component patterns. Reuse the existing date and form utilities from Units 13–17.

**Internal dependencies:** Unit 16 (stage/decision records, workflow provider, `/approvals` pages, review payload, status enum), Unit 15 (tracking page and payload), Unit 14 (balance logic, financial-year representation, reference-number conventions), Unit 13 (application model and form patterns).

**Out of scope for this unit**
- Real email sending (the no-op event hook only), plus the notifications app's transitions of `employee_notification_state`.
- Invalidating or superseding the approved leave document.
- Carry-forward calculation (only the exclusion flag).
- Delegation and HR reassignment of cancellation stages, and HR views of cancellation data.
- Employee withdrawal of an open cancellation request; partial cancellation of a date range; cancelling Rejected or Correction Required applications.
- Reconciliation with the real Unit 6 workflow contract and real Units 2–5 rules (Unit 20).

---

## 5. Verification checklist

### Rules and states
- [ ] A pending application can be withdrawn with a valid reason and confirmation; it becomes `Cancelled` immediately.
- [ ] Withdrawal creates no balance transaction and the balance is unchanged.
- [ ] Withdrawn applications disappear from all approver pending queues, and approver decisions on them return `409`.
- [ ] An approved application starting after today can have a cancellation requested; it remains `Approved` with a "Cancellation requested" pill.
- [ ] Approved leave starting today or earlier cannot be cancelled (`leave_already_started`).
- [ ] Draft, Rejected, Correction Required and Cancelled applications cannot be cancelled here.
- [ ] Only one open cancellation request per application (`open_request_exists`); a new request is allowed after a rejection.
- [ ] Reason under 10 or over 1000 characters is rejected; a missing `confirm` is rejected by the server.
- [ ] `expected_action` mismatch returns `409 action_changed` and never converts a withdrawal into a request.

### Approval workflow
- [ ] Administration workflow yields Supervisor → HOD stages; academic workflow yields HOD only; other roles never appear.
- [ ] Stages run sequentially; a later-stage approver cannot act early.
- [ ] Reject requires a comment; approve does not.
- [ ] Rejection at any stage ends the request, marks later stages `not_reached`, leaves the leave `Approved` and the balance unchanged.
- [ ] A workflow with no Supervisor/HOD stage is refused with `no_cancellation_approvers`.
- [ ] Approving the final stage after the leave has started returns `409`, and rejecting still works.

### Balance and carry-forward
- [ ] Final approval of an approved annual-leave cancellation restores exactly the deducted days to the originally debited financial year.
- [ ] Maternity, paternity and compassionate cancellations restore 0 days.
- [ ] Restoration is idempotent: no duplicate rows under replay or concurrent decisions.
- [ ] Restoration transactions and the cancelled application are `carry_forward_eligible = false`.
- [ ] The employee's available balance (Unit 14) reflects the restoration immediately; pending applications still don't reduce it.
- [ ] The balance ledger is append-only: no update or delete path exists.

### Authorization, integrity, audit
- [ ] Another employee's application returns 404; the employee identity comes only from the authenticated user.
- [ ] Only the assigned approver on the current pending stage can decide (403 otherwise); assigned approvers can read the Unit 16 review payload for their cancellation requests.
- [ ] Concurrent approver decision vs employee withdrawal: exactly one succeeds, the other gets `409`.
- [ ] The cancellation stages come from the *original* workflow snapshot, unaffected by later workflow changes.
- [ ] Audit records exist for requested, withdrawn, stage approved, approved, rejected and balance restored, with actor, timestamp, previous/new state and reason/comment.
- [ ] Domain events fire only after commit, and `employee_notification_state` is `not_required` for withdrawals and `pending` after a decision.

### Employee UI
- [ ] The button label follows `cancellation_action` (Withdraw application / Request cancellation) and is hidden with a muted reason when blocked.
- [ ] The dialog enforces 10–1000 characters with a live counter, has a confirm step with Back, and blocks double submit.
- [ ] The cancellation card shows status, stage stepper, reason, approver comments, outcome banner (restored days and financial-year label) and notification chip.
- [ ] The rejected outcome says the leave remains approved; earlier requests appear in the collapsible history.
- [ ] The `Cancelled` badge is slate; the tracker is read-only and "Edit & resubmit" never appears on a cancelled application.

### Approver UI
- [ ] `/approvals` switches between Applications and Cancellation requests; Unit 16 views are unchanged.
- [ ] The pending list shows only requests assigned to the viewer at their current stage; "Decided by me" shows the viewer's decided requests.
- [ ] The detail panel shows the reason, original leave details, balance impact, stage tracker and the started warning; Approve is disabled once the leave has started.
- [ ] Approve and Reject each require confirmation; Reject requires a comment.
- [ ] A `409` produces a toast and refetches.

### Cross-cutting
- [ ] All new UI uses ui-context tokens, works in light and dark mode, is keyboard-accessible (focus trap, labelled controls) and is usable on mobile widths.
- [ ] No new dependencies were added.
- [ ] Seed data is idempotent and produces every scenario listed in §3.10.
- [ ] All Django and Vitest tests pass, including the existing Unit 13–17 suites, and lint/type checks are clean.
