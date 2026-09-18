# Unit 3 — HR Grade and Annual Entitlement Configuration

## Goal

Create the HR grade/entitlement configuration experience: HR can view, create, and
edit effective-dated grade-range to annual-entitlement rules and see how an
employee's grade resolves to an annual-leave entitlement. The system determines an
employee's entitlement from the configured grade rather than allowing HR to
manually edit an employee's balance (build-plan §4, Unit 3).

Initial configuration:

| Grade range | Annual days |
|-------------|-------------|
| A–C         | 21          |
| D–G         | 24          |
| H–U         | 30          |

## Assumptions made (flag if wrong)

These reflect decisions the source documents leave open. They are the
implementation boundary of Unit 3 only; each is revisited by its owning unit.

- **Domain home:** the entitlement-rule model lives in the `leave` app.
  `code-standards.md` assigns "Leave applications, leave types, balances, and
  leave rules" to `leave/`; grade-based annual entitlement is a leave rule that
  feeds leave-balance logic, so it lives with the domain logic that consumes it.
  The `users` app keeps responsibility for employee identity (including the
  `grade` text field already on `EmployeeProfile`). If review prefers the model
  under `users`, it can move with no API change.
- **Model shape:** a `GradeEntitlement` row defines one grade range
  (`grade_start`–`grade_end`), an annual `days` value, and an `effective_from`
  date. Grade values are normalized (trimmed, upper-cased) and compared as
  case-insensitive string ranges — covering the single-letter LUANAR A–U bands
  referenced by the docs without inventing a fixed grade master list.
- **No overlapping ranges (supersedes the original future-effective plan):** a
  new or edited rule is rejected when its range overlaps *any* existing rule,
  regardless of `effective_from`. A band's entitlement is therefore changed by
  **editing the existing rule in place**, not by adding a superseding same-range
  rule with a later effective date. Resolution remains deterministic and still
  returns the latest `effective_from` on or before the query date for any
  pre-existing overlapping rows. Recorded in the tracker's Architecture
  Decisions.
- **No hard-delete:** consistent with `code-standards.md`/Unit 2, deleting rules
  could break historical resolution, so `DELETE` is not exposed. Entitlement
  values change by editing the existing rule (audit/version history is a later
  unit).
- **Employee grade assignment:** already delivered by Unit 2 (`EmployeeProfile.grade`).
  Unit 3 keeps that and makes entitlement *determined* from grade via a reusable
  resolution service (`leave/services.py`). A small HR "resolve by grade" widget
  demonstrates determination end-to-end without changing the employee API.
  Surfacing the resolved value on the employee profile/dashboard belongs to
  Units 12/20.
- **Seed:** `seed_dev_users` additionally seeds the three default entitlement
  rules (effective today) idempotently, so the HR screen starts populated for
  development/testing.
- **API namespace:** `/api/v1/entitlements/`, HR-only, mirroring the Unit 2
  employees pattern (page-paginated list, create, retrieve, PATCH; no delete).

## Design

### Backend data model (`leave` app)

```python
class GradeEntitlement(models.Model):
    grade_start = models.CharField(max_length=20)
    grade_end = models.CharField(max_length=20)
    days = models.PositiveIntegerField()
    effective_from = models.DateField()
```

- `save()` trims/upper-cases `grade_start`/`grade_end`.
- DB `CheckConstraint`s guard `days >= 1` and `grade_start <= grade_end`.
- Default `Meta.ordering`: `-effective_from`, then `grade_start`, `grade_end`.

### Entitlement resolution (`leave/services.py`)

```
resolve_grade_entitlement(grade, as_of=None) -> GradeEntitlement | None
```

- Normalizes the grade (strip/upper).
- Considers rules with `effective_from <= as_of` (default: `timezone.localdate()`,
  the configured Africa/Blantyre date) whose range contains the grade.
- Returns the rule with the latest `effective_from`, or `None` when no rule
  applies (unmapped grade, blank grade).
- Helper functions `normalize_grade`, `grade_in_range`, `ranges_overlap`, and
  `find_overlapping_rule` are reused by the serializer and admin so the rule
  lives in exactly one place.

### API contract

All endpoints require a valid JWT and the `hr` role.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/entitlements/` | List entitlement rules (paginated, newest effective first) |
| POST | `/api/v1/entitlements/` | Create an entitlement rule |
| GET | `/api/v1/entitlements/{id}/` | Retrieve one rule |
| PATCH | `/api/v1/entitlements/{id}/` | Partially update one rule |
| GET | `/api/v1/entitlements/resolve/?grade=B[&as_of=YYYY-MM-DD]` | Resolve a grade to its effective entitlement |

Response object (snake_case, DRF conventions):

```json
{
  "id": 1,
  "grade_start": "A",
  "grade_end": "C",
  "days": 21,
  "effective_from": "2026-01-01"
}
```

Resolve response (uniform shape):

```json
{ "grade": "B", "days": 21, "effective_from": "2026-01-01" }
```

An unmapped/blank grade resolves to `{"grade": "B", "days": null, "effective_from": null}`.

Validation:

- `grade_start <= grade_end`.
- `days >= 1`.
- `effective_from` required.
- No other rule (regardless of `effective_from`) whose range overlaps this
  rule's range. Editing a rule excludes itself.
- Errors follow Unit 1 conventions: `{"detail": "..."}` for single errors,
  `{"field": ["..."]}` for validation.

## Implementation

Work in the following order; verify each backend step before frontend work begins.

### 1. Model, service, migration

- Add `GradeEntitlement` to `leave/models.py` with the check constraints and
  `save()` normalization; add `Meta.ordering`.
- Add `leave/services.py` with `resolve_grade_entitlement` and helpers.
- `uv run manage.py makemigrations leave` (initial `leave` migration) and
  `uv run manage.py migrate`.

### 2. Admin registration

- Register `GradeEntitlement` in `leave/admin.py`: `list_display`
  (grade range, days, effective from), `search_fields` (grade start/end),
  `list_filter` (effective from), ordering, and a `GradeEntitlementAdminForm`
  whose `clean()` applies the same overlap rule (surfaced as a field error).
  `has_delete_permission` returns `False` so the no-hard-delete rule cannot be
  bypassed through the admin.

### 3. Serializer

- `leave/serializers.py`: `GradeEntitlementSerializer` (ModelSerializer):
  - Normalizes grades; validates start <= end, days >= 1, and rejects a range
    overlapping any existing rule (excluding self on update).

### 4. Views

- `leave/views.py`: `GradeEntitlementViewSet` — list/create/retrieve/partial-update
  only (no delete, no PUT). Permission `IsHRRole` on top of the global
  `IsAuthenticated`. A `@action(detail=False, methods=["get"])` named `resolve`
  returns the resolution for `grade` (required) and optional `as_of` (valid
  `YYYY-MM-DD`); the default date is `timezone.localdate()`.

### 5. URLs

- New `leave/urls.py`: register a `SimpleRouter` for `entitlements`
  (`basename="entitlement"`). Include `leave.urls` in `config/urls.py`
  alongside the existing `users` include.

### 6. Seed

- Extend `seed_dev_users` to idempotently seed the three default rules with
  `effective_from = date.today()` (get-or-create by range + date; does not
  overwrite HR edits on re-run).

### 7. Frontend

- `lib/entitlements.ts`: authoritative TypeScript types (`Entitlement`,
  `EntitlementInput`, `EntitlementResolution`, `EntitlementListResponse`) and
  typed helpers `listEntitlements`, `getEntitlement`, `resolveEntitlement`
  (server-side reads via `lib/api-client.ts`).
- Route-handler proxies (mirror Unit 2 employees proxies):
  - `app/api/hr/entitlements/route.ts` — POST.
  - `app/api/hr/entitlements/[id]/route.ts` — PATCH.
- Components under `components/hr/`:
  - `entitlement-table.tsx` — presentational table (grade range, annual days,
    effective from, "Current" badge when already effective).
  - `entitlement-form.tsx` — client create/edit form posting to the proxies.
- Pages under `app/(dashboard)/dashboard/hr-admin/entitlements/`:
  - `page.tsx` — list with "New entitlement" action, a server-side resolve
    widget (`grade` search param renders the resolved rule), and the table.
  - `new/page.tsx` — create form.
  - `[id]/edit/page.tsx` — edit form.
- Add an "Entitlements" item to the HR section of the dashboard sidebar
  (`components/dashboard/dashboard-shell.tsx`) and an Entitlements card on the
  HR administration index page.
- Use the established token classes only; no new dependencies.

### 8. Tests

- Backend (`leave/tests.py`):
  - Service: default bands resolve correctly (A/C→21, D/G→24, H/U→30); unmapped
    and blank grades → `None`; resolution prefers the latest effective rule when
    overlapping rows pre-exist (resolver determinism, not a create path).
  - API: 401 unauthenticated on list/create/retrieve/update/resolve; 403 for
    non-HR roles; HR list/create/retrieve/PATCH; validation failures
    (missing fields, start > end, days 0, overlap on any effective date);
    resolve success/unmatched/missing-grade/invalid-`as_of`; `DELETE` → 405.
  - Seed: `seed_dev_users` run twice seeds exactly 3 entitlement rules and stays
    idempotent.
- Frontend: a vitest test rendering the entitlement table (rows, current badge,
  empty state, edit link).

### 9. Docs

- Add `context/specs/03-hr-grade-entitlement-spec.md` (this file).
- Update `context/progress-tracker.md`: Unit 3 complete entry; replace "Next Up".
- Update root `README.md` API endpoints table with the `/api/v1/entitlements/`
  endpoints and project-structure note (`leave` no longer a stub).
- `architecture.md` / `code-standards.md` / `ai-workflow-rules.md` are
  unaffected (no new app, no permanent architecture change). The no-overlap
  entitlement rule is recorded under Architecture Decisions in the progress
  tracker; the new seed behavior is documented here and in the tracker.

## Dependencies

- Units 1–2 (`users` JWT auth, `IsHRRole`, page handling, api-client,
  dashboard shell, seed command).
- No new Python packages, no new npm packages.

## Verification checklist

- [ ] `uv run manage.py makemigrations leave` produces an initial migration; `uv run manage.py migrate` applies cleanly on Postgres.
- [ ] Admin shows `GradeEntitlement` with search/filter columns, rejects an overlapping range as a field error, and offers no delete.
- [ ] `GET/POST /api/v1/entitlements/`, `GET/PATCH /api/v1/entitlements/{id}/` require JWT (401 without), allow HR (200/201), deny non-HR roles (403).
- [ ] `GET /api/v1/entitlements/resolve/?grade=B` returns 21; `H` returns 30; an unmapped grade returns `days: null`; missing `grade` returns 400.
- [ ] Create validates start <= end, days >= 1, required `effective_from`, and rejects a range that overlaps any existing rule regardless of effective date.
- [ ] Any new/edited rule whose range overlaps an existing rule (regardless of `effective_from`) is rejected; a non-overlapping range on any date is accepted, and editing a rule does not flag itself.
- [ ] Grades are normalized (trimmed/upper-cased) on write; matching is case-insensitive.
- [ ] Seed command creates the 3 default rules idempotently.
- [ ] Frontend: HR can list rules, create a rule, edit a rule, and resolve a grade; non-HR never sees the routes in nav (server still enforces 403).
- [ ] `uv run manage.py test` passes (existing auth + employee tests + new entitlement tests).
- [ ] `npm test` passes; `npm run lint` and `npm run build` pass.
- [ ] `context/progress-tracker.md` and `README.md` updated.