# Unit 2 — HR Employee Directory

> **Superseded in part by Unit 27** (`context/specs/27-hr-managed-credentials.md`,
> 2026-10-01): the "unusable password" assumption below no longer holds. A
> directory-created employee now gets a real, HR-set password, and `POST
> /api/v1/employees/` requires one. Department is also now the `users.Department`
> model, not free text (Unit 20). Everything else in this spec still describes
> the directory.

## Goal

Create the HR employee-management experience: an HR-only API and frontend pages for listing (with search and sorting), viewing, creating, editing, and activating/deactivating employee records. For development/testing, HR is the authoritative source of employee records (build-plan §4, Unit 2).

## Assumptions made (flag if wrong)

These reflect decisions the source documents leave open. They are the implementation boundary of Unit 2 only; each is revisited by its owning unit.

- **Domain home:** the employee record lives in the `users` app because code-standards.md assigns "User and employee identity/domain logic" to `users/`. New `EmployeeProfile` model, 1:1 to the existing `users.User`.
- **Department/faculty, designation, grade:** stored as simple text/date fields on the profile in Unit 2. No `Grade`/`Department` lookup models yet — Unit 3 introduces the grade/entitlement model and Unit 6+ defines department grouping for workflows. Free-form text avoids inventing LUANAR master data that has not been documented.
- **Employee category:** a fixed choice set of `academic` and `administration`, matching the two workflow examples in project-overview.md. No additional categories until the workflow taxonomy is confirmed in Unit 6.
- **Activation/deactivation:** authoritative state is `User.is_active` (the login gate). The directory exposes `is_active`; toggling it updates the linked user. No duplicate active flag on the profile.
- **Identity/credentials:** creating an employee via the HR directory creates the linked `User` using the email as username with an **unusable password** (the employee cannot sign in until credentials are provisioned; production identity comes from LUANAR SSO). If the email already belongs to a user, the record is linked to that user instead of failing.
- **No hard-delete:** deactivation is the deactivation path. A destructive `DELETE` is not exposed because employee records must remain for audit/history (code-standards.md "File deletion must not silently destroy required audit or historical records"; same principle for records).
- **API namespace:** employee directory endpoints live at `/api/v1/employees/`, matching the shared contract hint in build-plan §8 (`GET /api/v1/employees/me/` arrives with the employee-facing units). HR-only permission for Unit 2.
- **Search/filter:** DRF built-in `SearchFilter` (substring across name/email/designation/department/grade) and `OrderingFilter`, under the existing global pagination. No new dependencies.
- **Seed dev users:** `seed_dev_users` additionally creates a matching `EmployeeProfile` for each seeded user so the directory starts populated for development/testing.

## Design

### Backend data model (`users` app)

```python
class EmployeeProfile(models.Model):
    class Category(models.TextChoices):
        ACADEMIC = "academic", "Academic"
        ADMINISTRATION = "administration", "Administration"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="employee_profile",
    )
    designation = models.CharField(max_length=200, blank=True)
    department = models.CharField(max_length=200, blank=True)
    category = models.CharField(
        max_length=20, choices=Category.choices, default=Category.ACADEMIC
    )
    grade = models.CharField(max_length=20, blank=True)
    appointment_date = models.DateField(null=True, blank=True)
```

- Active/inactive status is read from and written to the linked `User.is_active`.
- Full name/email are read from and written to the linked `User`.

### API contract

All endpoints require a valid JWT and the `hr` role.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/employees/` | List employee profiles (paginated, `search=`, `ordering=`) |
| POST | `/api/v1/employees/` | Create employee record (and linked user if email is new) |
| GET | `/api/v1/employees/{id}/` | Retrieve one employee profile |
| PATCH | `/api/v1/employees/{id}/` | Partially update the employee profile |

Response object (snake_case, DRF conventions):

```json
{
  "id": 1,
  "user_id": 7,
  "email": "hod@test.luanar",
  "full_name": "Test HOD",
  "role": "hod",
  "designation": "Senior Lecturer",
  "department": "Bunda Campus",
  "category": "academic",
  "grade": "D",
  "appointment_date": "2015-04-01",
  "is_active": true
}
```

- Create requires `email`, `first_name`, `last_name`; other profile fields optional.
- `role` is writable on create and update. Allowed values: `employee`, `supervisor`, `hod`, `dean`, `registrar`, `dvc`, `hr`. It defaults to `employee` when omitted or blank. HR assigns the role at create/update time, and role changes are audited with before/after values.
- Update accepts `first_name`, `last_name`, `email` (renames the linked user), `role`, and profile fields; `is_active` toggles activation.
- Errors follow Unit 1 conventions: `{"detail": "..."}` for single errors, `{"field": ["..."]}` for validation.

## Implementation

Work in the following order; verify each backend step before frontend work begins.

### 1. Migration

- Add `EmployeeProfile` to `users/models.py`; include `active` as *not* a field (delegated to `User.is_active`).
- Create `users/migrations/0002_employeeprofile.py` via `uv run manage.py makemigrations users`.
- `uv run manage.py migrate`.
- Update `seed_dev_users` to upsert an `EmployeeProfile` for every seeded user (assign a dev designation/department/category/grade so the directory is populated and testable).

### 2. Admin registration

- Register `EmployeeProfile` in `users/admin.py` with `list_display` (user, designation, department, category, grade, active), `search_fields` (user name/email, designation, department), `list_filter` (category, department, active via user).

### 3. Permissions

- New `users/permissions.py` with `IsHRRole` — allows a request only when the authenticated user's role is `hr`. Used alongside the global `IsAuthenticated` default.

### 4. Serializers

- Extend `users/serializers.py` with `EmployeeSerializer`:
  - Read-only: `id`, `user_id`, `email`, `full_name`, `is_active` (derived from the linked user).
  - Writable: `email`, `first_name`, `last_name`, `role`, `designation`, `department`, `category`, `grade`, `appointment_date`, `is_active`.
  - `create`: find-or-create the linked `User` by email (set unusable password when created), assign the submitted role or default to `employee`, then create the profile.
  - `update`: apply name/email/role/active changes to the linked user.

### 5. Views

- `users/views.py`: `EmployeeViewSet` — list/create/retrieve/partial-update only (no `delete`, no `put`). `get_queryset` prefetches/selects the linked user (the "employee") to avoid N+1. Permission: `IsHRRole`. Filter backend: `SearchFilter` + `OrderingFilter`; `search_fields` covers name, email, designation, department, grade.

### 6. URLs

- `users/urls.py`: register a DRF `DefaultRouter` (or `SimpleRouter`) for `employees` with `basename="employee"` under the existing `/api/v1/` include. Keep the existing auth routes untouched.

### 7. Frontend pages

- `lib/employees.ts`: one authoritative set of TypeScript interfaces (`Employee`, `EmployeeInput`) and typed helpers (`listEmployees`, `getEmployee`, `createEmployee`, `updateEmployee`) built on the existing `lib/api-client.ts`.
- `lib/api-client.ts`: add `PATCH` support if not already usable by `apiClient` (it forwards options, so only a convenience/typed wrapper is needed).
- Pages under `app/(dashboard)/dashboard/`:
  - `hr-admin/page.tsx` — HR administration index linking to Employees.
  - `hr-admin/employees/page.tsx` — server-component list with search input (client form) and a results table showing name, email, department, designation, category, grade, status; row links to the profile.
  - `hr-admin/employees/new/page.tsx` — create-employee form.
  - `hr-admin/employees/[id]/page.tsx` — profile view + inline edit form + activation toggle.
- Add an "Employees" item to the HR section of the dashboard sidebar (`components/dashboard/dashboard-shell.tsx`).
- Use the established token classes only; no new dependencies.

### 8. Tests

- Backend (`users/tests.py`): extend with an `EmployeeEndpointTests` class covering:
  - 401 unauthenticated on list/create/retrieve/update.
  - 403 for non-HR roles.
  - HR list returns seeded profiles; create returns 201 and links/creates the user; retrieve; PATCH updates name/email/profile/`is_active`; `search` and `ordering` behave.
  - Validation failure (missing email on create → 400).
- Frontend: a vitest test rendering the employees list with a mocked data fetch, asserting rows render and inactive state is shown.

### 9. Docs

- Update `context/progress-tracker.md`: Unit 2 complete entry under Completed; remove/replace "Next Up".
- Update root `README.md` API endpoints table to include the `/api/v1/employees/` endpoints.
- `architecture.md` / `code-standards.md` / `ai-workflow-rules.md` are unaffected (no new app, no permanent architecture change). If the implementation surfaces a real conflict, stop and record it before proceeding.

## Dependencies

- Unit 1 only (users app, JWT auth, DRF, pagination, seed command, api-client, dashboard shell).
- No new Python packages, no new npm packages.

## Verification checklist

- [ ] `uv run manage.py makemigrations users` produces one migration; `uv run manage.py migrate` applies cleanly.
- [ ] Seed command populates `EmployeeProfile` for all 7 seeded users, idempotently.
- [ ] Admin shows `EmployeeProfile` with search/filter columns.
- [ ] `GET/POST /api/v1/employees/` and `GET/PATCH /api/v1/employees/{id}/` require JWT (401 without), allow HR (200/201), deny non-HR roles (403).
- [ ] Create with a new email creates a user (unusable password) + profile; create with an existing email links the existing user.
- [ ] PATCH `is_active` deactivates/activates the linked user's login.
- [ ] `search` and `ordering` query params filter/sort the list; pagination shape is DRF's default.
- [ ] Frontend: HR can list, search, create, view, edit, and toggle an employee; non-HR never sees the routes in nav (server still enforces 403).
- [ ] `uv run manage.py test` passes (existing auth tests + new employee tests).
- [ ] `npm test` passes (existing dashboard-shell test + new employee list test).
- [ ] `npm run lint` and `npm run build` pass.
- [ ] `context/progress-tracker.md` and `README.md` updated.