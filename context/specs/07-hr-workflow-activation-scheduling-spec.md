# Unit 7 — HR Workflow Activation & Scheduling

> **Partly superseded.** The activation gate described here is now `Team.status`
> and lives on the team; a team owns its chain and is activated as a whole, and
> there is no separate workflow activation screen. The scheduling/effective-date
> model and the validation rules still stand. For the current contract see
> `context/architecture.md` §12.12.

## Goal

Add workflow administration capabilities on top of the Unit 6 workflow
builder (build-plan §4, Unit 7):

- Required-stage validation.
- Missing approver validation.
- Inactive approver validation.
- Invalid configuration detection.
- Conflicting workflow detection.
- Future-effective workflow scheduling.
- Active/inactive workflow states.

Workflow configuration must be validated **before activation or scheduling**.

## Assumptions made (flag if wrong)

- **Activation = an effective date on the workflow.** `Workflow` gains two
  fields; there is no separate "activate" endpoint, because `PATCH` already
  updates the whole workflow and everything that must be validated lives on
  the same row. Scheduling a workflow **is** setting its `effective_from`:
  - `effective_from` (DateField, nullable, blank). `null` = **draft** (built
    but never scheduled; never applies; never conflicts).
  - `is_active` (BooleanField, default `True`). Meaningful once
    `effective_from` is set. A workflow only applies while `is_active` is
    `True`.
  - Derived, read-only `state` reported by the API (used by the UI):
    `draft` (`effective_from` null), `scheduled` (`effective_from` future,
    active), `active` (`effective_from` past/today, active), `inactive`
    (`is_active` False with an `effective_from` set).

- **Approver availability is a role-capacity check.** Stages store approver
  roles, not persons (Unit 6 decision; the *specific* approver for a real
  application is resolved in Unit 21). Activation therefore requires, for
  every stage role in the workflow, that **at least one active user with that
  role exists** (`User.is_active = True`, role set). This covers both
  "missing approver" (no user has the role) and "inactive approver" (the
  role exists but all its users are deactivated), and names the offending
  role(s) in the error.

- **Conflicting workflows are scope-overlap conflicts.** Two workflows
  conflict when both apply to the same employee, i.e. when a workflow could
  match an employee today or in the future. A workflow's scope is its
  `employee_category` (blank = any) **and** `department` (blank = any). Two
  scopes overlap when category matches (equal or either is blank) **and**
  department matches (equal or either is blank). So "Any category / Any
  department" overlaps "academic / Faculty of Science", and "academic / *"
  overlaps "academic / Faculty of Science". Activating or scheduling a
  workflow is rejected (400) if any **other** workflow with an overlapping
  scope is already applying now or in the future (has `effective_from` set
  and `is_active`). To swap a scope, HR deactivates the existing workflow
  first. Two drafts (no `effective_from`) for the same scope never conflict.

- **Editing re-validates.** Any create/update that carries an `effective_from`
  (activating, rescheduling, or editing an already-scheduled/active workflow)
  is validated. Deactivation (`is_active` False) and draft edits are always
  allowed — deactivating is the intentional way to free a scope.

- **No scheduler job and no retroactive concern.** There are no submitted
  applications yet, so nothing references a workflow row and activation is
  simply the stored effective date (lazy "is it live today?" is derived, not
  a background flip). Historical integrity at the application level is
  untouched (architecture.md §11; that materializes in Unit 21).

- **Nothing is seeded** (Unit 6 decision stands). `seed_dev_users` already
  creates one active user per role, which is enough to activate the documented
  example sequences.

## Visible result

HR can validate and schedule a workflow for a future effective date: the
workflow list shows each workflow's state and effective date, and activating
a broken or conflicting workflow shows the backend validation errors in the
form.

## Dependencies

- Unit 6 (workflow builder, models, serializer, admin, frontend).
- Unit 2 (roles, `User.is_active`, HR permission, seed infra).

## API contract

Extends the existing `/api/v1/workflows/` contract (HR-only `IsHRRole`;
PATCH replaces stages wholesale):

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/workflows/` | List workflows (paginated, by `name`; each row now includes `state`, `effective_from`, `is_active`) |
| POST | `/api/v1/workflows/` | Create a workflow (draft unless `effective_from` is sent) |
| GET | `/api/v1/workflows/{id}/` | Retrieve one workflow with its stages |
| PATCH | `/api/v1/workflows/{id}/` | Update a workflow (replaces stages; `effective_from`/`is_active` may be sent) |

Object shape (additions on top of Unit 6):

```json
{
  "id": 4,
  "name": "Administration approval",
  "employee_category": "administration",
  "department": "",
  "effective_from": "2026-12-01",
  "is_active": true,
  "state": "scheduled",
  "stages": [
    { "id": 1, "order": 1, "approver_role": "supervisor" },
    { "id": 2, "order": 2, "approver_role": "hod" },
    { "id": 3, "order": 3, "approver_role": "registrar" },
    { "id": 4, "order": 4, "approver_role": "dvc" }
  ]
}
```

Validation (new, on top of Unit 6 rules):

- `effective_from` may be null/blank (draft) or an ISO date. A blank/draft
  create/update is always valid (drafts are never blocked by approver or
  conflict checks).
- When `effective_from` is set and `is_active` is `True`, the workflow must:
  - Have at least one stage (already enforced by Unit 6).
  - Have an active user for each stage's `approver_role`; otherwise 400 with
    e.g. `{"stages": "No active Dean exists for stage 3."}` (one error naming
    the first offending stage) or a single `{"detail": "..."}` listing the
    missing roles.
  - Not overlap any other applying workflow's scope; otherwise 400
    `{"effective_from": ["Activating this workflow conflicts with \"Academic approval\" (active since 2026-01-01)."]}`.
- Setting `is_active` False (deactivate) is always allowed. Setting
  `is_active` True when `effective_from` is null is accepted but has no
  effect until an effective date is set (the workflow stays a draft).
- Errors follow Unit 1 conventions: `{"detail": "..."}` for single errors,
  `{"field": ["..."]}` for validation.

## Implementation

Verify each backend step before frontend work begins.

### 1. Model (`workflows/models.py`)

- `Workflow.effective_from` = `DateField(null=True, blank=True)`
  (help text: blank keeps the workflow a draft; set a date to schedule it).
- `Workflow.is_active` = `BooleanField(default=True)`.
- Add a `state` property/helper (`draft`/`scheduled`/`active`/`inactive`) and
  a `scope` tuple helper (`(employee_category or "", department or "")`)
  used by the conflict checker. Keep these thin; today's date comes from
  `timezone.localdate()` (Unit 3 convention).
- Migration `0002_workflow_effective_from_workflow_is_active` (via
  `makemigrations workflows`).

### 2. Services (`workflows/services.py`)

- `scopes_overlap(a, b) -> bool` — category equal-or-any and department
  equal-or-any.
- `missing_approver_roles(stages) -> list[str]` — stage roles that have no
  active `User` with that role (`User.objects.filter(role=role, is_active=True)
  .exists()`).
- `find_conflicting_workflow(workflow_pk, scope) -> Workflow | None` —
  any other workflow with an overlapping scope that is applying
  (`effective_from` set, `is_active` True), excluding `workflow_pk`.
- `validate_workflow_for_activation(workflow_pk, scope, stages) -> list[str]`
  — returns human-readable errors (missing approver roles, conflict) so the
  serializer and the admin form share one authoritative implementation.

### 3. Serializer (`workflows/serializers.py`)

- Add `effective_from`, `is_active` (writable), `state` (read-only, from the
  model helper).
- In `validate`: when the submitted workflow has `effective_from` set and
  `is_active` (using the existing `_value` merge of submitted + instance),
  call `validate_workflow_for_activation` and map returned messages to
  `ValidationError` (conflict → field error on `effective_from`; missing
  roles → `detail`).
- `create`/`update` stay atomic as in Unit 6.

### 4. Admin (`workflows/admin.py`)

- Add `effective_from` and `is_active` to `WorkflowAdmin.list_display`
  (or a `state` column), `list_filter` for `is_active`, and the conflict /
  approver checks to `WorkflowAdminForm.clean()` using the same services
  (mirror the Unit 5 admin-form-guard pattern). Reuse `stage_summary`.
- Keep `has_delete_permission=False`.

### 5. Views + URLs

- No routing changes. `WorkflowViewSet` already exposes exactly the four
  operations; the serializer change carries the new fields.

### 6. Seed

- No workflow seeding, and no approver seeding changes (seed users already
  give every role an active representative). Existing `seed_dev_users`
  behavior is unchanged.

### 7. Frontend

- `lib/workflows.ts` + `lib/workflows-client.ts`: add `effective_from`/
  `is_active`/`state` to the `Workflow` type; add `effective_from?`/
  `is_active?` to `WorkflowInput`; add a `workflowStateLabel` helper and
  status badge styling helper (mirror `leaveRuleStatus`/table badges).
- `workflow-table.tsx`: add "Effective from" and a "State" column showing a
  Draft/Scheduled/Active/Inactive badge.
- `workflow-form.tsx`: add a date input "Effective from" (empty = draft) and
  an "Active" checkbox (shown once a date is set / editing a scheduled or
  active workflow); keep the submit shape unchanged otherwise; backend
  validation errors (missing approvers, conflicts) render in the existing
  error block.
- Pages unchanged (existing list/new/edit under
  `/dashboard/hr-admin/workflows`), since the form and table carry the new
  controls.
- No new sidebar/HR-index items (already added in Unit 6).

### 8. Tests

- `backend/workflows/tests.py`:
  - Model/services: `scopes_overlap` equal/any combinations; `missing approver
    roles` returns the roles; conflict lookup excludes self and only considers
    applying workflows; `validate_workflow_for_activation` messages.
  - API: schedule with `effective_from` + `is_active` succeeds (state
    `scheduled` for a future date, `active` for today); draft create succeeds
    with no approvers needed; activate without an active approver for a stage
    role → 400 naming the role; activate overlapping scope (including
    any-vs-specific) → 400 naming the conflict; deactivate frees the scope
    (then a second workflow can activate); editing an active workflow that now
    conflicts → 400; `state` derived correctly in responses.
  - Admin: `WorkflowAdminForm` rejects conflict and missing-approver
    activations, allows drafts.
- Frontend: `workflow-form.test.tsx` gains effective-from/active assertions
  and prefill-on-edit; `workflow-table.test.tsx` gains state/effective-date
  columns.

### 9. Docs

- `context/specs/07-hr-workflow-activation-scheduling-spec.md` (this file).
- `context/progress-tracker.md`: Unit 7 complete; note person resolution stays
  Unit 21 and applications still have no workflow binding.
- Root `README.md` API table: extend the `/api/v1/workflows/` rows with the
  new fields; note activation validation on POst/PATCH.

## Verification

- `uv run manage.py test --noinput` green (existing 171 + new backend tests).
- `npm test` green, `npm run lint` and `npm run build` green.
- `npm run dev` against a seeded backend: HR schedules a workflow for a
  future date (Scheduled state), sees the badge and effective date in the
  list, gets the missing-approver error when a role has no active user,
  gets the conflict error when a scope overlaps an active workflow,
  deactivates a workflow and then schedules a replacement in the same scope.

## Implementation notes (2026-09-17)

- `validate_workflow_for_activation` returns `ActivationIssue(field, message)`
  records rather than the `list[str]` sketched above so the serializer can map
  each issue to `effective_from` (scope conflict) or `detail` (missing approver
  roles) from the single shared implementation. The admin form joins the
  messages for its non-field error.
- DRF normalizes every value in a serializer `ValidationError` dict into a
  list, so the missing-approver error is `{"detail": ["No active user exists
  for: Dean."]}` rather than the single-string `{"detail": "..."}` example
  above. The frontend `apiErrorMessage` helper still surfaces it.
- PATCH keeps the Unit 6 "replace stages wholesale" contract, so deactivation
  (`is_active: false`) and draft edits must resend the stage list.