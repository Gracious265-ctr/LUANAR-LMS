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
| `backend/leave` | The core leave domain: employees, grade entitlements, financial years, holidays, applications, validation, submission, resubmission, cancellation, supporting documents, tracking, document storage |
| `backend/leave_config` | **The leave-type registry** — the one owner of `LeaveType` and every rule on it: branch/grade/gender eligibility, maximum duration, notice period, supporting-document requirement, plannability, institutional-registrar escalation, the deactivate/reactivate lifecycle, and the reserved annual-leave identity. Every other module reads these rules through `leave_config/services.py` |
| `backend/organisation` | The **approver registry and org scoping**: `ApproverRole`, `Campus`, and the institution-wide (`RoleAssignment`) and campus-wide (`CampusRoleAssignment`) role holdings. (Split out of `workflows`; the `workflows.models` re-export shim keeps historical imports working.) |
| `backend/teams` | **Teams and their role holdings**: `Team` (identification, lifecycle, the one chain it routes, campus/category scoping) and `TeamRoleAssignment` (team-wide role holders, including the designated team manager). (Split out of `workflows`.) |
| `backend/approvals` | The **approval engine's data**: `ApplicationStage`, `ApplicationStageApprover`, `ApprovalDecision`, `Delegation`, `Reassignment`. (Split out of `workflows`.) |
| `backend/workflows` | Approval **chains**: `Workflow`, `Section`, `SectionMember`, `WorkflowMember`. Teams are **active on creation** (no activation action), and a chain carries its own required name with an `effective_from`/`effective_to` window defaulting to the current academic year |
| `backend/documents` | The official approved-leave **PDF** generator + template |
| `backend/notifications` | Notification outbox + email sending (composers write rows, `tasks.py` sends them via django-q2) |
| `backend/audit` | The immutable **AuditEvent** trail + HR audit view |
| `backend/directory` | The **organisation data provider** seam: provider contract + dataclasses, the `ORG_DATA_BACKEND` factory, the placeholder fixture directory (employees, grades, org units, role holders) and the `sync_org_structure` command |
| `backend/org` | The mirrored organisation tree (`OrgUnit`): the provider sync that creates/updates units and appoints `designated_approver` from role holders |

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
| The set-password link (request, resend, confirm) | `backend/users/services.py`, `backend/notifications/accounts.py`, `frontend/lib/password-set.ts` |
| Changing a password from a live session (and the session eviction) | `backend/users/services.py` (`change_password`), `backend/users/authentication.py` |
| Seed dev demo data (a routable team, its Supervisor→HOD→Registrar chain, approver + employee accounts, and baseline leave config) | `backend/users/management/commands/seed_demo_data.py` |
| Employee/HR data serialisers (employees, entitlements, financial years, holidays, applications) | `backend/leave/serializers/__init__.py` |
| The HR/employee API endpoints (entitlements, financial years, holidays, applications, documents) | `backend/leave/views/__init__.py` |
| A leave type or any rule on it (name, eligibility, maximum duration, notice period, documents, plannability, registrar escalation) | `backend/leave_config/models.py`, `backend/leave_config/services.py`, `backend/leave_config/serializers.py`, `backend/leave_config/views.py` |
| Stopping or restoring a leave type (deactivate/reactivate, never delete) | `backend/leave_config/services.py` (`deactivate_leave_type`/`reactivate_leave_type`), `backend/leave_config/views.py` |
| Whether an employee may pick a leave type (branch/grade/gender eligibility) or how much notice it needs | `backend/leave_config/services.py` (`is_eligible`, `validate_notice`) |
| The annual leave type's rules (notice period, maximum duration, eligibility …) | `backend/leave_config/services.py` (`provision_annual_leave` provisions the row; its rules are edited through the ordinary leave-type endpoint) |
| Employee "my leave" overview and history endpoints | `backend/leave/views/my_leave.py`, `backend/leave/views/history.py` |
| The employee leave **dashboard** summary (balances + needs-attention + drafts + recent) | `backend/leave/services/dashboard.py`, `backend/leave/views/dashboard.py` |
| Resubmission endpoint after a correction | `backend/leave/views/resubmission.py` |
| Which fields are validated and how (grade ranges, dates, balance, overlap…) | `backend/leave/validation/pipeline.py` + `backend/leave/validation/validators/` |
| Logic of **submitting** an application | `backend/leave/services/submission.py` |
| Logic of **saving changes / resubmitting** an application | `backend/leave/services/resubmission.py` |
| Entitlement/rules resolution helpers (which grade get which days) | `backend/leave/services/__init__.py` |
| Per-type leave entitlement mapping (external grade + type + year → days) and `get_entitlement` | `backend/leave/models.py` (`GradeLeaveEntitlement`), `backend/leave/services/__init__.py` (`get_entitlement`) |
| The organisation data source (employees, grades, org units, role holders) and its contract | `backend/directory/provider.py`, `backend/directory/fixtures/seed_data.json`, `backend/directory/factory.py` (`ORG_DATA_BACKEND` in `backend/config/settings/base.py`) |
| Syncing the org tree / who a unit's designated approver is | `backend/org/services.py`, command `backend/directory/management/commands/sync_org_structure.py` |
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
| When/what **emails and notifications** are sent | the composers in `backend/notifications/` (`services.py` decisions, `delegations.py`, `reassignments.py`, `plans.py`, `cancellations.py`) + the single send site `backend/notifications/tasks.py` |
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
| `frontend/app/(dashboard)/leave-config/…` | The HR **Leave Configuration** app (leave-type list, create, edit) |
| `frontend/app/(auth)/login/` | The login page |
| `frontend/app/api/…` | Thin proxy route handlers, one per backend endpoint group (auth, leave, hr, approvals, plans, leave-config) |
| `frontend/components/…` | Reusable UI pieces, grouped by area (hr, leave-config, approvals, applications, cancellation, tracking, dashboard) |
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
| Employee leave **dashboard** (landing page: balance rings, needs attention, drafts, recent) | `frontend/app/(dashboard)/dashboard/leave/page.tsx` + `frontend/components/leave/*Section.tsx`, `frontend/lib/hooks/useLeaveDashboard.ts` |
| Employee drafts list | `frontend/app/(dashboard)/dashboard/leave/drafts/` |
| One application's pages (details, review, tracking, history, edit) | `frontend/app/(dashboard)/dashboard/leave/[id]/…` |
| **Leave Plans** (plan ahead → reminder → apply) | `frontend/app/(dashboard)/dashboard/plans/…` + `frontend/components/plans/`, `frontend/lib/plans/`, `frontend/lib/hooks/usePlans.ts` and `useTeamPlans.ts`; backend `backend/plans/` |
| Scheduled plan reminders / missed-plan sweep | `backend/plans/tasks.py` (`check_and_notify_plans`) + `backend/plans/migrations/0002_schedule_plan_check.py` |
| Approvals list / approval detail for approvers | `frontend/app/(dashboard)/approvals/` + `frontend/components/approvals/` |
| HR admin home and all HR pages (employees, entitlements, workflows, calendar, delegations, reassignments, audit, document template) | `frontend/app/(dashboard)/dashboard/hr-admin/…` |
| The **Leave Configuration** app (list/create/edit leave types, deactivate & reactivate) | `frontend/app/(dashboard)/leave-config/…` + `frontend/components/leave-config/`, `frontend/lib/leave-config*.ts` |
| Who may open Leave Configuration (the frontend access check) | `frontend/lib/leave-config-server.ts` (`canAccessLeaveConfig`; backend twin in `backend/leave_config/services.py`) |
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
1. Pick the subject family, then edit its composer — each one owns its wording
   and its recipient matrix:
   - decisions: `backend/notifications/services.py` (`compose_subject`/`compose_body`)
   - delegation: `backend/notifications/delegations.py`
   - reassignment: `backend/notifications/reassignments.py`
   - leave plans: `backend/notifications/plans.py`
   - cancellations: `backend/notifications/cancellations.py`
2. **When** a notification fires comes from the event that emits on commit
   (`backend/workflows/events.py`, `backend/leave/cancellations/events.py`, or a
   plan service), not from the composer.
3. Every composer ends in `enqueue_delivery()`; `backend/notifications/tasks.py`
   is the only module that calls `send_mail`. Do not send anywhere else — the
   outbox row, the recipient override and the `failed` record all live there.
4. Add or update a test in `backend/notifications/tests_*.py`: a queue call leaves
   the row `pending`, and `deliver_notification(row.pk, recipients=[...])` is what
   actually sends.

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

**I want mail to actually go out (or not go out in dev).**
1. Transport comes from `backend/.env` (see `backend/.env.example`):
   `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`,
   `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `EMAIL_USE_SSL`,
   `DEFAULT_FROM_EMAIL`. With none of these set, `EMAIL_BACKEND` stays the
   console backend and nothing leaves the machine.
2. `DEFAULT_FROM_EMAIL` **must** be an address the SMTP account is authorised to
   send as (for Gmail, an alias on that account). With SMTP and no
   `DEFAULT_FROM_EMAIL`, every row records `failed` on purpose.
3. Run the worker, otherwise queued mail stays `pending` forever:
   ```bash
   uv run manage.py qcluster
   ```
   Or set `NOTIFICATIONS_SYNC_SEND=True` for a single-process dev server, which
   sends inline on commit.
4. `FRONTEND_URL` is the absolute base URL of the Next.js app. A set-password
   link is the one email a person has to click, so it is built from this; outside
   `DEBUG` a plain-HTTP value is refused rather than mailed, since it would put a
   live secret on an unencrypted link.
5. To smoke-test real SMTP against seeded (`@test.luanar`) addresses, set
   `EMAIL_DEV_RECIPIENT_OVERRIDE=<your inbox>` — it is honoured **only** when
   `DEBUG=True` and is refused (with an error log) otherwise. Leave it unset once
   real employees exist; the recipients are then real.
6. Scheduled Leave Plan jobs come from the `django_q.Schedule` row created by
   `backend/plans/migrations/0002_schedule_plan_check.py` — a daily
   (`Schedule.DAILY`) run of `plans.tasks.check_and_notify_plans`, which sends
   plan reminders, one follow-up, and marks missed plans. It also needs
   `qcluster` running, or the queued reminders stay `pending`.
7. Inspect results in Django admin → Notifications → Notification outbox
   (read-only: state, recipient, and the error text on failures).
8. **The sending address must not be one of the recipients.** A finalised
   application mails the owner *and* the approver who finalised. If the SMTP
   account is also one of those addresses, the relay accepts the message and the
   row records `sent`, but the copy to the sender lands in **Sent** rather than
   the Inbox — so the fan-out looks broken when it worked. The outbox row only
   ever records the owner (`notifications/services.py`); the wider recipient list
   travels inside the queued task, so a correct `sent` row is *not* evidence that
   every recipient received it. To verify multi-recipient delivery, use a sender
   distinct from both recipients.

**I want a new employee to be able to sign in.**
1. There is no password to hand out. HR adds the person on the Employees page and
   a set-password link is queued to their address automatically
   (`EmployeeSerializer.create` → `users.services.request_password_set`).
2. The person follows the link to `frontend/app/(auth)/set-password/page.tsx`,
   picks a password, and signs in. The link is single-use, expires after
   `PASSWORD_SET_TOKEN_LIFETIME_HOURS` (72 by default), and only the SHA-256 of
   the secret is stored (`users.PasswordSetToken`).
3. Lost mail: the employee's row has a **Send password link** action, or they can
   request one from `/forgot-password`. Issuing a new link invalidates the old
   one, so there is only ever one live link per account.
4. `POST /api/v1/auth/password-set/request/` answers the same thing whether or not
   the address has an account, on purpose — it must not be usable to find out who
   works here. Keep it that way when you edit it.

**I want to change what happens to a session when a password changes.**
1. This app issues a 24-hour refresh token and never rotates or blacklists it,
   and signing out only clears cookies. So the *only* thing that ends a session
   is the password itself: `CHECK_REVOKE_TOKEN` writes a fingerprint of the
   password hash into every token, and a token that no longer matches the
   account is rejected.
2. That covers the access path. It does **not** cover refresh —
   `TokenRefreshView` hands the raw token to `TokenRefreshSerializer`, which
   never looks at the user record — so `users/views.py::RefreshView` re-checks
   the same fingerprint through `users/authentication.assert_token_matches_password`.
3. If you change one, change both. A check that exists on only one of the two
   paths is a check that can be walked around, and the refresh path is the way
   around it.

**I want the seeded demo accounts gone.**
```bash
uv run manage.py retire_demo_users
```
They are deactivated, not deleted: audit entries, decisions, delegations, role
assignments and balance transactions all point at `users.User` with `PROTECT`, so
a demo account with any history cannot be deleted. The command writes a
`DEACTIVATED` audit entry per account and is idempotent. `--undo` puts the demo
state back. Leave `seed_dev_users` in place regardless — it also seeds the leave
types, entitlements, rules and financial year.

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