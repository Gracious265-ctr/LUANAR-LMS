# Developer Guide — Where to Edit Things

A simple map of the LUANAR Leave Management System (LMS) for anyone (especially
junior developers) who needs to find **which file to open** to change something.

> For setup and how to run the app, read `README.md` first.
> For the deep technical design, read `context/project-overview.md`,
> `context/architecture.md`, and `context/ui-context.md`.

---

## 1. What is this system?

A web app that lets university staff manage leave:

- **Employees** apply for leave (annual, maternity, paternity, compassionate…).
- A configured **chain of approvers** (e.g. HOD → Dean → Registrar → DVC)
  reviews and approves each request.
- When the **last** approver approves, the system:
  - prints an **official PDF** of the approved leave,
  - **deducts the days** from the employee's annual balance, and
  - **notifies** everyone involved, while **recording everything** in an
    auditable history trail.
- **HR** configures the rules: grade entitlement bands, leave types, leave
  rules, financial years, public holidays, approval workflows, and handles
  delegation/reassignment. HR can also cancel approved leave, view audit logs,
  and read the whole history of any application.

### Two parts that talk to each other

```
Browser
  │
  ▼
frontend/  (Next.js + React + TypeScript — the screens)
  │  pages call "lib" helpers
  ▼
frontend/app/api/...  (thin "proxy" route handlers)
  │  each one forwards to the backend API
  ▼
backend/  (Django + Django REST Framework — the engine)
  │  /api/v1/... endpoints
  ▼
PostgreSQL database   +   Supabase/disk storage for documents
```

- **backend/** — Django "engine". All the real rules live here.
- **frontend/** — Next.js "screens". Shows data and sends requests.

The Django API is the **source of truth**. The frontend never talks to the
database directly; it always goes through the Django API.

---

## 2. Backend map (Django)

### The Django apps and what each one owns

| App | What it owns |
|-----|--------------|
| `backend/users` | User accounts, roles/permissions, login (JWT tokens) |
| `backend/leave` | The core leave domain: employees, entitlements, leave types/rules, financial years, holidays, applications, validation, submission, resubmission, cancellation, supporting documents, tracking, document storage |
| `backend/workflows` | Approval workflows: stages, decisions, delegation, reassignment |
| `backend/documents` | The official approved-leave **PDF** generator + template |
| `backend/notifications` | Notification records + email sending (queued with django-q2) |
| `backend/audit` | The immutable **AuditEvent** trail + HR audit view |

### The standard layout inside one app

Every Django app uses the same pattern. Learn it once, use it everywhere:

| File / folder | What it's for |
|---------------|---------------|
| `models.py` | Defines the **database tables** (the data). |
| `migrations/` | History of table changes; run automatically. **Never edit by hand** — make with `makemigrations`. |
| `serializers/…` | "Translators" — turn request JSON into model data (and validate it), and model data back into JSON responses. |
| `views/…` | The **endpoints** (the API routes). Keep them thin; real logic goes in services. |
| `services/…` | The **real business rules**. If a rule exists, it is usually here, not in the view. |
| `urls.py` | Connects URLs (e.g. `/api/v1/entitlements/`) to the views. |
| `management/commands/` | `manage.py` commands (seeding sample data). |
| `tests/` or `tests_*.py` | Tests for that app. |

### "I want to change …" → open this (backend)

| I want to change… | Open this file |
|-------------------|---------------|
| Add/adjust the list of API routes and where they're mounted | `backend/config/urls.py` |
| Database/storage/providers settings, login settings, seed flags | `backend/config/settings/base.py` |
| What DB / storage / secrets the app runs with locally | `backend/.env` (local secrets, not committed changes) |
| Define or rename a data table (User, LeaveApplication, GradeEntitlement…) | App's `models.py`, then create a migration |
| Login flow, user model, roles, JWT | `backend/users/models.py`, `backend/users/views.py`, `backend/users/permissions.py` |
| Seed users + default HR config (grades, leave types, rules, financial year, workflows) | `backend/users/management/commands/seed_dev_users.py` |
| Employee/HR data serialisers (employees, entitlements, leave types, rules, financial years, holidays, applications) | `backend/leave/serializers/__init__.py` |
| The HR/employee API endpoints (entitlements, leave types/rules, financial years, holidays, applications, documents) | `backend/leave/views/__init__.py` |
| Employee "my leave" overview and history endpoints | `backend/leave/views/my_leave.py`, `backend/leave/views/history.py` |
| Resubmission endpoint after a correction | `backend/leave/views/resubmission.py` |
| Which fields are validated and how (grade ranges, dates, balance, overlap…) | `backend/leave/validation/pipeline.py` + `backend/leave/validation/validators/` |
| Logic of **submitting** an application | `backend/leave/services/submission.py` |
| Logic of **saving changes / resubmitting** an application | `backend/leave/services/resubmission.py` |
| Entitlement/rules resolution helpers (which grade get which days) | `backend/leave/services/__init__.py` |
| Working-day / weekend / holiday calculation | `backend/leave/services/working_days.py` |
| Reference numbers (e.g. `LV-2026-27-…`) | `backend/leave/services/references.py` |
| Supporting-document lifecycle (upload/replace/delete rules) | `backend/leave/services/documents.py` |
| Default seed data (grade bands, leave types, rules, workflows) | `backend/leave/defaults.py` |
| Cancellation of approved leave | `backend/leave/cancellations/services.py` |
| History/tracking provider used by the app | `backend/leave/tracking/` |
| Where approved PDFs/documents are stored (local disk vs Supabase) | `backend/leave/storage/` |
| The approval workflow engine (stage resolution, routing) | `backend/workflows/database_provider.py`, `backend/workflows/services.py` |
| The **decision** rules (approve/reject/return, final approval) | `backend/workflows/approval.py` |
| Who is allowed to see/decide what | `backend/workflows/policies.py` |
| The approved-leave **PDF** layout/content | `backend/documents/generator.py`, `backend/documents/models.py` (template) |
| What the PDF template looks like in the UI | `frontend` HR "Document Template" page (see frontend map) |
| When/what **emails and notifications** are sent | `backend/notifications/subscribers.py`, `backend/notifications/templates.py`, `backend/notifications/dispatcher.py` |
| The audit trail (what gets recorded) | `backend/audit/models.py`, `backend/audit/services.py`, `backend/audit/serializers.py` |
| A full demo scenario seed (authoritative smoke test) | `backend/leave/management/commands/seed_e2e.py` |

---

## 3. Frontend map (Next.js)

### The golden rule of the frontend

> A page never calls Django directly. The path is:
> **page → `lib/` helper → `app/api/…` proxy route → Django API.**

So to change something visible on screen you usually touch **two** files:
the `lib` helper (types + which endpoint) and the page/component (the look).

### Folder layout

| Folder | What it's for |
|--------|---------------|
| `frontend/app/(dashboard)/dashboard/…` | The pages you see inside the app (employee + HR) |
| `frontend/app/(dashboard)/approvals/…` | Approvers' "pending approvals" pages |
| `frontend/app/(auth)/login/` | The login page |
| `frontend/app/api/…` | Thin proxy route handlers, one per backend endpoint group (auth, leave, hr, approvals) |
| `frontend/components/…` | Reusable UI pieces, grouped by area (hr, approvals, applications, cancellation, tracking, dashboard) |
| `frontend/lib/…` | Typed helpers for each domain — where API calls + TypeScript types live |
| `frontend/scripts/e2e.sh` | The end-to-end smoke test script (`npm run test:e2e`) |
| `frontend/tests/…` | Frontend tests (Vitest + Testing Library) |

### "I want to change…" → open this (frontend)

| I want to change… | Open this |
|-------------------|-----------|
| The app's outer layout / **sidebar** / top bar / hide button | `frontend/components/dashboard/dashboard-shell.tsx` |
| Colors, fonts, global styles | `frontend/app/globals.css` (also see `context/ui-context.md`) |
| Login page | `frontend/app/(auth)/login/` |
| After-login access control (redirects by role) | `frontend/middleware.ts`, `frontend/lib/auth.ts` |
| Employee "new application" form | `frontend/app/(dashboard)/dashboard/leave/new/` and its form components |
| Employee drafts list | `frontend/app/(dashboard)/dashboard/leave/drafts/` |
| One application's pages (details, review, tracking, history, edit) | `frontend/app/(dashboard)/dashboard/leave/[id]/…` |
| Approvals list / approval detail for approvers | `frontend/app/(dashboard)/approvals/` + `frontend/components/approvals/` |
| HR admin home and all HR pages (employees, entitlements, leave rules, workflows, leave types, calendar, delegations, reassignments, audit, document template) | `frontend/app/(dashboard)/dashboard/hr-admin/…` |
| An API call's payload or types (e.g. entitlements) | `frontend/lib/entitlements.ts` (mirror in `app/api/hr/entitlements/route.ts` for how it is sent) |
| Shared API client / how tokens are attached | `frontend/lib/api-client.ts` |
| Shared utilities (`cn`, error messages, dates) | `frontend/lib/utils.ts` |

---

## 4. "How do I…" — quick recipes

**I want to add a field to the leave application (e.g. a new column).**
1. Add the field to `backend/leave/models.py` (`LeaveApplication`).
2. Run (in `backend/`): `uv run manage.py makemigrations leave` then `migrate`.
3. If it needs validation or appears in the API, add it to
   `backend/leave/serializers/__init__.py` (`LeaveApplicationSerializer`).
4. Frontend: update the matching type + call in `frontend/lib/…`, and the form
   component that posts the data.

**I want to change an API response's fields.**
1. Backend: edit the model → serializer (`backend/leave/serializers/…`).
2. Frontend: match the new shape in `frontend/lib/…` and wherever the page
   reads it.

**I want to add a whole new HR admin page.**
1. Backend: model (if new) → serializer → viewset in `backend/leave/views/…` →
   register the route in `backend/leave/urls.py`.
2. Frontend: proxy route in `frontend/app/api/hr/<name>/route.ts` → page folder
   `frontend/app/(dashboard)/dashboard/hr-admin/<name>/page.tsx` → a helper in
   `frontend/lib/`.
3. Add the sidebar link in `frontend/components/dashboard/dashboard-shell.tsx`.

**I want to add a new validation rule for leave applications.**
1. Put the rule in `backend/leave/validation/validators/`.
2. Wire it into the pipeline: `backend/leave/validation/pipeline.py` (or the
   submission service if it is flow-specific).
3. Add a test in `backend/leave/tests/`.

**I want to change the wording or recipients of an email.**
1. Wording lives in `backend/notifications/templates.py`.
2. When/what triggers a notification lives in
   `backend/notifications/subscribers.py`.
3. Sending is handled by `backend/notifications/dispatcher.py` + `tasks.py`
   (queued via django-q2 — in dev it may only create Notification rows).

**I want to edit the approved-leave PDF.**
1. The PDF builder is `backend/documents/generator.py`.
2. The stored template (what HR edits in the UI) is `LeaveDocumentTemplate`
   in `backend/documents/models.py`; the HR management page is under
   `dashboard/hr-admin/leave-document-template`.

**I want to change the approval decision logic or the approver chain.**
1. The chain/resolution: `backend/workflows/database_provider.py`.
2. Approve/reject/return and final approval: `backend/workflows/approval.py`.
3. Visibility/permission rules: `backend/workflows/policies.py`.
4. Delegation + reassignment: `backend/workflows/services.py`.

**I want to run the tests.**
- Backend (from `backend/`):
  ```bash
  DJANGO_SETTINGS_MODULE=config.settings.test uv run manage.py test leave --parallel 1
  ```
  If another session is using the default test DB, pick a unique one:
  ```bash
  TEST_DB_NAME=test_luanar_leave_mine DJANGO_SETTINGS_MODULE=config.settings.test uv run manage.py test --parallel 1
  ```
- Frontend (from `frontend/`): `npm test` (Vitest), `npm run lint` (ESLint).
- Full end-to-end smoke: `npm run test:e2e` (runs the canned leave scenario
  end to end against a dedicated test database).

---

## 5. Where to read more

| If you want… | Read this |
|--------------|-----------|
| How to install and run the project | `README.md` |
| What the product is and its features | `context/project-overview.md` |
| How the parts fit together (architecture) | `context/architecture.md` |
| The exact rules/validations in detail | `backend/docs/leave-validation.md`, `context/specs/` |
| Colors, spacing, and UI conventions | `context/ui-context.md` |
| Known bugs and their fixes | `context/troubleshooting-notes.md` |