# Unit 6 — HR Workflow Builder

## Goal

Create the HR approval-workflow configuration experience (build-plan §4,
Unit 6):

- Configure approval workflows based on **employee category** and
  **department/faculty**.
- Configure an ordered sequence of **approval stages**.
- Support the documented stage roles (Supervisor, HOD, Dean, Registrar, DVC).
- Every configured stage is mandatory and executes sequentially.

The unit delivers the *workflow builder* only: the models, HR CRUD, and the
"complete approval sequence" UI. Activation, scheduling, approver-availability
validation, conflict detection, and active/inactive states are Unit 7; the
actual resolution of "which person approves this employee's application" is
Unit 21 (Workflow-to-Approver Integration) and is out of scope here.

## Assumptions made (flag if wrong)

- **Domain home: the `workflows` app.** architecture.md designates
  `workflows/` as "Approval workflow configuration and processing", the app
  already exists in `INSTALLED_APPS` as a stub, and the project file
  organization rules say "New Django apps must represent a meaningful domain
  responsibility". Unlike Unit 5 (where financial years joined the existing
  `leave` app), the workflow domain gets its real home here.
- **A configured stage stores an approver role, not a named person.** The
  documented sequences are role-based ("Employee → Supervisor → HOD → Registrar
  → DVC"). Each `WorkflowStage` records `approver_role`
  (`supervisor`/`hod`/`dean`/`registrar`/`dvc`/`hr`). The *specific* approver
  for a real employee's application (their supervisor, their department's HOD,
  the Registrar, the DVC) is resolved at application-processing time (Unit 21).
  Unit 7 later validates that approvers exist for each stage.
- **Workflow matching scope is category + department.** A workflow applies to
  employees whose `EmployeeProfile.category` matches `employee_category`
  (blank = any) **and** whose `EmployeeProfile.department` string equals
  `department` (blank = any). `department` is free text today, so matching is
  exact-string; a department-scoped workflow only applies when
  `EmployeeProfile.department` matches exactly.
- **Stages must be sequential and complete.** A workflow requires at least one
  stage. The serializer re-normalizes the submitted stage list to `1..N` in
  submission order and rejects duplicate approver roles within one workflow
  (mirrors the documented sequences and avoids ambiguous duplicate-role routing).
  The DB also enforces unique `(workflow, order)` and `order >= 1`.
- **One workflow row owns its whole stage list.** The serializer is nested and
  writable; a `PATCH` replaces the stage list wholesale. Stage-level history /
  audit does not exist yet (delegation, reassignment, and audit are later
  units), so wholesale replacement is safe.
- **No effective-dating or active flag in this unit.** `effective_from`,
  active/inactive states, activation validation, and conflict detection are
  Unit 7. Unit 6 only builds and edits sequences. This keeps Unit 6 free of
  speculative scheduling columns.
- **No workflow seeding — start empty** (user decision, 2026-09-17). Like Unit 5,
  workflows are organizational configuration and LUANAR's real approval
  sequences are not documented as defaults (project-overview.md's sequences are
  only examples). HR creates the first workflows. Existing `seed_dev_users`
  behavior is unchanged.
- **Workflow name is unique** as a simple
  structural guard for HR references (workflows are edited, not deleted).
- **No hard delete** (consistent with Units 2–5): future applications reference
  a workflow, so `DELETE` is not exposed.
- **No resolution endpoint.** A `resolve`/`current` workflow-for-employee
  endpoint is Unit 21's concern; nothing consumes workflow resolution yet.

## Visible result

An HR workflow configuration interface showing a complete approval sequence
per workflow.

## Dependencies

- Unit 2 (HR role, `IsHRRole`, `EmployeeProfile.category`/`department`, seed
  infra, frontend proxy conventions).
- Unit 3 (HR-only viewset/serializer structure, admin form guard pattern).
- Unit 4 (split server-safe/client lib pattern, frontend table/form
  conventions).
- Unit 5 (same for the nested list of related rows).

## API contract

All endpoints require a valid JWT and the `hr` role (`IsHRRole`), mirroring
Units 3–5. Namespace: `/api/v1/workflows/`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/workflows/` | List workflows (paginated, by `name`) |
| POST | `/api/v1/workflows/` | Create a workflow with its ordered stages |
| GET | `/api/v1/workflows/{id}/` | Retrieve one workflow with its stages |
| PATCH | `/api/v1/workflows/{id}/` | Update a workflow (replaces its stages) |

Request/response object (snake_case, DRF conventions):

```json
{
  "id": 1,
  "name": "Administration approval",
  "employee_category": "administration",
  "department": "",
  "stages": [
    { "id": 1, "order": 1, "approver_role": "supervisor" },
    { "id": 2, "order": 2, "approver_role": "hod" },
    { "id": 3, "order": 3, "approver_role": "registrar" },
    { "id": 4, "order": 4, "approver_role": "dvc" }
  ]
}
```

`employee_category` is `""` (any category), `"academic"`, or
`"administration"`. `department` blank means applies to any department.

Validation:

- `name` required, trimmed, unique (excluding self).
- `employee_category` must be blank or one of the two category codes.
- `department` may be blank or an exact department string.
- `stages` required, at least one entry.
- Each stage: `approver_role` must be one of
  `supervisor`/`hod`/`dean`/`registrar`/`dvc`/`hr`; `order` must be a positive
  integer; orders within a workflow must be unique; approver roles within a
  workflow must not repeat.
- Submitted stage order is preserved and re-normalized to `1..N`.
- Errors follow Unit 1 conventions: `{"detail": "..."}` for single errors,
  `{"field": ["..."]}` for validation.

## Implementation

Work in the following order; verify each backend step before frontend work begins.

### 1. Models (`workflows/models.py`)

- `Workflow`:
  - `name` (CharField max_length 200, unique).
  - `employee_category` (CharField max_length 20, blank; choices
    `academic`/`administration` taken from `EmployeeProfile.Category`).
  - `department` (CharField max_length 200, blank).
  - `Meta.ordering = ["name"]`.
- `WorkflowStage`:
  - `workflow` FK (`on_delete=CASCADE`, `related_name="stages"`).
  - `order` (PositiveIntegerField).
  - `approver_role` (CharField max_length 20, choices built from
    `User.Role` entries restricted to the approver roles).
  - `Meta.ordering = ["order"]`; `CheckConstraint` `order >= 1`;
    `UniqueConstraint(fields=["workflow", "order"])`.
- Migration `0001_initial` (created via `makemigrations workflows`).

### 2. Serializers (`workflows/serializers.py`)

- `WorkflowStageSerializer`: `id` (read-only), `order`, `approver_role`.
- `WorkflowSerializer` (nested, writable stages):
  - Fields: `id`, `name`, `employee_category`, `department`, `stages`.
  - `validate`: required trimmed unique name; category must be blank or a valid
    category; department trimmed; stages required and non-empty; approver roles
    must not repeat; orders positive and unique.
  - `create`/`update`: wrap in `transaction.atomic`; save the workflow; replace
    the stage list (update deletes existing stages) re-normalized to `1..N` in
    submission order.
- Shared stage-sequence checks reused by the admin guard (single authoritative
  implementation in the serializer or `workflows/services.py`).

### 3. Services (`workflows/services.py`)

- A small `normalize_stage_sequence(stages)`-style helper used by the
  serializer to validate/renormalize the submitted stage list, and by the
  admin form guard — mirrors how Unit 3/5 shared overlap checks between
  serializer and admin. No resolution logic yet.

### 4. Admin (`workflows/admin.py`)

- Register `Workflow` with a `TabularInline` for stages (`extra=1`,
  `min_num=1`, `validate_min=True`, `ordering=["order"]`), an admin form guard
  enforcing the non-empty/duplicate-role/sequential rules, and
  `has_delete_permission=False`.
- Inline form guard: `order >= 1`; inline formset `clean` rejects duplicate
  approver roles within the workflow.

### 5. Views + URLs

- `workflows/views.py`: `WorkflowViewSet`
  (list/create/retrieve/patch only, HR-only `IsHRRole`, no delete) mirroring
  the existing viewsets. `get_queryset` prefetches `stages`
  (`prefetch_related("stages")`).
- `workflows/urls.py`: `SimpleRouter` registering `workflows` (basename
  `workflow`).
- `config/urls.py`: add `path("api/v1/", include("workflows.urls"))`.

### 6. Seed

- No workflow seeding (see assumptions — start empty). Existing
  `seed_dev_users` behavior is unchanged.

### 7. Frontend

- `lib/workflows.ts` (server-safe): TS types `Workflow`, `WorkflowStage`,
  `WorkflowStageInput`, `WorkflowInput`, `WorkflowListResponse`; read helpers
  `listWorkflows`, `getWorkflow`; small `approverRoleLabel`/`workflowCategoryLabel`
  helpers for the UI.
- `lib/workflows-client.ts` (client-safe): `createWorkflow`, `updateWorkflow`
  posting to the route-handler proxies — split exactly as
  `leave-rules.ts`/`leave-rules-client.ts` so the client forms never pull
  `next/headers` into the bundle.
- Route-handler proxies (`app/api/hr/workflows/route.ts` POST,
  `app/api/hr/workflows/[id]/route.ts` PATCH), mirroring Units 2–5.
- Components under `components/hr/`:
  - `workflow-table.tsx` (name, scope/category, sequence summary rendered as
    role labels joined with arrows, edit link, empty state).
  - `workflow-form.tsx` (client create/edit form: name, category select with an
    "Any category" option, department input, and an ordered stage builder with
    add / remove / move-up / move-down controls, approver-role select per
    stage; submit posts the ordered stage list).
- Pages under `app/(dashboard)/dashboard/hr-admin/workflows/`:
  - `page.tsx` (list with "New workflow" button).
  - `new/page.tsx`, `[id]/edit/page.tsx`.
- Add a sidebar item ("Workflows", lucide `Workflow`) and an HR index card,
  reusing existing dashboard shell patterns. Update the HR index footer note
  (remove "workflows" from the "later units" list).
- All pages guard with `getCurrentUser()` → redirect `/login` and
  `user.role !== "hr"` → redirect `/dashboard`, matching existing pages.

### 8. Tests

- `workflows/tests.py`:
  - Model/DB: stage order unique per workflow; order `>= 1` constraint.
  - Service: `normalize_stage_sequence` accepts a good list, rejects empty /
    duplicate roles / duplicate or non-positive orders, renumbers to `1..N`.
  - API: 401 unauthenticated; 403 for non-HR; HR create with stages; retrieve
    returns ordered stages; list ordered by name; PATCH replaces stages;
    validation failures (missing name, duplicate name, no stages, invalid
    approver role, duplicate role, duplicate order, invalid order); `DELETE` →
    405.
  - Admin: workflow form guard rejects duplicate roles / empty stages; inline
    rejects `order < 1`.
- No seed tests (nothing new is seeded).
- No `resolve` endpoint tests (out of scope).

### 9. Docs

- Add `context/specs/06-hr-workflow-builder-spec.md` (this file).
- Update `context/progress-tracker.md` (Unit 6 complete; note that stage
  resolution for real applications and workflow activation/validation remain
  for Units 21 and 7).
- Update root `README.md` API table with the `/api/v1/workflows/` endpoints.

## Verification

- `uv run manage.py test --noinput` green (existing 144 + new workflow tests).
- `npm test` green, `npm run lint` and `npm run build` green.
- `npm run dev` against a seeded backend: HR sees the Workflows page (empty
  state), creates a workflow with an ordered stage list, reorders/removes stages
  on edit, sees the sequence in the list; non-HR 403s; empty/duplicate/invalid
  stages are rejected with backend errors shown in the UI.