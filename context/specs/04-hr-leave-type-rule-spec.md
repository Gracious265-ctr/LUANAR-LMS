# Unit 4 — HR Leave Type and Rule Management

## Goal

Create the HR leave-rule configuration experience: HR can view, create, and edit
leave types and their configurable rules. Each leave type supports a configured
maximum duration, eligibility, minimum notice period, supporting-document
requirement, and whether it consumes annual entitlement, all effective-dated so
rule changes are future-effective and never silently alter already-submitted
applications (build-plan §4; requirements: configurable leave types and rules,
"minimum notice period", "eligibility", "supporting documents", "consumes annual
entitlement").

The system's configurable leave types are:

- Annual leave.
- Maternity leave.
- Paternity leave.
- Compassionate leave.
- Additional HR-defined leave types.

Initial special-leave defaults (must be seeded, HR-configurable afterwards):

- Maternity → 90 days.
- Paternity → 10 days.

## Assumptions made (flag if wrong)

- **Domain home:** leave types and their rules live in the `leave` app. Unit 3's
  entitlements already established `leave/` as the leaf domain home for
  "leave rules"; leave types are the same rule family, so they belong beside
  `GradeEntitlement` rather than a new app. The active leave types and a
  single HR-manageable leave-rule table make up the Unit 4 model.
- **Model shape (two concepts, not one):** a leave *type* is a named registry
  entry (`annual`, `maternity`, `paternity`, `compassionate`, plus any HR-created
  additions); a *rule* is the effective-dated configuration for that type. This
  matches "Additional HR-defined leave types" (types are added) and "effective
  dates / future-effective rule changes" (rules change over time) in the build
  plan. A type's current rule is resolved by picking the newest `effective_from`
  on or before the query date — a direct parallel to Unit 3's
  `effective_from` resolution.
- **No overlap constraint for leave rules:** Unit 3 rejects overlapping *grade
  ranges* because ranges are exclusive bands. Leave-rule versions are sequential
  versions of the *same* type (no range), so a future-effective edit to a type is
  just a new effective-dated row — overlapping versions are not a conflict. This
  preserves the "future-effective rule changes without rewriting
  already-submitted applications" invariant instead of forcing in-place edits.
- **Eligibility shape:** the source documents specify that eligibility is
  configurable ("configurable eligibility", requirements §... and
  project-overview: "Configurable eligibility") but do not define a closed
  vocabulary (e.g. whether it's per-category, per-grade, or free-form). To avoid
  inventing an entitlement taxonomy, eligibility is stored as an HR-authored
  description string (`eligibility`) that HR writes per leave type. It is shown
  in the rule rows and becomes the input HR edits, leaving the concrete
  eligibility-rule vocabulary to the unit that actually enforces eligibility
  (the leave-application/eligibility-validation unit, which also owns special-
  leave eligibility boundaries). This is the smallest faithful reading and is
  explicitly a TBD-shaped assumption to revisit in that later unit.
- **`consumes_annual_entitlement`:** mirrors the protected rule "Special leave
  must not deduct annual leave unless the configured leave type explicitly
  defines it as annual-leave-consuming." Only the configured boolean governs;
  the backend leave-type endpoint enforces nothing beyond storing the flag now
  (deduction logic is a later unit), but the field is authoritative and
  present so the deduction unit has a single source of truth.
- **No hard delete:** consistent with Units 2–3, destroying a leave rule could
  break historical applications, so `DELETE` is not exposed. Editing a rule (or
  adding a future-effective version) is the change path.
- **Seed:** `seed_dev_users` seeds the four built-in leave types and default
  rules (maternity 90, paternity 10, annual/compassionate with configured days)
  idempotently, so the HR screen starts populated for development/testing without
  overwriting HR edits on re-run.

## Visible result

An HR leave-rule management interface.

## Dependencies

- Unit 2 (HR role, employee directory patterns, seed infra).
- Unit 3 (HR-only CRUD/viewset structure, effective-dated resolution service
  pattern, frontend proxy/form/table conventions).

## API contract

All endpoints require a valid JWT and the `hr` role (`IsHRRole`), mirroring
`leave/views.py` from Unit 3. Namespaces are `/api/v1/leave-types/` and
`/api/v1/leave-rules/`.

### Leave types (`LeaveType`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/leave-types/` | List leave types (paginated) |
| POST | `/api/v1/leave-types/` | Create a leave type |
| GET | `/api/v1/leave-types/{id}/` | Retrieve one leave type |
| PATCH | `/api/v1/leave-types/{id}/` | Rename / update one leave type |

Response object (snake_case, DRF conventions):

```json
{
  "id": 1,
  "code": "maternity",
  "name": "Maternity leave"
}
```

Validation:

- `name` required, non-blank.
- `code` optional; defaults to a slug-like value derived from `name`; must be
  unique when provided.

### Leave rules (`LeaveRule`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/leave-rules/` | List rules (paginated, newest effective first; `leave_type=`, `effective=current|upcoming|all`) |
| POST | `/api/v1/leave-rules/` | Create a rule |
| GET | `/api/v1/leave-rules/{id}/` | Retrieve one rule |
| PATCH | `/api/v1/leave-rules/{id}/` | Partially update one rule (no effective-date overlap validation; versions are sequential) |

Response object:

```json
{
  "id": 1,
  "leave_type": 1,
  "leave_type_code": "maternity",
  "leave_type_name": "Maternity leave",
  "max_duration_days": 90,
  "eligibility": "Female employees at any grade",
  "min_notice_days": 5,
  "requires_supporting_document": true,
  "consumes_annual_entitlement": false,
  "effective_from": "2026-01-01"
}
```

Validation (mirrors Unit 3's serializer conventions):

- `leave_type` required and must exist.
- `max_duration_days >= 1`.
- `effective_from` required.
- `min_notice_days >= 0`.
- Errors follow Unit 1 conventions: `{"detail": "..."}` for single errors,
  `{"field": ["..."]}` for validation.

## Implementation

Work in the following order; verify each backend step before frontend work begins.

### 1. Models

- `leave/models.py`:
  - `LeaveType`: `name` (CharField, unique), `code` (SlugField, unique, blank;
    `save()` fills from `name` if blank). `Meta.ordering = ["name"]`.
  - `LeaveRule`: `leave_type` (FK `LeaveType`, related_name `rules`),
    `max_duration_days` (PositiveIntegerField), `eligibility` (TextField,
    blank), `min_notice_days` (PositiveIntegerField, default 0),
    `requires_supporting_document` (BooleanField, default False),
    `consumes_annual_entitlement` (BooleanField, default False),
    `effective_from` (DateField).
    DB `CheckConstraint`s (Django 6.1 `condition=` kwarg):
    `max_duration_days >= 1`, `min_notice_days >= 0`.
    `Meta.ordering = ["-effective_from", "leave_type"]`.
- Migration `0002_leavetype_leaverule` (created via `makemigrations leave`).

### 2. Service (resolution)

- `leave/services.py`: extend with
  `resolve_leave_rule(leave_type, as_of=None) -> LeaveRule | None` returning the
  newest rule for the type whose `effective_from <= as_of` (default: today). Add
  a `normalize_leave_code` helper used by the serializer's code normalization.

### 3. Admin

- `leave/admin.py`: register `LeaveType` and `LeaveRule` with `list_display`,
  `search_fields`, `list_filter`, ordering.

### 4. Serializers

- `leave/serializers.py`:
  - `LeaveTypeSerializer` (name/code; validates unique code, auto-fills from
    name via `save()`).
  - `LeaveRuleSerializer` (all rule fields + read-only `leave_type_code` /
    `leave_type_name`; validates `max_duration_days >= 1`, requires
    `effective_from`, `leave_type` exists).

### 5. Views

- `leave/views.py`: `LeaveTypeViewSet` and `LeaveRuleViewSet`
  (list/create/retrieve/patch only, HR-only `IsHRRole`, no delete), mirroring
  `GradeEntitlementViewSet` from Unit 3.

### 6. URLs

- `leave/urls.py`: register `leave-types` (basename `leave-type`) and
  `leave-rules` (basename `leave-rule`) routers alongside `entitlements`.

### 7. Seed

- `seed_dev_users`: idempotently seed the four leave types
  (`annual`, `maternity`, `paternity`, `compassionate`) and default rules
  (maternity → 90 days, paternity → 10 days effective today; annual and
  compassionate with sensible default durations) via `get_or_create` keyed on
  `leave_type` + `effective_from`. Re-running re-seeds without creating
  duplicates or overwriting HR edits.

### 8. Frontend

- `lib/leave-rules.ts`: authoritative TS types (`LeaveType`, `LeaveTypeInput`,
  `LeaveRule`, `LeaveRuleInput`, `LeaveRuleResolution`, list responses) and
  helpers `listLeaveTypes`, `createLeaveType`, `listLeaveRules`,
  `getLeaveRule`, `createLeaveRule`, `updateLeaveRule`.
- Route-handler proxies (mirror Unit 2/3 employees/entitlements proxies):
  - `app/api/hr/leave-types/route.ts` — POST.
  - `app/api/hr/leave-types/[id]/route.ts` — PATCH.
  - `app/api/hr/leave-rules/route.ts` — POST.
  - `app/api/hr/leave-rules/[id]/route.ts` — PATCH.
- Components under `components/hr/`:
  - `leave-type-table.tsx` and `leave-type-form.tsx`.
  - `leave-rule-table.tsx` and `leave-rule-form.tsx` (client create/edit forms
    posting to the proxies; leave-type selection via an HR-loaded dropdown of
    leave types).
- Pages under `app/(dashboard)/dashboard/hr-admin/leave-rules/`:
  - `page.tsx` (list with leave-type filter and "current/upcoming" tabs),
  - `new/page.tsx`,
  - `[id]/edit/page.tsx`.
  And a `leave-types` index (list + create/edit) or a combined leave-rule
  settings index with leave-type management.
- Add sidebar items ("Leave Rules", "Leave Types") and HR index cards, reusing
  existing `components/dashboard/dashboard-shell.tsx` nav patterns.

### 9. Tests (`leave/tests.py`)

- Service: default rules resolve correctly (maternity→90, paternity→10);
  unmapped type → None; newest-effective-wins on future edits.
- API: 401 unauthenticated; 403 for non-HR; HR CRUD for both resources;
  validation failures (missing name, duplicate code, missing leave_type,
  max_duration < 1, missing effective_from); filter by leave type and
  effective status; `DELETE` → 405.
- Seed: `seed_dev_users` run twice seeds exactly these leave types/rules
  idempotently.

### 10. Docs

- Add `context/specs/04-hr-leave-type-rule-spec.md` (this file).
- Update `context/progress-tracker.md` (Unit 4 complete; `leave` no longer
  "entitlement-only").
- Update root `README.md` API table with the new `/api/v1/leave-types/` and
  `/api/v1/leave-rules/` endpoints and project-structure note.

## Verification

- `uv run manage.py test` green (existing 55 + new leave-type/rule tests).
- `npm test` green, `npm run lint` and `npm run build` green.
- `npm run dev` against a seeded backend: HR sees seeded leave types/rules;
  create/edit a rule; non-HR 403s.
