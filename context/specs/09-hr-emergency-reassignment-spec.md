# Unit 9 — HR Emergency Reassignment

## Goal

Create the HR emergency reassignment experience (build-plan §4, Unit 9):

- View applications requiring intervention.
- Reassign pending applications.
- Select replacement approvers.
- Record a mandatory reassignment reason.
- Preserve reassignment history.

Employee-facing views must eventually expose the new responsible approver but
not the internal HR reason (that exposure belongs to the Employee + Approver
track — see the boundary note below).

## Assumptions made (flag if wrong)

- **"Pending application" = a `submitted` application.** Unit 13
  `LeaveApplication` currently has exactly two statuses (`draft`, `submitted`);
  there is no approval-stage or workflow-routing concept yet (that is Unit 21).
  So the only "applications requiring intervention" that exist today are
  `submitted` rows. Drafts and any future finalized states are never
  reassignable. This is the minimal truthful definition; Unit 21 refines
  "pending at stage X" on top of the spine this unit adds.

- **Add a nullable `current_approver` FK to the shared `LeaveApplication`
  model — the Unit 21 boundary.** Unit 21 resolves workflow stages into concrete
  approvers and, per the progress tracker, "consumes `active_delegation_for`";
  this field is the single "who must act on this application now" spine it sets
  and reads. In this unit HR's reassignment is the *only* writer. The change is
  additive (nullable FK, new migration), preserves the existing serializer
  contract (the field is not added to `LeaveApplicationSerializer`), and is the
  smallest representation that makes "select replacement approvers" real and
  demoable before routing exists. **This modifies the merged Unit 13 model, so
  it is a cross-track coordination point - flagging for explicit approval.**

- **`Reassignment` history model lives in the `workflows` app** (mirrors
  `Delegation`: a record of an approver-administration action). It is person +
  application based: one application → one replacement approver per row. Fields:
  `application` FK `leave.LeaveApplication`, `from_approver` FK `User`
  (`null=True` — a `submitted` application may have no responsible approver yet,
  so the first reassignment is effectively an initial assignment),
  `to_approver` FK `User` (required), `reason` TextField (mandatory), `decided_by`
  FK `User`, `created_at`. `on_delete=CASCADE` matches the `Delegation`
  convention (there is no user-deletion feature; a full audit app is Unit 24).

- **`current_approver` on the application is the live state; `Reassignment`
  rows are the history.** Reassigning atomically writes a `Reassignment` row and
  sets `application.current_approver = to_approver`. This mirrors how `Delegation`
  carries decision fields alongside the actionable state.

- **Reassignment is HR-only.** An employee must never reassign their own
  application; approvers need an HR intervention to transfer work. `IsHRRole`
  guards every endpoint (list/pending/create/retrieve).

- **Validation.**
  - `application` must exist and have `status == "submitted"` (pending). A draft
    → 400. (No other non-final states exist yet.)
  - `to_approver` must be an active user holding an approver role — reuse
    `workflows.services.is_approver_user` (one authoritative implementation; the
    same check `Delegation` uses).
  - `to_approver` must differ from the application's current approver when one is
    set (reassigning to the same person is a no-op → 400).
  - `to_approver` must differ from the application's employee (assigning the
    applicant themselves as the approver of their own request is rejected).
  - `reason` is mandatory (trimmed, non-blank) — mirrors the `Delegation`
    decision-reason requirements (code-standards: mandatory reasons are enforced
    server-side).

- **No `active_delegation_for` consultation here.** Real routing that consults
  live delegations (`active_delegation_for`) and moves work to delegates comes
  in Unit 21. This unit directly sets the responsible approver and records the
  intervention; it does not reach into delegation logic.

  > **Superseded 2026-09-26.** Unit 21 did land, and it made this boundary a
  > correctness problem rather than a clean separation: because delegation is a
  > *query-time overlay* on top of the spine this unit writes, reassigning to an
  > approver with active cover changes the record without changing who acts. The
  > intervention queue now reports the acting approver for exactly that reason.

- **Employee-facing visibility of the new approver is a later-track concern.**
  Unit 9 makes `current_approver` available on reassignment/pending payloads so
  the boundarary is real, but the employee "who is my approver now" view (with
  the reason hidden) belongs to Unit 15/21. Note it, don't build it.

- **No notifications and no audit app here.** Email for reassignment is Unit 22
  and the aggregated audit view is Unit 24. The `Reassignment` row itself is the
  preserved history for this unit.

> **Superseded 2026-09-26.** Both deferrals above have since landed, and one
> assumption this unit made is no longer true. See "Follow-ups (2026-09-26)" at
> the end of this file for the reassignment email, the delegation-aware
> intervention queue, and the tests that pin their interaction.

- **No seeding.** Reassignment starts empty; the seeded per-role users and any
  `submitted` applications created through the leave UI (or tests) provide the
  demo data.

## Visible result

An HR intervention interface under "Reassignments": HR sees every pending
(submitted) application with its employee, leave details, and current
responsible approver ("Unassigned" until one is set), reassigns any of them to a
replacement approver with a mandatory reason, and sees the reassignment history
(application, from → to, reason, HR actor, timestamp).

## Dependencies

- Unit 8 (`Delegation`, `workflows/services.py::is_approver_user`,
  `APPROVER_ROLE_CODES`, HR-only viewset + admin patterns, API/proxy/client/
  table/form conventions, role-tagged employee list for selects).
- Unit 13 (`LeaveApplication` rows, serializers, enabled/verified via the leave
  submissions the HR track was blocked on).
- Unit 2 (`IsHRRole`, employee endpoint providing the role-tagged user list for
  selects).
- Unit 4 (`LeaveType.name` resolution for the intervention queue's leave-type
  display).

## API contract

Namespace: `/api/v1/reassignments/`. Authentication required on all endpoints;
every endpoint is HR-only (`IsHRRole`).

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/reassignments/pending/` | Intervention queue: submitted applications, newest first, with employee, leave type, dates, days, reference, and `current_approver` |
| POST | `/api/v1/reassignments/` | Reassign one pending application (`application`, `to_approver`, `reason`); sets `current_approver` and records history |
| GET | `/api/v1/reassignments/` | Reassignment history (paginated, newest first; filter `application=<uuid>`) |
| GET | `/api/v1/reassignments/{id}/` | Retrieve one reassignment record |

Pending application object shape (snake_case, DRF conventions):

```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "reference_number": "LUANAR-2026-00001",
  "employee": 3,
  "employee_name": "Jane Dean",
  "leave_type_name": "Annual",
  "start_date": "2026-10-01",
  "end_date": "2026-10-05",
  "calculated_days": 5,
  "reason": "Family visit",
  "submitted_at": "2026-09-18T10:00:00Z",
  "current_approver": null,
  "current_approver_name": ""
}
```

Reassignment object shape:

```json
{
  "id": 1,
  "application": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "reference_number": "LUANAR-2026-00001",
  "employee": 3,
  "employee_name": "Jane Dean",
  "from_approver": null,
  "from_approver_name": "",
  "to_approver": 5,
  "to_approver_name": "Bob HOD",
  "reason": "Approver is unavailable; reassigned to HOD cover.",
  "decided_by": 1,
  "decided_by_name": "Aisha HR",
  "created_at": "2026-09-18T12:00:00Z"
}
```

`POST /api/v1/reassignments/` accepts `{ "application": "<uuid>",
"to_approver": 5, "reason": "..." }`. Errors use the unit 1 conventions
(`{"detail": "..."}` / `{"field": ["..."]}`).

Validation summary:

- **401** unauthenticated; **403** any non-HR role on any endpoint.
- **Reassign**: `application` required and must be `submitted` (pending) → 400
  naming it otherwise; `to_approver` required, active approver-role user,
  different from the application's current approver (when set), different from
  the application's employee; `reason` required (trimmed, non-blank).
- **History**: read-only.

## Implementation

Work in the following order; verify each backend step before frontend work begins.

### 1. Model changes

- `leave/models.py`: add `current_approver = ForeignKey(settings.AUTH_USER_MODEL,
  on_delete=SET_NULL, null=True, blank=True, related_name="applications_assigned")`
  to `LeaveApplication`. Migration `leave/0005_*` via `makemigrations leave`.
- `workflows/models.py`: add `Reassignment` model (fields per the assumptions;
  `Meta.ordering = ["-created_at"]`; `__str__`: `{reference} → {to_approver}`).
  Migration `workflows/0004_reassignment` via `makemigrations workflows`.
- Do **not** add `current_approver` to `LeaveApplicationSerializer` fields
  (preserves the Unit 13 API contract); the reassignment and pending serializers
  expose it.

### 2. Services (`workflows/services.py`)

- `reassign_application(*, application, to_approver, actor, reason) -> Reassignment`:
  validates via the shared rules (pending status, active approver-role
  `to_approver`, differs from current approver when set, differs from the
  application's employee, mandatory reason), then inside `transaction.atomic()`
  creates the `Reassignment` row (with `from_approver` = the application's
  current `current_approver`, `to_approver`, `reason`, `decided_by=actor`) and
  sets `application.current_approver = to_approver`. Raises
  `ReassignmentError(field, message)` (mirrors `DelegationActionError`) so the
  serializer/views/admin stay thin.
- Reuse `is_approver_user` for the `to_approver` check — no duplicate role logic.

### 3. Serializers + views (`workflows/serializers.py`, `workflows/views.py`)

- `ReassignmentSerializer` (ModelSerializer): writable `application` (PK, UUID),
  `to_approver` (PK); read-only `reference_number`, `employee`,
  `employee_name`, `from_approver`, `from_approver_name`, `to_approver_name`,
  `reason`, `decided_by`, `decided_by_name`, `created_at`. `reason` trimmed on
  write. `create` calls `reassign_application` with the authenticated HR actor
  and returns the created record.
- `PendingApplicationSerializer` (plain Serializer, read-only): application
  fields + `employee_name`, `leave_type_name` (resolved by `LeaveType.objects
  .filter(pk=app.leave_type_id).values_list("name", flat=True).first()`,
  falling back to ""), `current_approver`, `current_approver_name`.
- `ReassignmentViewSet` (List/Retrieve + custom `@action(detail=False, url_path=
  "pending", methods=["get"])`); `permission_classes = [IsAuthenticated,
  IsHRRole]`; `http_method_names = ["get", "post", "head", "options"]`.
  - `get_queryset`: `Reassignment.objects.select_related("application__employee",
    "from_approver", "to_approver", "decided_by")`, newest first, optional
    `?application=<uuid>` filter.
  - `pending`: `LeaveApplication.objects.filter(status=SUBMITTED).select_related(
    "employee", "current_approver")`, ordered `-submitted_at`, paginated.
- `workflows/urls.py`: register `reassignments` with the existing `SimpleRouter`
  (basename `reassignment`); `config/urls.py` already includes `workflows.urls`.

### 4. Admin (`workflows/admin.py`)

- Register `Reassignment` as a view-only inspector (mirrors `DelegationAdmin`):
  `list_display` (reference/application, employee, from → to approvers, `reason`,
  `decided_by`, `created_at`), `raw_id_fields` for the three user FKs,
  read-only everything, `has_delete_permission=False`. Actions are API-driven.

### 5. Seed

- No reassignment seeding. Existing `seed_dev_users` unchanged.

### 6. Frontend

- `lib/reassignments.ts` (server-safe): `Reassignment`, `PendingApplication`,
  `ReassignmentInput`, `ReassignmentListResponse`, `PendingListResponse`,
  `listReassignments()`, `getReassignment(id)`, `listPendingApplications()` (reads
  via `apiClient`).
- `lib/reassignments-client.ts` (client-safe): `reassignApplication(input)`
  posting to the route-handler proxy; helper `approverRolePeople` is reused from
  `delegations-client` (no duplicate). Split exactly like
  `workflows.ts`/`workflows-client.ts` so client forms never pull `next/headers`
  into the bundle.
- Route-handler proxies under `app/api/hr/reassignments/`:
  `route.ts` (GET list + POST create) and `pending/route.ts` (GET), mirroring
  the Unit 8 proxy conventions (cookie + Bearer, JSON passthrough).
- Components under `components/hr/`:
  - `pending-applications-table.tsx` — intervention queue: reference, employee,
    leave type, dates/days, current approver badge (or "Unassigned"), Reassign
    link per row, empty state.
  - `reassignment-table.tsx` — history: application (link), employee, from → to
    approvers, reason, decided by/at, empty state.
  - `reassignment-form.tsx` — client form bound to a selected `PendingApplication`
    summary: `to_approver` select (role-tagged approver options from the employee
    list, excluding the current approver and the applicant), mandatory `reason`
    textarea, backend errors in the existing error-block pattern, submit through
    the proxy, then redirect to the reassignments list.
- Pages under `app/(dashboard)/dashboard/hr-admin/reassignments/`:
  - `page.tsx` — two panels: "Pending applications" (queue) and "Reassignment
    history"; a "Reassign" button per pending row linking to `new/?application=
    <uuid>`.
  - `new/page.tsx` — loads the selected pending application (via
    `listReassignments`-style read), shows the summary + `ReassignmentForm`.
  - All pages guard with `getCurrentUser()` → `/login` and `user.role !== "hr"`
    → `/dashboard`, matching existing pages.
- Sidebar: add a "Reassignments" item (lucide `ArrowLeftRight`) under the HR
  section; add an HR index card; update the HR index footer note (remove
  "emergency reassignment area" from the remaining-units sentence, keeping only
  document rendering).

### 7. Tests

- `backend/workflows/tests.py`:
  - Model: `Reassignment.__str__`; ordering newest-first.
  - Service: `reassign_application` happy path sets `current_approver` + writes
    `from_approver`, `to_approver`, reason, `decided_by`; 400-family errors for
    draft/non-submitted application, missing/blank reason, inactive/plain-
    employee/absent `to_approver`, `to_approver` == current approver, and
    `to_approver` == application employee; atomicity (failure leaves
    `current_approver` untouched).
  - API: 401 unauthenticated; employee and approver → 403 on list/pending/
    create/retrieve; pending queue shape (name, leave type, current approver)
    and ordering; create happy path returns the reassignment with
    `to_approver_name` and the application's `current_approver` moves; create
    with each invalid input → 400; history list + `?application=` filter +
    retrieve; admin renders and `has_delete_permission` False.
- Frontend: `pending-applications-table.test.tsx`, `reassignment-table.test.tsx`,
  `reassignment-form.test.tsx` (renders, submit shape from
  `reassignments-client`, mandatory-reason rendering, current-approver
  exclusion).

### 8. Docs

- `context/specs/09-hr-emergency-reassignment-spec.md` (this file).
- `context/progress-tracker.md`: Unit 9 complete; record the big decisions
  (`pending` = `submitted`, `current_approver` spine + `Reassignment` history,
  HR-only, `is_approver_user` reuse, no delegation consultation — Unit 21
  boundary, no notifications/audit app here).
- Root `README.md` API table: add the `/api/v1/reassignments/` rows.

## Verification

- `uv run manage.py test --noinput` green (existing 265 + new reassignment tests).
- `npm test` green, `npm run lint` and `npm run build` green.
- `npm run dev` against a seeded backend with a submitted application: HR opens
  the Reassignments page (queue shows the pending application as "Unassigned",
  history empty), reassigns it to the HOD with a mandatory reason, the queue
  badge updates to the HOD, history lists the row, reassigning again to the same
  HOD returns the conflict error, and a draft application is not listed and
  cannot be reassigned.

## Implementation notes (2026-09-18)

- Because Unit 13 applications have no stage/approver concept yet,
  "requiring intervention" is truthfully just "submitted". This unit plants the
  `current_approver` spine + `Reassignment` history that Unit 21 (workflow →
  approver integration) and Unit 15 (employee tracking "responsible approver")
  consume, mirroring how Unit 8 planted `active_delegation_for`.
- Reuses `workflows.services.is_approver_user` for the replacement-approver
  check (code-standards: one authoritative implementation).
- Mandatory-reason rule mirrors the delegation decision-reason pattern.
- Cross-track note: adding the nullable `current_approver` FK to the merged
  `LeaveApplication` is additive and does not change the Unit 13 serializer
  contract, but the other developer should be aware before merging.

## Follow-ups (2026-09-26)

Unit 9 shipped every deliverable above, so the audit that followed was about the
three things this spec explicitly deferred and that no later unit picked up.

### 1. Reassignment email — the deferral to Unit 22 never happened

Unit 22 covers `DECISION_RECORDED` and `APPLICATION_FINALISED` only; it never
mentions reassignment. So a reassignment silently moved an application between
two people's queues and told neither. Both are now notified on commit, through
`notifications/reassignments.py`, on the same discipline as the delegation path:

* the **replacement** learns they now own a pending application they did not ask
  for, and the **previous** approver learns it was taken off them before they
  acted;
* an *initial* assignment (`from_approver is None`) mails only the new approver —
  nobody lost a queue that never existed;
* the **employee is deliberately not mailed**: they already see the reassignment
  on their tracking timeline as a `reassigned` event (Unit 15, which resolves the
  HR reason as the event comment), so the only thing an email would add is a
  repeat of it.

`NotificationOutbox` gained a **third subject family**, `reassignment`, rather
than hanging these rows off `application`. The application family's constraint is
unique per `(application, kind, cycle, role)`, and an application can be
reassigned several times in one submission cycle — so an application-keyed row
would have made every reassignment after the first silently idempotent-suppress
against the first. See `notifications/migrations/0003_notificationoutbox_reassignment.py`.

### 2. The intervention queue now reports the *acting* approver

`GET /api/v1/reassignments/pending/` gained `acting_approver`,
`acting_approver_name` and `is_delegated` alongside the existing
`current_approver`. This unit wrote the queue assuming "pending" meant the
responsible approver acts, which was true when it was written and stopped being
true in Unit 21.

Without it, HR's queue showed "Jane Dean" for an application that Bob HOD was
actually deciding, and reassigning it to a *third* approver looked like it
worked while the same delegate kept acting. The HR queue and the reassignment
form both now name the delegate and who they are covering for.

Resolution is bulked through `acting_approver_map()` so the queue stays a fixed
number of queries — one delegation pass plus one user-name pass for the whole
page, not two per row. `acting_approver_identity()` is the single-row equivalent
for callers off-queue, and a test asserts the two agree.

### 3. Tests pinning the interaction

The behaviour above was correct but unpinned, so it read as an accident:

* `workflows/tests_routing.py` — reassigning *away* from a delegated approver
  hands over cleanly (the old cover no longer matches the moved spine);
  reassigning *to* an away approver leaves their delegate acting; and the bulk
  resolver agrees with `acting_approver_id` row for row.
* `workflows/tests.py` — the pending payload reports the delegate, respects
  delegation windows that have not started or have ended, and reports `None` for
  an unassigned application.
* `notifications/tests_reassignments.py` — the recipient matrix, idempotency,
  two-reassignments-of-one-application, failure isolation, the on-commit
  boundary, a rejected reassignment emitting nothing, and the two new
  exactly-one-subject constraints.
