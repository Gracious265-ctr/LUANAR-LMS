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
| `backend/leave` | The core leave domain: employees, grade entitlements, financial years, applications, validation, submission, resubmission, cancellation, supporting documents, tracking, document storage. (Holidays were retired to `calendar_app`, but the shared `FinancialYear` still lives here.) |
| `backend/calendar_app` | **The institution-wide calendar**: `FinancialYear` (re-exposed), the single `WorkingDayPattern`, `Holiday` (recurring + observed-shift, optionally FY-scoped), and `CalendarEvent`. Resolution (recurring expansion, observed-shift) lives in `calendar_app/services.py`; leave day-counting and notice periods read it. |
| `backend/leave_types` | **The leave-type registry** — the one owner of `LeaveType` and every rule on it: branch/grade/gender eligibility, maximum duration, notice period, supporting-document requirement, plannability, institutional-registrar escalation, the deactivate/reactivate lifecycle, and the reserved annual-leave identity. Every other module reads these rules through `leave_types/services.py` |
| `backend/roles` | The **approver role registry**: `ApproverRole` and institution-wide (`RoleAssignment`) role holdings. |
| `backend/campuses` | **Campus scoping**: `Campus` and campus-wide (`CampusRoleAssignment`) role holdings. |
| `backend/teams` | **Teams and their role holdings**: `Team` (identification, lifecycle, the one chain it routes, campus/category scoping) and `TeamRoleAssignment` (team-wide role holders, including the designated team manager). **Team endpoints live here** (`TeamViewSet`, routes under `api/v1/teams/` via `teams.urls`). |
| `backend/roles` | Approver roles and team/campus role assignments split out of `organisation/` (`ApproverRole`, `RoleAssignment`, `TeamRoleAssignmentViewSet`, role permissions/services). |
| `backend/campuses` | Campus entities and campus role assignments split out of `organisation/` (`Campus`, `CampusRoleAssignment`, campus APIs). |
| `backend/org_structure` | The mirrored organisation tree (`OrgUnit`): the provider sync that creates/updates units and appoints `designated_approver` from role holders (formerly `org/`). |
| `backend/leave_types` | Leave type registry/configuration (formerly `leave_config/`). |
| `backend/approvals` | The **approval engine's data**: `ApplicationStage`, `ApplicationStageApprover`, `ApprovalDecision`, `Delegation`, `Reassignment`. (Split out of `chains`.) |
| `backend/chains` | Approval **chains**: `Workflow`, `Section`, `SectionMember`, `WorkflowMember` (formerly `workflows/`). Teams are **active on creation** (no activation action), and a chain carries its own required name with an `effective_from`/`effective_to` window defaulting to the current academic year. Team management endpoints were moved to `backend/teams`. |
| `backend/documents` | The official approved-leave **PDF** generator + template |
| `backend/notifications` | **In-app notifications** (`Notification` model, API under `/api/v1/notifications/`, wiring approvals/plans) + notification outbox + email sending (composers write rows, `tasks.py` sends them via django-q2) |
| `backend/audit` | The immutable **AuditEvent** trail + HR audit view |
| `backend/directory` | The **organisation data provider** seam: provider contract + dataclasses, the `ORG_DATA_BACKEND` factory, the placeholder fixture directory (employees, grades, org units, role holders) and the `sync_org_structure` command |
| 
### The standard layout inside one app
| 
Every Django app uses the same pattern. Learn it once, use it everywhere:
| 
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
| Seed the end-to-end test profiles (14 accounts on `@e2e.luanar`: HR, DVC, Registrar, Supervisor, HOD, Dean, Campus Registrar, 7 employees; two routable teams + campus + wide holdings) | `backend/users/management/commands/seed_test_profiles.py` |
| Retire/reactivate every published-password seed account (`@test.luanar`, `@e2e.luanar`) | `backend/users/management/commands/retire_demo_users.py` |
| Employee/HR data serialisers (employees, entitlements, financial years, applications) | `backend/leave/serializers/__init__.py` |
| The HR/employee API endpoints (entitlements, financial years, applications, documents) | `backend/leave/views/__init__.py` |
| Financial years, holidays, working-day pattern, or calendar events | `backend/calendar_app/models.py`, `backend/calendar_app/services.py`, `backend/calendar_app/serializers.py`, `backend/calendar_app/views.py` |
| How many working days a leave period has (excludes weekends/holidays from the configured pattern) | `backend/leave/validation/working_days.py` (`configured_weekdays`), `backend/calendar_app/services.py` (`get_holidays_for_range`/`working_weekdays`) |
| A leave type or any rule on it (name, eligibility, maximum duration, notice period, documents, plannability, registrar escalation) | `backend/leave_types/models.py`, `backend/leave_types/services.py`, `backend/leave_types/serializers.py`, `backend/leave_types/views.py` |
| Stopping or restoring a leave type (deactivate/reactivate, never delete) | `backend/leave_types/services.py` (`deactivate_leave_type`/`reactivate_leave_type`), `backend/leave_types/views.py` |
| Whether an employee may pick a leave type (branch/grade/gender eligibility) or how much notice it needs | `backend/leave_types/services.py` (`is_eligible`, `validate_notice`) |
| The annual leave type's rules (notice period, maximum duration, eligibility …) | `backend/leave_types/services.py` (`provision_annual_leave` provisions the row; its rules are edited through the ordinary leave-type endpoint) |
| Employee "my leave" overview and history endpoints | `backend/leave/views/my_leave.py`, `backend/leave/views/history.py` |
| The employee leave **dashboard** summary (balances + needs-attention + drafts + recent) | `backend/leave/services/dashboard.py`, `backend/leave/views/dashboard.py` |
| Resubmission endpoint after a correction | `backend/leave/views/resubmission.py` |
| Which fields are validated and how (grade ranges, dates, balance, overlap…) | `backend/leave/validation/pipeline.py` + `backend/leave/validation/validators/` |
| Logic of **submitting** an application | `backend/leave/services/submission.py` |
| Logic of **saving changes / resubmitting** an application | `backend/leave/services/resubmission.py` |
| Entitlement/rules resolution helpers (which grade get which days) | `backend/leave/services/__init__.py` |
| Per-type leave entitlement mapping (external grade + type + year → days) and `get_entitlement` | `backend/leave/models.py` (`GradeLeaveEntitlement`), `backend/leave/services/__init__.py` (`get_entitlement`) |
| The organisation data source (employees, grades, org units, role holders) and its contract | `backend/directory/provider.py`, `backend/directory/fixtures/seed_data.json`, `backend/directory/factory.py` (`ORG_DATA_BACKEND` in `backend/config/settings/base.py`) |
| Syncing the org tree / who a unit's designated approver is | `backend/org_structure/services.py`, command `backend/directory/management/commands/sync_org_structure.py` |
| Working-day / weekend / holiday calculation | `backend/leave/services/working_days.py` |
| Reference numbers (e.g. `LV-2026-27-…`) | `backend/leave/services/references.py` |
| Supporting-document lifecycle (upload/replace/delete rules) | `backend/leave/services/documents.py` |
| Default seed data (grade bands, leave types, rules, workflows) | `backend/leave/defaults.py` |
| Cancellation of approved leave | `backend/leave/cancellations/services.py` |
| History/tracking provider used by the app | `backend/leave/tracking/` |
| Where approved PDFs/documents are stored (local disk vs Supabase) | `backend/leave/storage/` |
| The approval workflow engine (stage resolution, routing) | `backend/chains/database_provider.py`, `backend/chains/services.py` |
| The **decision** rules (approve/reject/return, final approval) | `backend/chains/approval.py` |
| Who is allowed to see/decide what | `backend/chains/policies.py` |
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
| `frontend/app/(dashboard)/dashboard/hr-admin/calendar/…` | The HR **Calendar** app (tabbed landing page: financial years, holidays & events, working days, with a month grid) |
| `frontend/app/(auth)/login/` | The login page |
| `frontend/app/api/…` | Thin proxy route handlers, one per backend endpoint group (auth, leave, hr, approvals, plans, leave-config) |
| `frontend/components/…` | Reusable UI pieces, grouped by area (hr, leave-config, approvals, applications, cancellation, tracking, dashboard) |
| `frontend/lib/…` | Typed helpers for each domain — where API calls + TypeScript types live |
| `frontend/scripts/e2e.sh` | The end-to-end smoke test script (`npm run test:e2e`) |
| `frontend/tests/…` | Frontend tests (Vitest + Testing Library) |

### "I want to change…" → open this (frontend)

| I want to change… | Open this |
|-------------------|-----------|
| The app's outer layout / floating pill-shaped **sidebar** / top bar / hide button / **notification bell** | `frontend/components/dashboard/dashboard-shell.tsx` |
| The responsive **launcher and dashboard** header, notifications, All Apps link, desktop profile popover, mobile avatar account menu, and password dialog | `frontend/components/ui/navbar-1.tsx`, used by `frontend/components/launcher/launcher-shell.tsx` and `frontend/components/dashboard/dashboard-shell.tsx`; password form in `frontend/components/account/password-change-form.tsx` |
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
| The **Calendar** app (financial years, holidays & events, working-day pattern, month grid) | `frontend/app/(dashboard)/dashboard/hr-admin/calendar/…` + `frontend/components/hr/CalendarTabs.tsx`, `CalendarMonthGrid.tsx`, `HolidaysSection.tsx`, `EventsSection.tsx`, `WorkingDaysSection.tsx`, `frontend/lib/financial-years*.ts` and `frontend/lib/calendar-weekdays.ts` |
| The **Calendar** app's own sidebar rail (only the launcher + one Calendar entry; the HR folio is hidden inside the app) | `frontend/lib/nav/calendar-nav.ts` (`isCalendarModule`, `CALENDAR_NAV_ITEMS`) |
| Who may open the Calendar (the frontend access check) | `frontend/lib/financial-years.ts` (`canAccessCalendar`/`requireCalendarAccess`; backend twin in `backend/calendar_app/services.py`) |
| The **Leave Configuration** app (list/create/edit leave types, deactivate & reactivate) | `frontend/app/(dashboard)/leave-config/…` + `frontend/components/leave-config/`, `frontend/lib/leave-config*.ts` |
| Who may open Leave Configuration (the frontend access check) | `frontend/lib/leave-config-server.ts` (`canAccessLeaveConfig`; backend twin in `backend/leave_config/services.py`) |
| An API call's payload or types (e.g. entitlements) | `frontend/lib/entitlements.ts` (mirror in `app/api/hr/entitlements/route.ts` for how it is sent) |
| Shared API client / how tokens are attached | `frontend/lib/api-client.ts` |
| Shared utilities (`cn`, error messages, dates) | `frontend/lib/utils.ts` |
| **Search and filter** controls on a list screen | `frontend/components/ui/list-search.tsx`, `frontend/components/ui/filter-chips.tsx`, matching rule in `frontend/lib/search.ts` |
| The **progress rail** above a form split across pages | `frontend/components/ui/form-progress.tsx` (wraps `frontend/components/ui/Stepper.tsx`) |
| The team create/edit form (details → manager or approval steps) | `frontend/components/hr/team-form.tsx` |
| A team's **chain builder** (steps page → members page) | `frontend/components/hr/workflow-form.tsx` |
| The **chain cards** on a team's workflows page (badge, Edit, Make default) | `frontend/components/hr/workflow-compact-card.tsx` |
| The **multi-select employee picker** used to add a team's or a chain's members | `frontend/components/hr/employee-picker-dialog.tsx` |
| The Supporting/Approved **document tables** (shared by both pages) | `frontend/components/documents/documents-table.tsx` |

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

**I want to add search or a filter to a list screen.**
1. **Decide who filters.** If the page already loads the whole list, filter in
   the browser. If the backend endpoint takes a query parameter for it, keep it
   server-side so the filtering happens over the whole dataset, not one page.
2. **Local search:** render
   `frontend/components/ui/list-search.tsx` (`ListSearch` — controlled, labelled,
   with a clear action) and filter with `matchesSearch(query, [...values])` from
   `frontend/lib/search.ts`. Pass the values the row actually shows (name, code,
   reference, status label, formatted date) so the box finds what the eye sees.
3. **Local enum narrowing:** `frontend/components/ui/filter-chips.tsx`
   (`FilterChips`) for active/retired, account status, etc. Give each chip a
   label distinct from the row badge ("Active only", not "Active") or Testing
   Library will find two elements with the same text.
4. **Keep the empty state honest.** A table that takes an optional `empty` slot
   (`AdminUserTable`, `TeamTable`, `ApproverRoleTable`, `EntitlementTable`,
   `LeaveTypeTable`, `CampusTable`, `FinalizedLeaveTable`,
   `PendingApplicationsTable`, `ReassignmentTable`) should be handed
   "nothing matches this search" when a filter caused the emptiness, and
   `undefined` otherwise — an empty registry and a hidden row mean different
   things.
5. **Resolve overlays against the unfiltered list.** A section's `?user=<id>` /
   `?role=<id>` / `?entitlement=<id>` / `?team=<id>` lookup must read the full
   array it was given (`users.find(...)`, not `visible.find(...)`), or a filter
   turns a live deep link into a not-found.
6. **Server search:** add the parameter to the `lib/` helper (see
   `listFinalizedApplications({ employee })` in `frontend/lib/audit.ts` and
   `listDelegations(state, approver)` in `frontend/lib/delegations.ts`), then
   render a plain `method="get"` form with `Input` + `Button`. Carry every
   *other* active filter as `<input type="hidden">` (see the audit and
   delegations pages) so searching does not silently reset the tab or the
   history filters; build the "Clear" links from the same helper that builds the
   form's own URL.
7. Add a case to the existing suite for the screen, or a small one for a new
   shared component. `frontend/tests/list-controls.test.tsx` covers the two
   primitives.

**I want to split a form across pages or add a progress rail.**
1. Render `frontend/components/ui/form-progress.tsx` (`FormProgress`) at the
   top of every page, passing **all** stages in order and the id of the current
   one. It derives completed/current/pending from position, so a page never
   invents its own statuses.
2. Keep one `<form>` and one payload. The forward button is `type="button"`
   and only validates the page and moves it (`setPage(2)`) — it has no write
   path at all. The save button on the last page is also `type="button"` and
   calls the save function directly, running the same validation again (see
   `stepsProblem()` in `frontend/components/hr/workflow-form.tsx`). A page that
   can be returned to can be changed, so the check that opened the next page is
   not evidence about what will be written.
3. Make the form's native submit **inert**. A browser can submit the form while
   an earlier page is showing — Enter in a field or select, or autofill — even
   when that page has no submit button, and a `type="submit"` anywhere would let
   that write. The workflow form's `onSubmit` only calls `preventDefault()`;
   pages move through their own click handlers, and Enter in the page's text
   input advances explicitly. Ignore a click whose `event.detail > 1` on the
   save button. The stronger rule is layout: put the last page's write at the
   **far end** of its action row, with the harmless "Back" next to where the
   forward button was, so a repeat click cannot land on the write at all; key
   the two action rows so the focused forward button is unmounted instead of
   becoming a focused save. As a fallback for narrow screens that wrap the row,
   also record the forward click's point and time and ignore a save click that
   lands within ~32px of it, inside 1.5s, with the pointer never having moved.
   End that pending gesture on the first `pointermove` beyond ~8px, otherwise a
   deliberate click on a save button that happens to sit under the old spot
   would be swallowed.
4. Keep the forward button enabled and let the validation say what is missing.
   `stepsProblem()` returns the message **and the control that fixes it**, so
   the cursor lands on the field, button or select to change instead of an
   alert the viewer may be scrolled away from. Only disable an action that
   genuinely cannot do anything (e.g. "Add step" once every approver role
   already sits on a step).
5. Test the boundary, not just the final submit: assert the rail's
   `data-state` values, that the later page is absent before advancing, that
   the forward action calls no write API (`createWorkflow`/`updateWorkflow`) and
   that Enter and an implicit `submit` neither advance nor write, that a
   `detail: 2` click on save does not write while a `detail: 1` click does, that
   a `detail: 1` click at the forward button's point does not write either, that
   the leading action on the later page is the way back rather than the write,
   that a repeat click at the forward point is not a save, that moving the
   pointer lets the same click write, that
   "Back" keeps what was already entered, and that the write API is not called
   on page one.
6. Give the last page its own gate, and say it before the click. The workflow
   form will not write a chain with nobody on it (`membersProblem()`): the save
   button is disabled while the list is empty, a one-line reason sits above the
   actions, and `handleSave` repeats the rule so no stray click can bypass it.
   When a later page shows somebody who is *already placed elsewhere*, treat
   that as context, not as an action. One person serves one chain of a team at a
   time, so `workflow_member_pool` returns them under `assigned_elsewhere` with
   a `kind` (`"member"` or `"step"`) and the member page puts that list behind a
   **View … already on another chain** button instead of printing it beside the
   people who can join; the dialog shows what the pool already knows about each
   person, so it is inspectable without a write path and without linking to the
   employee directory, which a team's manager cannot read. The rule is enforced
   on the write side too: both `assign_workflow_member` and
   `sync_workflow_members` refuse an already-placed person (the sync reports it
   against `members`) instead of silently moving them off another chain. Wide
   approvers are the one exception: their holdings staff chains automatically,
   so they stay addable to several and their row carries
   `is_wide_approver`.
7. Add members several at a time. Both rosters open
   `frontend/components/hr/employee-picker-dialog.tsx`, which holds the
   selection, searches the already-loaded pool, and confirms with a count. The
   team roster sends the whole selection to `POST /teams/{id}/members/` as
   `users: [id, …]`; `add_team_members` validates and writes the batch in one
   transaction, so one refusal rolls the whole selection back. The chain page
   merges the selected ids into `members` and writes them with the workflow, so
   a chain add stays one save rather than one request per person.

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
1. The chain/resolution: `backend/chains/database_provider.py`.
2. Approve/reject/return and final approval: `backend/chains/approval.py`.
3. Visibility/permission rules: `backend/chains/policies.py`.
4. Delegation + reassignment: `backend/chains/services.py`.

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

**I want every capacity to sign in and walk the system end to end.**
```bash
uv run manage.py seed_test_profiles
```
Creates fourteen `@e2e.luanar` accounts (password `testpass123`) — HR, DVC,
Registrar, Supervisor, HOD, Dean, Campus Registrar and seven employees — two
routable teams (administration `Supervisor→HOD→Registrar→DVC`, academic
`Dean→Campus Registrar` at Main Campus), the wide holdings that staff their
unmanned steps, and baseline leave config. Run it **after** `seed_demo_data` if
both are used: an office has one holder, so it moves the Registrar holding to the
E2E account and re-points the chain step that named the previous holder.

The seed also designates `hod@e2e.luanar` as **manager** of Registry Operations,
so the team-manager path ships with a working fixture (sign in as that account to
walk it).

**I want to understand or change what a team manager may do.**
A team manager is an ordinary employee holding a *team-wide* approver role whose
`TeamRoleAssignment.is_team_manager` is set. One manager per team is a database
constraint; HR designates them on the team's **Approvers** tab (Make manager) or
at team creation (`manager={"role","user"}`). Authority is `is_hr_actor(actor) or
is_team_manager(actor, team)` (`backend/chains/services/_shared.py::_require_can_manage_team`).

| Surface | HR / superuser | Team manager |
|---------|----------------|--------------|
| Teams list | every team | only teams they manage (single team → redirect) |
| Team identity (category, campus, name) & retire | yes | **no** (403) |
| Team chains (create/edit/route a `Workflow`) | yes | yes, own team only |
| Workflow steps | staff from the whole directory | staff from the team's own members |
| Roster (add/remove members) | yes | yes, own team only |
| Approvers tab (wide holders, Make manager) | read + write | **read-only** |
| Approver roles (create/edit/retire) | yes | no (read-only active list) |

The manager path reads through **manager-scoped endpoints**, never by loosening an
HR-only one: `GET /api/v1/teams/{id}/member-candidates/` and
`GET /api/v1/teams/eligible-approver-roles/` (`backend/teams/views.py`).
Writes are scoped too: `SectionMemberWriteSerializer.validate_section` refuses a
manager staffing a step of a team they do not run, because a write names its
section directly and the viewset queryset alone would not stop it.

**I want the seeded demo accounts gone.**
```bash
uv run manage.py retire_demo_users
```
They are deactivated, not deleted: audit entries, decisions, delegations, role
assignments and balance transactions all point at `users.User` with `PROTECT`, so
a demo account with any history cannot be deleted. The command writes a
`DEACTIVATED` audit entry per account and is idempotent, and it covers both the
`@test.luanar` demo seed and the `@e2e.luanar` test profiles. `--undo` puts the
demo state back. Leave `seed_dev_users` in place regardless — it also seeds the
leave types, entitlements, rules and financial year.

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