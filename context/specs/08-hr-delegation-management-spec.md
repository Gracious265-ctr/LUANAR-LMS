# Unit 8 — HR Delegation Management

## Goal

Create the HR daily approval-delegation administration experience (build-plan
§4, Unit 8):

- Approver unavailability / delegation requests.
- Delegate nomination by the requesting approver.
- HR approval.
- HR rejection.
- Mandatory HR decision reason.
- Active delegation management.
- Delegation cancellation.
- Automatic return of unacted applications to the original approver
  (mechanism boundary; actual application rows land in Unit 21).

## Assumptions made (flag if wrong)

- **Domain home: the `workflows` app.** Delegation is approver/workflow
  administration. It depends on Units 6–7 (the `workflows` app), builds a real
  domain model there, and its "automatic return" reads workflow/application
  processing in Unit 21. architecture.md assigns the `workflows` app "Approval
  workflow configuration and processing".

- **Delegation is person-based, not stage-based.** Workflows store approver
  *roles*; a real person resolves per application in Unit 21. A delegation
  therefore binds a specific approver `User` to a specific delegate `User`, and
  the delegated role/stage is whatever role that approver holds in the
  workflow's stages. There is **no** workflow/stage foreign key on a
  delegation — the delegate temporarily acts for that approver wherever they
  are assigned to approve. This mirrors how Unit 7 validated role *capacity*
  while deferring person resolution.

- **The delegate is required at approval time, not at request time.** The
  requesting approver *may* nominate a preferred delegate (build-plan:
  "Delegate nomination"). HR may accept the nominated delegate or substitute
  another person when approving. An approved delegation therefore always has a
  concrete delegate; a `requested` one may have a blank delegate (a nomination
  nobody approved yet).

- **Both approvers and HR can create requests.** Per the ownership summary
  (Delegation: HR = Primary, Approver = "request/interaction"):
  - An active user holding an approver role
    (`supervisor`/`hod`/`dean`/`registrar`/`dvc`/`hr`, the `APPROVER_ROLE_CODES`
    list) can POST their own request (self-service; `approver` is forced to the
    authenticated user — never accepted from the client).
  - HR can POST on behalf of an approver (needed because the Employee +
    Approver track UI for requests does not exist until Units 12–19, and it
    makes the vertical slice demo-able with the seeded per-role users).
  - A plain `employee` user cannot request (403).
  - The approver-side request *form* is **not** part of this HR-track unit; it
    lands in the approver track. This unit ships the HR management UI plus the
    self-service API for approvers.

- **A delegation carries its own decision audit trail.** The delegation row
  stores `requested_by`, `decided_by`, `decided_at`, `decision_reason`, and
  timestamps. The full audit app is Unit 24 and notifications are Unit 22 —
  neither is introduced now.

- **States.** Explicit `status` choice
  (`requested`/`approved`/`rejected`/`cancelled`) is the persistent truth, plus
  a derived read-only `state` for the UI that tightens `approved` by the
  calendar, mirroring `Workflow.state`:

  | status | state | when |
  |--------|-------|------|
  | requested | `requested` | no HR decision yet |
  | approved | `scheduled` | `starts_on` is a future date |
  | approved | `active` | `starts_on <= today` and open-ended or `ends_on >= today` |
  | approved | `ended` | `ends_on < today` (delegation period completed) |
  | rejected | `rejected` | HR rejected |
  | cancelled | `cancelled` | HR cancelled a previously approved delegation |

- **One open request, no overlapping cover per approver.**
  - Creating a second `requested` delegation for an approver who already has an
    open request returns 400 (one request under review at a time).
  - Approving is rejected (400) when the delegation's period overlaps another
    non-final (`approved`, i.e. scheduled/active) delegation for the same
    approver — one acting delegate at a time. Rejected/cancelled/ended
    delegations never block. Period overlap reuses the inclusive date-range
    logic that Unit 5 established (`date_ranges_overlap`), treating a blank
    `ends_on` as open-ended (overlaps anything starting on or after `starts_on`).
  - Delegates are checked only for "active user, approver role, not the
    approver" — no delegate-capacity overlap guard (delegates routinely cover
    many people; real capacity checks are Unit 21's concern).

- **Cancellation ends cover immediately.** HR may cancel an `approved`
  delegation while it is `scheduled` or `active` (an already-`ended` one is
  final). Cancellation is always allowed and requires a mandatory reason. When
  a delegation is not active, application processing simply resolves to the
  original approver — i.e. "unacted applications return" is handled by
  resolution consulting only *active* delegations (the boundary service
  below). The literal re-assignment of application rows has no rows to move yet
  and materializes in Unit 21.

- **"Automatic return" boundary.** `workflows/services.py` gains
  `active_delegation_for(user)` — the current (today, `status="approved"`,
  period covers today) delegation for an approver, or `None`. This is the
  single lookup Unit 21 will call to route a pending application to the
  delegate and, once the delegation ends/cancels, to fall back to the original
  approver. No application tables are touched in this unit.

- **Who may be an approver/delegate.** Both ends must be *active* users, the
  approver and delegate must differ, and both must hold an approver role from
  `APPROVER_ROLE_CODES` (the same codes workflows use for stages — a delegate
  exercises approval authority, so a plain employee is not a valid delegate).

- **Dates.** `starts_on` is required. `ends_on` is optional (blank =
  open-ended until HR cancels) and, when present, must be on/after `starts_on`.
  No past-start restriction: a backdated or today-starting request is legal and
  its derived `state` resolves correctly.

- **No seeding** (consistent with Units 6–7): delegation starts empty; the
  seeded per-role users provide approvers and delegates for testing.

## Visible result

An HR delegation-management interface: HR sees every delegation request and
its state, reviews a request, approves it (picking/confirming the delegate) or
rejects it with a mandatory reason, and cancels an approved delegation; the
list shows approver, delegate, period, and state badges.

## Dependencies

- Unit 7 (workflow approver-role codes, `Workflow.state` pattern, admin form
  guard pattern, API/proxy/table/form conventions).
- Unit 2 (roles, `IsHRRole`, `User.is_active`, employee endpoint providing the
  role-tagged user list for selects, seed infra).
- Unit 5 (`date_ranges_overlap` in `leave/services.py` — reused, not
  duplicated).

## API contract

Namespace: `/api/v1/delegations/`. Authentication required on all endpoints.
List/create/retrieve are HR-only (`IsHRRole`) **plus** self-service create for
approvers; actions (approve/reject/cancel) are HR-only.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/delegations/` | List delegations (HR-only, paginated, newest first; filters `state=`, `approver=` search) |
| POST | `/api/v1/delegations/` | Create a delegation request (approver self-service or HR on behalf) |
| GET | `/api/v1/delegations/{id}/` | Retrieve one delegation (HR-only) |
| POST | `/api/v1/delegations/{id}/approve/` | HR approves (mandatory `decision_reason` + `delegate`) |
| POST | `/api/v1/delegations/{id}/reject/` | HR rejects (mandatory `decision_reason`) |
| POST | `/api/v1/delegations/{id}/cancel/` | HR cancels an approved delegation (mandatory `decision_reason`) |

Object shape (snake_case, DRF conventions):

```json
{
  "id": 1,
  "approver": 3,
  "approver_name": "Jane Dean",
  "approver_role": "dean",
  "delegate": 5,
  "delegate_name": "Bob HOD",
  "starts_on": "2026-10-01",
  "ends_on": null,
  "request_reason": "Attending a conference",
  "requested_by": 1,
  "requested_by_name": "Aisha HR",
  "decision_reason": "",
  "decided_by": null,
  "decided_at": null,
  "status": "requested",
  "state": "requested",
  "created_at": "2026-09-17T12:00:00Z",
  "updated_at": "2026-09-17T12:00:00Z"
}
```

Endpoints for approve/reject/cancel accept `{ "decision_reason": "..." }`
(approve also accepts `delegate`). Errors use the Unit 1 conventions
(`{"detail": "..."}` / `{"field": ["..."]}`).

Validation summary:

- **Create**: HR or approver-role self-service; employee → 403. For
  self-service, `approver` is ignored and forced to the authenticated user.
  `approver` must be an active user holding an approver role; `delegate` when
  present must be active, hold an approver role, and differ from the approver;
  `ends_on` (when present) >= `starts_on`; reject one open request per
  approver.
- **Approve**: only from `requested`; `decision_reason` required (trimmed,
  non-blank); `delegate` required, valid, != approver; no period overlap with
  another `approved` delegation for the approver → 400 naming it.
- **Reject**: only from `requested`; `decision_reason` required.
- **Cancel**: only for `approved` delegations whose state is `scheduled` or
  `active` (not `ended`, `rejected`, `cancelled`, `requested`);
  `decision_reason` required.

## Implementation

Work in the following order; verify each backend step before frontend work begins.

### 1. Model (`workflows/models.py`)

- `Delegation`:
  - `approver` FK User (`on_delete=CASCADE`, `related_name="delegations_as_approver"`).
  - `delegate` FK User (`on_delete=CASCADE`, `related_name="delegations_as_delegate"`,
    `null=True`, `blank=True` — the nomination; required on approval).
  - `starts_on` `DateField`.
  - `ends_on` `DateField(null=True, blank=True)` (open-ended when blank).
  - `request_reason` `TextField(blank=True)`.
  - `requested_by` FK User (`related_name="delegations_requested"`).
  - `status` `CharField(max_length=20, choices=Status)`, default `"requested"`
    (`requested`/`approved`/`rejected`/`cancelled`).
  - `decision_reason` `TextField(blank=True)`.
  - `decided_by` FK User (`null=True`, `blank=True`, `related_name="delegations_decided"`).
  - `decided_at` `DateTimeField(null=True, blank=True)`.
  - `created_at`/`updated_at` auto timestamps.
  - `Meta.ordering = ["-created_at"]`; `CheckConstraint` `ends_on >= starts_on`
    (blank `ends_on` allowed when null).
  - `state` property derived per the table above using `timezone.localdate()`.
  - `__str__`: approver → delegate, state.
- Migration `0001_delegation` (via `makemigrations workflows`).

### 2. Services (`workflows/services.py`)

- `is_approver_role(user) -> bool` — `user.role in APPROVER_ROLE_CODES` (shared
  with the serializer's self-service check).
- `validate_delegate(approver, delegate_pk) -> User | None` — returns the
  delegate user when valid (active, approver role, differs from approver),
  else `None`; the serializer turns `None` + reason into field errors.
- `find_conflicting_delegation(delegation, approver, starts_on, ends_on) -> Delegation | None` —
  another non-final (`status="approved"`) delegation of `approver` whose period
  overlaps `[starts_on, ends_on]`, excluding `delegation`, reusing
  `date_ranges_overlap` with `ends_on or` an effectively-infinite upper bound.
- `active_delegation_for(approver_user) -> Delegation | None` — the current
  active delegation (status `approved`, `starts_on <= today`, open-ended or
  `ends_on >= today`), newest first. Documented as the Unit 21 routing boundary.

### 3. Serializers + actions (`workflows/serializers.py`, `workflows/views.py`)

- `DelegationSerializer`:
  - Writable on create: `approver` (PK), `delegate` (PK, optional), `starts_on`,
    `ends_on`, `request_reason`.
  - Read-only: `approver_name`, `approver_role`, `delegate_name`,
    `requested_by`, `requested_by_name`, `decision_reason`, `decided_by`,
    `decided_at`, `status`, `state`, `created_at`, `updated_at`.
  - `create` (called with the authenticated user): normalizes `approver` for
    self-service, applies all create validations, sets `requested_by` and
    `status="requested"`.
- `DelegationViewSet` routes the six operations (list/create/retrieve + three
  custom `@action` endpoints). HR-only list/retrieve/actions; create passes
  auth-role logic. List filter `?state=` and `?approver=` (search by name) via
  a small `filter_queryset`/`get_queryset` override. Actions are implemented in
  a shared service so serializer/views/admin stay thin:
  - `approve_delegation(delegation, actor, delegate_pk, decision_reason)`.
  - `reject_delegation(delegation, actor, decision_reason)`.
  - `cancel_delegation(delegation, actor, decision_reason)`.
  Each validates the pre-state, mandatory reason, and constraints, then sets
  status/decided fields inside `transaction.atomic()`.
- `workflows/urls.py`: register `delegations` with a `SimpleRouter`
  (basename `delegation`; the actions become `{id}/approve/` etc.).
- `config/urls.py`: the existing `path("api/v1/", include("workflows.urls"))`
  already covers the new routes.

### 4. Admin (`workflows/admin.py`)

- Register `Delegation`: `list_display` (approver, delegate, `starts_on`,
  `ends_on`, state column, `requested_by`, `decided_by`, `decided_at`),
  `list_filter` (`status`), `search_fields` (approver/delegate user names),
  raw_id_fields for the three user FKs, read-only timestamps,
  `has_delete_permission=False`. Actions are API-driven, so the admin is a
  view-only inspector for development (mirrors Unit 6's "no hard delete").

### 5. Views + URLs

- Covered in step 3. `config/urls.py` already includes `workflows.urls`.

### 6. Seed

- No delegation seeding. Existing `seed_dev_users` unchanged.

### 7. Frontend

- `lib/delegations.ts` (server-safe): `Delegation` type, `DelegationInput`,
  `DelegationListResponse`, `DelegationState`/`DelegationStatus` types,
  `listDelegations(state?)`, `getDelegation(id)` (reads via `apiClient`).
- `lib/delegations-client.ts` (client-safe): `createDelegation`,
  `approveDelegation(id, {delegate, decision_reason})`,
  `rejectDelegation(id, decision_reason)`, `cancelDelegation(id,
  decision_reason)` posting to the route-handler proxies; plus
  `DELEGATION_STATE_CODES`/`DELEGATION_STATE_LABELS`/
  `delegationStateBadgeClass` constants and the `delegationStateLabel` helper —
  split exactly like `workflows.ts`/`workflows-client.ts` so client forms never
  pull `next/headers` into the bundle.
- Route-handler proxies: `/api/hr/delegations` POST;
  `/api/hr/delegations/[id]/approve`, `[id]/reject`, `[id]/cancel` POSTs,
  mirroring Unit 2–7 proxy conventions.
- Components under `components/hr/`:
  - `delegation-table.tsx` (approver, delegate, period, state badge, review
    link, empty state).
  - `delegation-form.tsx` (create: approver select, optional delegate
    nomination select, starts/ends dates, request reason; approver and delegate
    options built from the role-tagged employee list passed in from the page).
  - `delegation-review.tsx` (client detail: full info + state badge; when the
    state allows it, Approve/Reject/Cancel controls each opening a small
    in-form section for the mandatory reason — and the delegate select on
    approve — submitting through the proxies; backend errors render in the
    existing error-block pattern).
- Pages under `app/(dashboard)/dashboard/hr-admin/delegations/`:
  - `page.tsx` (list with `?state=` tab filter and "New delegation request"
    button).
  - `new/page.tsx`.
  - `[id]/page.tsx` (review/detail).
  - All pages guard with `getCurrentUser()` → `/login` and
    `user.role !== "hr"` → `/dashboard`, matching existing pages.
- Add a sidebar item ("Delegations", lucide `UserCog` or `UserCheck`) and an HR
  index card; update the HR index footer note (remove "delegation" from the
  "later units" list, leaving only documents).

### 8. Tests

- `backend/workflows/tests.py`:
  - Model/state: derived `state` for requested/scheduled/active/ended/rejected/
    cancelled combinations; `ends_on >= starts_on` constraint.
  - Services: `active_delegation_for` none/active/ended/not-yet-started;
    `find_conflicting_delegation` overlap incl. open-ended vs dated, excludes
    self and rejected/cancelled; `validate_delegate` active/role/self checks.
  - API: 401 unauthenticated; employee self-create → 403; approver self-create
    (self forced even when a foreign `approver` is sent); HR create on behalf;
    400 for one-open-request and for invalid end-before-start; HR list with
    `state` filter + `approver` search; approve happy path (+ delegate
    substituted by HR), approve missing reason 400, approve blank/employee/
    same-as-approver delegate 400, approve overlap 400, approve twice 400;
    reject happy path + missing reason + reject a non-requested row 400; cancel
    happy path + missing reason + cancel a `requested`/`ended` row 400, then
    `active_delegation_for` returns nothing for the cancelled/ended approver;
    non-HR list/retrieve/actions 403.
  - Admin: `DelegationAdmin` renders and `has_delete_permission` False.
- Frontend: `delegation-table.test.tsx` (columns, badges, empty state),
  `delegation-form.test.tsx` (renders, submits create shape from
  `delegations-client`), `delegation-review.test.tsx` (approve/reject/cancel
  shapes + mandatory-reason validation rendering).

### 9. Docs

- `context/specs/08-hr-delegation-management-spec.md` (this file).
- `context/progress-tracker.md`: Unit 8 complete; note the biggest decisions
  (person-based delegation, delegate required at approval, `active_delegation_for`
  is the Unit 21 routing boundary, approver request *form* is a later-track
  unit, no notifications/audit app here).
- Root `README.md` API table: add the `/api/v1/delegations/` rows.

## Verification

- `uv run manage.py test --noinput` green (existing 192 + new delegation tests).
- `npm test` green, `npm run lint` and `npm run build` green.
- `npm run dev` against a seeded backend: HR opens the Delegations page (empty
  state), creates a request for the Dean with a nominated HOD delegate, reviews
  it, approves with the HOD delegate + reason (state becomes `active` when the
  start date is today), the list shows the badge and period, HR rejects a
  second request with a mandatory reason, HR cancels a now-active delegation
  (mandatory reason), and overlapping approval for the same approver returns
  the conflict error in the UI.

## Implementation notes (2026-09-17)

- Person-based, not stage-based: a delegation is approver `User` → delegate
  `User`. The role shown is the approver's role; the actual pending-application
  transfer is Unit 21, reached through `active_delegation_for`.
- `delegate` is required at approval time: the request's nomination is optional,
  HR confirms or substitutes when approving.
- Reuses `leave.services.date_ranges_overlap` for period overlap instead of a
  second copy (code-standards: one authoritative implementation).
- Approver self-service create forces `approver` to the authenticated user; the
  approver request *form* UI belongs to the approver track.