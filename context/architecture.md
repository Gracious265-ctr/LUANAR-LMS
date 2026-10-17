
````markdown
# Architecture — LUANAR Leave Management System

## 1. Architecture Overview

The LUANAR Leave Management System is a web-based application that separates the user interface, application/business logic, authentication, and data persistence into clear layers. The frontend is responsible for presenting the system and collecting user input, while the Django backend owns business rules, workflow processing, authorization, and database access. File storage is intentionally left undefined until the organization’s existing storage infrastructure is investigated so that development and testing can use an architecture compatible with the eventual LUANAR environment.

The system should be designed so that organization-specific infrastructure can be introduced later without requiring major changes to the core leave-management logic.

---

## 2. Technology Stack

| Layer | Technology | Role |
|---|---|---|
| Frontend | Next.js | Web application, routing, pages, forms, and user-facing interactions |
| UI Components | 21st.Dev | Reusable interface components and consistent UI patterns |
| Styling | Tailwind CSS | Frontend styling and responsive layouts |
| Backend | Django | Core application logic, business rules, workflow processing, and server-side operations |
| API | Django REST Framework | Provides API endpoints consumed by the Next.js frontend |
| Database | PostgreSQL | Stores structured application data, users, leave applications, workflows, approvals, configuration, and audit records; also backs the background-job queue (Django-Q2 ORM broker), so no separate broker service is required |
| Authentication | Django authentication / LUANAR institutional authentication* | Authenticates users and establishes their system identity |
| File Storage | supabase | Stores supporting documents and generated approved leave documents; organization infrastructure must be investigated before final selection |
| Cache | Django local-memory cache (dev) | Temporary caching and performance-related data if required; production cache technology remains TBD (no Redis dependency introduced for this) |
| Background Processing | Django-Q2 (ORM broker) | Handles operations that should not block normal web requests, such as document generation or email processing; uses Postgres as the broker, no Redis dependency |
| Email | SMTP (Google Workspace relay), env-configured | Sends decision, delegation, reassignment, leave-day-plan, cancellation, set-password, and password-change notifications; the console backend is the fallback when no relay is configured |

\* Final technologies that depend on LUANAR's existing infrastructure must be confirmed before production deployment.

---

## 3. System Structure

The project should maintain a clear separation between frontend presentation and backend application responsibilities.

A high-level structure is:

```text
luanar-leave-system/
├── frontend/
│   ├── app/
│   ├── components/
│   ├── lib/
│   └── ...
│
├── backend/
│   ├── config/
│   ├── users/
│   ├── leave/
│   ├── workflows/
│   ├── notifications/
│   ├── documents/
│   ├── audit/
│   └── ...
│
├── storage/
│   └── TBD
│
└── docs/
    └── ...
````

The exact Django app names may change during implementation, but the responsibility boundaries must remain clear.

---

## 4. System Boundaries

### 4.1 Frontend — `/frontend`

The frontend owns the presentation layer and user interaction.

Responsibilities:

* Display dashboards and application information.
* Provide leave application forms.
* Display employee leave balances.
* Display application status and workflow progress.
* Display approval interfaces for authorized approvers.
* Display HR administration interfaces.
* Perform basic client-side validation for user experience.
* Send requests to the Django API.
* Display API validation and business-rule errors.
* Handle authenticated user sessions from the perspective of the UI.

The frontend must **not** own authoritative business rules.

For example, the frontend may display that an annual leave application requires available balance, but the backend must perform the authoritative balance validation.

The frontend must not:

* Decide whether an application can be approved.
* Calculate authoritative leave balances.
* Decide which user is an approver.
* Assign workflow stages.
* Modify database records directly.
* Bypass backend authorization.

---

### 4.2 Backend — `/backend`

The Django backend owns the application's authoritative behavior.

Responsibilities:

* Authentication and user identity handling.
* Authorization and role enforcement.
* Employee records.
* Leave applications.
* Leave-type configuration.
* Leave entitlement rules.
* Leave balance calculations.
* Working-day calculations.
* Public-holiday validation.
* Financial-year rules.
* Application overlap validation.
* Approval workflows.
* Approval decisions.
* Rejection and correction handling.
* Resubmission processing.
* Cancellation processing.
* Delegation and reassignment.
* Notification triggering.
* Document generation coordination.
* Audit logging.
* Database access.
* API validation.

All authoritative business decisions must originate from the backend.

---

### 4.3 File Storage — `/storage`

File storage is intentionally **TBD**.

The system will eventually need storage for:

* Supporting documents uploaded with leave applications.
* Generated approved leave documents.
* Potential document versions/history where required.

The storage technology and infrastructure must not be assumed until LUANAR's existing storage environment is investigated.

The final implementation should isolate file-storage operations behind a dedicated service or abstraction so that the underlying storage mechanism can be changed without changing leave-application logic.

---

### 4.4 Cache

Caching is not currently assigned a specific technology.

If caching is required, it must contain temporary or reproducible information rather than authoritative business records.

The database remains the source of truth for leave applications, balances, approvals, workflow configuration, and audit history.

---

## 5. Storage Model

The system separates persistent structured data, files, and temporary cached information.

### 5.1 Database

The database stores structured and authoritative system information.

Examples:

| Data                                    | Storage  |
| --------------------------------------- | -------- |
| Employee records                        | Database |
| Employee roles                          | Database |
| Employee team membership                | Database |
| Team membership roster (who routes a team) | Database |
| Normal workflow memberships (team member on a chain) | Database |
| Employee grades                         | Database |
| Grade entitlement configuration         | Database |
| Approver-role definitions (HR-managed)  | Database |
| Campuses                                | Database |
| Teams (academic / administration; campus-scoped when academic) | Database |
| Team-wide role assignments              | Database |
| Campus-wide role assignments            | Database |
| Institution-wide role assignments       | Database |
| Section approvers (one per step, effective-dated) | Database |
| Leave applications                      | Database |
| Leave types                             | Database |
| Leave-type rules                        | Database |
| Leave dates                             | Database |
| Calculated application days             | Database |
| Leave balances/history                  | Database |
| Workflow definitions                    | Database |
| Workflow stages                         | Database |
| Stage approver-role references          | Database |
| Assigned approvers                      | Database |
| Approval decisions                      | Database |
| Approval comments                       | Database |
| Rejection reasons                       | Database |
| Correction requests                     | Database |
| Delegations                             | Database |
| Reassignments                           | Database |
| Cancellation requests/decisions         | Database |
| Financial-year configuration            | Database |
| Public-holiday references/configuration | Database |
| Notification records/status             | Database |
| Audit records                           | Database |
| Document metadata                       | Database |

The database must remain the authoritative source for system state.

---

### 5.2 File Storage

The eventual file-storage system will contain binary documents rather than application state.

Examples:

* Supporting documents.
* Approved leave PDFs.
* Other generated document formats.
* Document versions where required.

The database should store metadata and references to files rather than unnecessarily storing large binary files inside ordinary application records.

The exact storage implementation is **TBD pending LUANAR infrastructure investigation**.

---

### 5.3 Cache

Cache is reserved for temporary, performance-oriented information.

Possible examples include:

* Frequently accessed configuration.
* Short-lived session-related information.
* Temporary computation results.
* Rate-limiting data.
* Temporary background-job state.

Cached data must be safe to recreate from authoritative sources.

A cache failure must not cause permanent loss of leave applications, approval decisions, balances, or audit history.

---

## 6. Authentication and Access Model

### 6.1 Authentication

The system is intended to use existing LUANAR institutional accounts.

The exact institutional identity provider and integration mechanism are **TBD** and must be confirmed with LUANAR IT.

The architecture should therefore separate:

```text
Institutional Identity
        ↓
Authentication
        ↓
Application User
        ↓
System Role
        ↓
Permissions
```

This allows the application's internal authorization model to remain stable even if the institutional authentication mechanism changes.

Until that integration is confirmed, the product issues its own password accounts. A superuser creates `hr` accounts in the Django admin; HR creates every other account from the employee directory and sets that person's initial password, and alerts nobody by email. `User.username` mirrors `User.email`, and `POST /api/v1/auth/login/` authenticates `email` + `password`. There is no self-service password change: only HR (or an administrator) sets a password. A directory-created employee is therefore a normal `employee`, and a password shorter than eight characters is refused. The full decision record is `context/specs/27-hr-managed-credentials.md`.

---

### 6.2 User Ownership

Each leave application belongs to the employee who submitted it.

The employee's identity must be determined by the authenticated backend user rather than supplied as trusted information by the frontend.

For example:

```text
Authenticated User
        ↓
Employee Record
        ↓
Leave Application
        ↓
Application Owner
```

An employee must not be able to submit an application on behalf of another employee by changing an employee ID in a frontend request.

---

### 6.3 Role-Based Access

Access is controlled by two separate things, and conflating them was the defect this model replaces.

**1. System role** — what an account may reach. Exactly three values, and nothing else:

* `employee` — own applications and personal leave information
* `approver` — the approver queue, review, delegation, and cover surfaces
* `hr` — organization-wide administrative/configuration access according to HR permissions

`User.role` is a reachability label. It is **not** a place in an approval chain, and a person's authority to approve a given application is never derived from it. An administrator grants `hr`; the employee directory cannot grant or revoke any role, and it always creates a normal `employee`. Approver standing comes from a workflow appointment (a team/section membership or an institution-wide `RoleAssignment`), never from editing the account.

**2. Approver role** — a position in an approval chain, maintained by HR as configuration (`ApproverRole`: `code`, `label`, `description`, `history_scope`, `is_institution_wide`, `handles_cancellation`). Approver roles are open-ended: HR defines the codes. No role is privileged in code.

An approver role is held in one of four places, and a stage's role resolves through
them in a fixed order — the nearest scope wins:

| Holding                | Model                          | Scope                                                        |
| ---------------------- | ------------------------------ | ------------------------------------------------------------ |
| Section appointee      | `Section.approver`             | The one person HR put on this step, effective-dated          |
| Team-wide grant        | `TeamRoleAssignment`           | One holder per role per team                                 |
| Campus-wide grant      | `CampusRoleAssignment`         | One holder per role per campus                               |
| Institution-wide grant | `RoleAssignment`               | One holder for a role marked `is_institution_wide`           |

A `Team` is either **academic** — it sits at a `Campus`, and its stages may resolve to a
campus-wide holder — or **administration** — institution-wide, and the only kind of team
an institution-wide approver may serve. `EmployeeProfile.team` places an employee on a
team, so routing is per-employee rather than per-category guesswork. `Team.workflow` is
the routing pointer (a team routes exactly one chain); `Workflow.team` is ownership (a
team may own several chains and switch which one it routes).

Access principles:

| Principal                                  | Access Principle                                                                 |
| ------------------------------------------ | -------------------------------------------------------------------------------- |
| Employee                                   | Own applications and personal leave information                                  |
| Holder of an approver role                 | Only the applications whose current stage names a role they hold, at any scope    |
| Institution-wide holder                     | Decides for any applicant whose stage reaches that role, whose team has no nearer holder, and whose team is an administration team |
| Holder of a role marked `handles_cancellation` | Decides cancellation requests, not only stage approvals                      |
| HR                                         | Organization-wide administrative/configuration access                            |

**Resolution is the backend's, per applicant, at submission time**
(`workflows.providers.resolve_section_approvers`): the section's own appointee wins;
failing that the team-wide holder; failing that the campus-wide holder; failing that an
institution-wide holder — and only when the routing team is an administration team (a
`team=None` lookup may still reach it, since institution-wide roles have no team).
Otherwise the configuration is incomplete and the submission is refused with an error
that names the role and what HR must do. The same answer is exposed as display data
(`section_resolution`) and never raises, so a screen can show who would act here
without the lookup failing first.

A person is an approver when they hold at least one **active** approver role (`is_approver_user`). Retiring a role therefore retires the approver status it conferred, which is why roles are retired rather than deleted.

**The frontend must ask, not infer.** The surfaces that need to know (`/approvals`, `/dashboard/approvals`, `/dashboard/cover`, the sidebar, the dashboard's pending count) read the backend's `GET /api/v1/approvals/capabilities/`, and fail closed when it cannot be read. The frontend may hide unavailable actions for usability, but hiding a UI element is **not** an authorization mechanism.

The backend must independently verify every protected operation.

---

## 7. Leave and Workflow Processing

The backend owns the leave-management state machine.

A simplified application lifecycle is:

```text
Draft
  ↓
Submitted
  ↓
Pending Approver
  ↓
Approve ─────────→ Next Stage
  │
  ├── Reject ────→ Rejected
  │
  └── Correction → Correction Required
                         ↓
                    Employee Resubmits
                         ↓
                    Same Approver
```

After the final configured approval:

```text
Final Approval
      ↓
Approved
      ↓
Balance Updated
      ↓
Approved Document Generated
      ↓
Notifications Sent
```

The actual approval stages are determined by the employee's configured workflow.

The workflow must not be hard-coded around a single sequence such as:

```text
Supervisor → HOD → Registrar → DVC
```

Different employee categories may use different configured workflows.

The team is the unit of organization; the `Department` concept is removed. Eligibility to approve is a fact about appointment, not location: a step's approver is its section appointee, or a holder of the step's role at team, campus, or (administration teams only) institution scope. Each workflow section has exactly one appointee (`Section.approver`); replacements are effective-dated handovers that keep the closed periods as history, so "who could act on a given day" stays answerable after a handover.

A stage names an approver role by `code`, resolved at submission time against the `ApproverRole` registry — not against a list in code. Consequences that the implementation must honour:

* A role code this build has never seen is legitimate; it is a row HR added, and it must round-trip untouched.
* A stage carries an `approver_role_label` snapshot so a decision, an application stage record, and a cancellation record still read correctly after a role is renamed or retired.
* A retired role cannot be activated into a workflow, and an application already inside a chain continues on the role it was routed to.
* When a stage's role has no resolver for a given applicant, the submission is refused (`workflow_unavailable`, 422) rather than routed to a fallback. See §12.7 and §6.3.

---

## 8. Background Processing

The system may require background processing for operations that are slow or should not block an HTTP request.

Potential background operations include:

* Sending email notifications.
* Generating approved leave documents.
* Processing uploaded supporting documents.
* Synchronizing public-holiday information.
* Other integrations introduced during implementation.

The background-processing technology is **Django-Q2**, using Postgres as its ORM-based broker (no Redis dependency).

Background jobs must not become the authoritative source of business state. Important state transitions must be persisted in the database.

For example, an approval must be recorded as an approval in the database before notification delivery is treated as a secondary operation.

Notification delivery implements that rule literally: a composer writes an
append-only `NotificationOutbox` row, `transaction.on_commit` hands the row to
Django-Q2, and the delivery task is the only place that calls `send_mail`. The row
is the delivery record (`pending → sent | failed`, with the error text on failure),
so a dead relay can never undo a decision, and a replayed event can never send the
same mail twice (one row per subject, kind and role). Scheduled work — plan
housekeeping and block-confirmation reminders — is a `django_q.Schedule` row, so it
also requires a running `qcluster` worker.

---

## 9. AI Model

The LUANAR Leave Management System does **not currently require an AI model** for its core functionality.

Leave approval decisions, balance calculations, eligibility checks, workflow routing, and authorization must be deterministic system operations.

AI should not be introduced into core decision-making unless a future requirement explicitly justifies it.

---

## 10. Configuration Model

Rules that may change over time should be represented as configurable data rather than hard-coded application logic where practical.

Examples include:

* Annual leave entitlement by grade range.
* Leave types.
* Maximum leave duration.
* Eligibility rules.
* Minimum notice periods.
* Supporting-document requirements.
* Approval workflows.
* Financial-year dates.
* Public-holiday configuration.
* Future-effective configuration changes.

Configuration changes must have an effective date where historical behavior could otherwise be affected.

One configuration row is owned rather than curated: annual leave and its starting rule
are created on demand when HR saves a grade entitlement, rather than seeded or entered
by hand in Leave Types. The annual leave type is therefore read-only there and its rule
is edited under Leave Rules. See
`context/specs/31-entitlement-linked-leave-type-availability-spec.md`.

---

## 11. Historical Integrity

Once a leave application is submitted, the system must preserve the rules and workflow context that applied to that application.

A later configuration change must not silently rewrite historical applications.

For example:

```text
Workflow A
    ↓
Application submitted
    ↓
Application retains Workflow A
    ↓
HR activates Workflow B
    ↓
New applications use Workflow B
```

Existing applications continue using their assigned workflow unless an explicit administrative reassignment operation occurs.

The same principle applies to leave-type rules and other configuration that affects an application's processing.

---

# 12. Invariants

The following rules must never be violated by the codebase.

### 12.1 Backend Authority

**All authoritative business rules must be enforced by the backend.**

The frontend must never be trusted to determine:

* Leave eligibility.
* Available balance.
* Approval permissions.
* Workflow routing.
* Application ownership.
* Final application state.

---

### 12.2 Application Ownership

**An employee can only create, view, modify, or cancel their own applications unless an explicitly authorized administrative or approval role permits the operation.**

The employee identity must come from the authenticated backend identity, not from an untrusted employee identifier supplied by the client.

---

### 12.3 Sequential Workflow

**A leave application must never skip a mandatory configured approval stage, and an approver must never approve their own leave — so the two rules resolve the applicant's own stage by skipping forward, and only ever that stage.**

An application can move to the next stage only after the current stage has completed its required action. A workflow is an ordered list of **sections**; each section is a step that runs in exactly that order, and advancement is always to the next stage that was not skipped. A stage is one of: not reached yet (`waiting`), open (`pending`), decided, or `skipped`.

A step is resolved to **one named person**, so the question "who can act at this step" has one answer and the decision record has one author. A person can never sit in judgment of their own leave. Where the applicant holds a stage — as its sole approver — that stage, and every stage below it, is **skipped** rather than refused or routed to a stand-in:

- a stage the applicant is the approver of is skipped because an approver cannot approve their own application;
- a stage below the applicant's is skipped because they outrank it;
- both are materialised as `skipped` with the reason recorded, so the approval history shows a considered step rather than a quietly dropped one. A skipped stage is terminal, resolves nobody, never appears in an approver's queue, and never raises a notification.

Advancement therefore continues at the first stage above the applicant's own. If the applicant holds the **last** stage there is nowhere to continue to, so the application is handed to **Human Resources**: one further stage with `section_ref = NULL`, `role = "hr"`, `history_scope = "all"`, and every active HR user — other than the applicant — in `eligible_approvers`. HR's authority, the history and the decision path are the ones that already exist, because `get_decision_authority` resolves through `user_may_act` to that snapshot. Approving it finalises; rejecting it rejects. If excluding the applicant leaves no eligible HR user, submission is refused rather than parked on a stage nobody may act on.

Within one workflow, one employee appears on **one** stage and one role on **one** stage (`section_workflow_approver_unique`, `section_workflow_role_unique`): one office cannot sign off twice on the same application. The same employee or role may still appear in a different team's workflow. The admin and the API agree on this by construction, because it is a model constraint rather than two rules kept in step by hand.

A section that cannot resolve an eligible approver for any *other* reason is a configuration error, never a silent bypass: an application whose chain contains such a step is refused at submission with `workflow_unavailable` (422), and the request never leaves the employee. The advance-time refusal (409 `workflow_unavailable`) remains only as defence in depth for applications whose workflow changed after submission.

---

### 12.4 Balance Integrity

**Pending, rejected, or correction-required annual leave applications must never permanently deduct annual leave balance.**

Annual leave is deducted only after final approval.

Approved cancellation must restore the applicable deducted annual-leave days.

**A charged leave day is a working day: weekends and configured public holidays are never charged.** There is one counting rule in the product — Saturdays, Sundays, and any date HR has configured as a public holiday are not working days — reached both by the validation pipeline at submission and by `leave/services/working_days.calculate_working_days()` for the draft preview and the `preview-days` endpoint. The resulting count is **frozen at submission** (invariant 12.5): holidays HR configures afterwards never re-cut an application that is already in flight, and cancellation restores exactly the days that were deducted rather than recounting. The one thing a holiday change *must* reach is an application still in the employee's hands: `calculated_days` is denormalized, so configuring a holiday re-counts the editable drafts it covers rather than waiting for the employee to re-save.

---

### 12.5 Historical Integrity

**Changes to current configuration must never silently modify the rules, workflow, decisions, or historical state of an already-submitted application.**

Historical applications must retain the applicable processing context.

---

### 12.6 Authorization Integrity

**Every protected backend operation must verify the authenticated user's role and organizational scope.**

A user must never gain access merely because the frontend displays or submits an identifier belonging to another user.

---

### 12.7 Workflow Integrity

**An application must always have a valid configured workflow before submission.**

The system must not submit an application into an incomplete workflow with missing mandatory stages or unavailable required approvers.

---

### 12.8 Document Integrity

**An approved leave document must represent the approved application data and must not be editable through document-template customization.**

Template customization changes presentation, not the underlying approved leave record.

---

### 12.9 Cache Independence

**Loss or invalidation of cached data must never cause loss of authoritative leave-management data.**

Applications, approvals, balances, workflow decisions, and audit records must remain recoverable from persistent storage.

---

### 12.10 Audit Integrity

**Significant workflow, administrative, and decision-making actions must produce an auditable record.**

The audit record must identify the actor, action, timestamp, and relevant previous/new state or reason where applicable.

---

### 12.11 Approver-Role Identity

**An approver role is never deleted, and no historical record may be left unrenderable because HR changed the configuration.**

* A role is retired, never removed: the API exposes retirement (`DELETE` → `is_active=False`), and the foreign keys that reference it are `PROTECT`.
* Retirement is refused while an active workflow or a holder still needs the role, and the refusal names each blocker. Configured state is never left dangling.
* Renaming a role must not rewrite the past. Sections, decisions, and cancellations keep the code and label they were routed with.
* A section is identified by its **(role, name)** pair, so re-ordering a chain keeps each step's appointed approver. A step whose role *or* name changes is a different step and is rebuilt empty — the old appointment is deliberately never handed to a new role without HR asking.
* A step's name is **its role's label**, and a new chain is named after its team, so there is no second typed name per step and no chain name that can disagree with its own steps. The name is still stored, because it is part of a step's identity across writes and part of the snapshot an in-flight application is judged by.
* Membership is held **on the section**, not on the team, and a team's chain is owned by that team alone, so there is exactly one place a person is recorded as able to act and no other team's chain can be changed by editing this one.
* A section names **exactly one approver**, so a step always has a single person to decide whether it is done and the decision always has one author. The same person may hold several sections, and a handover is a removal plus an addition rather than a duplicate row (see 12.13). A team with no chain routes nothing, so a chain is required before a team can be activated.
* A retired role confers no approver status, a section naming it cannot be activated, and its members are removed from routing.

---

### 12.12 Team Lifecycle

**A team's lifecycle is one authoritative field, and only a team in force inside its effective window routes an application.**

* `Team.status` is the single answer — `draft`, `active`, or `inactive`. The former `is_active` boolean is removed rather than kept alongside, so a team can never hold two contradictory answers to "is this routing".
* `draft` is inert **by design**: a team being built routes nothing, which is what makes it safe to create before it is finished. `active` but outside `[effective_from, effective_to]` likewise routes nothing, which is how a dated handover is expressed without a gap.
* The gate lives in the routing provider, not in the UI, and every failure names the team — and the date, where a date is the reason — so an applicant's refusal is actionable rather than a stage error nobody can act on.
* Activation and retirement are actions, not fields: `status` is read-only on `PATCH`. Activation validates first and is refused, leaving the team `draft`, if the chain cannot route. Both are audited, and the audit entry records the status *before* the change.
* A team's detail and action routes reach it whatever its status. A retired team is exactly the one HR needs to read, and a 404 would make retirement indistinguishable from deletion.
* A team owns its chains and routes exactly one of them. `Workflow.team` is the ownership relation (a team may own several, `SET_NULL` when a chain is orphaned); `Team.workflow` is the routing pointer, still one-to-one (`PROTECT`), so a chain is routed by at most one team and two teams can never both route the same steps. There is no shared chain to hand out and no "which chain does this team use?" question to answer — the answer is `Team.workflow`.
* A team is created with its first chain. `POST /teams/` takes `new_workflow`, and `PATCH /teams/<id>/` may too, rewriting the chain the team already routes through rather than replacing it. Steps are matched by `(approver_role, name)`, so reordering moves a step with its roster intact while a renamed step is a different step and starts empty. Applications already inside a step are unaffected either way: `section_ref` is `PROTECT`, so a step an application used cannot be deleted out from under it.
* Creating a team need not send `new_workflow`: a team without one is a chainless draft and routes nothing until its chain is added. The **create form is details-only for that reason** — it writes the team without a chain and lands on the new team's **Members** tab, so employees are added before anyone is appointed — and the chain is configured afterwards from the team's Overview, where a chain added later offers only the people now on the roster.
* Each owned chain is configured on its own through `POST/PATCH /workflows/`, which takes `name`, `team` (create only) and `sections` and *refuses* `effective_from` and `is_active` by name — when a chain begins applying is decided when the team that routes through it is activated, and switching a chain off is retiring that team. A team may not adopt a chain it does not own: the serializer refuses `workflow` on create outright and on update unless the team already owns it. `GET /workflows/?team=` lists a team's own chains.
* Validation returns **every** problem at once, each with a stable code, and is side-effect free. A chain with three unstaffed steps takes one pass, not three.
* `ApplicationStage.section_ref` stays `PROTECT` and `decide()` still reads the `ApplicationStageApprover` snapshot, so retiring a team, re-approving it, or rebuilding a chain cannot change the meaning of an application already inside it.

### 12.13 Membership Is a Period

**A person's ability to act for a step is a date range, not a row that is there or not, and closing a period never erases the fact of it.**

* `SectionMember.effective_from` / `effective_to`; the default manager exposes only **open** (in-force) memberships, `all_objects` exposes every period. "Who can act for this step" and "who could act on the second of March" are different questions and the data answers both.
* Routing resolves approvers from memberships effective **today**, which is what lets a handover be planned: the outgoing approver is dated to a Friday and the incoming one from Monday.
* Removal **closes** a period rather than deleting the row. A membership is the record of who was entitled to act, and deleting it would leave a decision that somebody with no membership today made, unexplainable.
* A period that has not started yet never took effect and is removed outright, so a handover that was called off leaves no row claiming somebody held a step they never held.
* Uniqueness is on the **open** membership: one person, one section, one time. That is what makes a handover — remove, then add — a normal sequence rather than a duplicate-row error.
* The API mirrors the split: the default view is who can act now, `?history=1` is every period.
* Effective-dating never rewrites a running application. The approval snapshot is the authority for anything already submitted.

### 12.14 Team Roster Is Managed on the Team

**Who routes a team's applications is this team's roster, read and written through the team rather than edited on the employee.**

* `EmployeeProfile.team` remains the source of truth for which team an employee routes through (`users.EmployeeProfile`, `related_name="members"`). The team members screen reads it via `GET /teams/<id>/members/`, and `POST` places one employee on the team. Assigning from a picker that offers another team's employee is refused with a message naming that team rather than silently moving the person.
* A roster change is `select_for_update`-protected on the profile row, so concurrent HR edits cannot interleave two writers on one employee.
* Removal refuses while the person still ties to the team: an active section approver, an open approver period, a normal membership on one of the team's chains, or a team-wide role holding. Every blocker is named in the same 409, so HR can release them one at a time rather than being sent back with a bare "no".
* Adding and removing a roster row is audited against `TargetType.EMPLOYEE` with the before/after detail, so membership is part of the personnel history.
* **A roster matches its team's category, and never collects a wide approver.** An academic team takes academic employees; an administration team takes administration employees. `GET /employees/?team=none&category=<...>&not_wide_for_team=<id>` reads the same scoping the write enforces: `EmployeeViewSet` filters by the team's category and excludes the people who already serve it as wide approvers (institution-wide holders, team-wide holders on that team, or campus-wide at its campus), so the member picker offers exactly who `POST /teams/<id>/members/` will accept — and the write refuses both a category mismatch and a wide approver by name, because an approver is placed from the Approvers tab, not booked onto a roster that would silently route their leave.
* **Pickers that write a `User` field must read `employee.user_id`, never `employee.id`.** An `Employee` row from `EmployeeSerializer` carries its record pk as `id` and the linked account as `user_id`; every write that appoints a member, a step member, a delegate, or a `to_approver` resolves against `User`, so a picker that options on `id` sends a record pk as a user pk. When the record pk collided with another account's user pk the write hit the wrong person (a profile-less `User` then failed with "no employee record"); when they diverged the picker stoped offering people the write accepts. The team member add, the team-wide holder feed, delegation create/review, and reassignment pickers are all corrected to option on `user_id`.
* **The team-wide holder picker reads the whole matching directory, not the roster.** A team-wide holder need not be a member of the team — `create_team_role_assignment` accepts any active employee with a record — so the Approvers tab is fed by `listAllEmployees(team.category)`, the directory's half whose holders the write will take. The roster's wide-approver filter belongs to the *members* picker alone; reusing that scoped list on the Approvers tab would silently remove a currently-holding approver from their own replacement picker.
* **A scoped holding carries its scope from the page, not from a select that may not exist.** `WideHoldingPanel` takes a fixed `scopeId` (the team or campus whose page renders it) and draws no scope picker — there is nothing to choose. Only the Approvers page, which offers the choice among many teams, passes `scopeOptions`. The write guard refuses a scoped save with no id (`scope !== "institution" && !scopeId`) rather than sending pk 0, which the backend answers with `Invalid pk "0" - object does not exist`.
* **A wide approver is the same category as the teams they cover.** `create_team_role_assignment` refuses a holder whose profile category differs from the team's; `create_campus_role_assignment` refuses any non-Academic holder — every team at a campus is academic, so a campus holding is always an academic-team holding. Institution-wide holdings serve administration teams only and stay category-free. The pickers offer only what the write accepts: `listAllEmployees(category?)` scopes the team/campus Approvers feeds server-side, and `ScopeOption.category` / `requiredCategory` let the panel filter per chosen scope on the Approvers page.
* **The wide-approver form chooses its role, not its scope.** One panel per scope (institution, team, campus) on the Approvers page — the Approvers page no longer repeats a panel per role — and on the team/campus pages it is the single Approvers form. The role is a drop down whose options carry the scopes they may be written at: the institution panel offers every active role, while the team and campus panels offer scoped roles only (`!is_institution_wide`), so a role that would be refused at a team/campus scope is never offered there. The person picker is disabled until a role is chosen, offers only the scope's category, and excludes the people who already hold that role at that scope.
* **A person holds only one wide approver role, at one of the three scopes.** Once somebody is a wide approver anywhere they are gone from the picker of every other wide-approver section — institution, any team, any campus — because two sections claiming the same person is how HR loses track of who actually covers what. All three writes (`create_role_assignment`, `create_team_role_assignment`, `create_campus_role_assignment`) now run `_ensure_single_wide_holding`, which refuses a user who already holds a wide role at any other scope/role and names the existing holding ("… already holds Registrar institution-wide …"). The null space is the write itself: the same role at the same scope is the holding being written, so re-saving it (or re-pointing a holder at the same scope) still works. Every page computes the union of all holders' user ids — Approvers from its three lists, the team page and campus page by reading the institution/team/campus holdings unfiltered — and passes it to the panel as `excludedUserIds`, so the picker offers only people the write accepts.

### 12.15 Normal Workflow Membership Is a Team-Scoped Assignment

**"A team member on this chain" is its own record, separate from the step appointments that decide applications.**

* `WorkflowMember` is the pair (workflow, user) with a denormalised `team` for scoping, unique at the database level on both (workflow, user) and — unless the person is a **wide approver** — (team, user). The second constraint is a conditional `UniqueConstraint` on `(team, user)` where `is_wide_approver = False`, so one employee serves one of the team's chains at a time *except* the wide exception, and even a concurrent write cannot route around either side of that rule.
* Membership is written through the workflow (`POST /workflows/<id>/members/`, whole-list `members: [user_id]` on the workflow write) and the eligibility pool is read from the team (`GET /teams/<id>/workflow-member-pool/?workflow=<id>`). The pool splits `available` (may join), `current` (already on this chain), and `assigned_elsewhere` (on a sibling chain — a step approver counts exactly like a normal member — read-only and named), so an edit screen can only ever offer people the write will accept.
* One employee serves **one of the team's chains at a time**, whether staffing a step (active `Section.approver`) or as a normal member. The write paths agree: `ensure_not_assigned_elsewhere` runs inside `ensure_membership_allowed` for step appointments, and `assign_workflow_member` refuses a non-wide person who already serves another chain. A section's own workflow is excluded from the comparison, so re-saving the same appointment is not a conflict with itself.
* A **wide approver** is the exception: someone holding a team-wide role on this team, a campus-wide role at this team's campus, or an institution-wide role staffs chains automatically, so they may sit on several at once. The eligibility pool, the approver picker, and both write paths keep offering them; `WorkflowMember.is_wide_approver` is set at write time from the live holdings and is what the conditional constraint keys on.
* The approver picker applies the same rule before HR picks: `GET /teams/<id>/eligible-approvers/?workflow=<id>` drops anyone already on a *different* chain of the team, `?workflow=new` drops anyone on *any* of the team's chains (a chain not created yet), and the workflow form writes each step's `approver` at chain-write time. Wide approvers stay offered.
* Members are the submitters a chain decides; step approvers (Sections) are who acts. The two are kept visibly distinct in the data and in the UI.
* Add/remove/sync membership changes are audited against `WORKFLOW` with before/after details, so a chain's member list is part of its history like its steps.

---

## 13. Architecture Decisions Still To Be Confirmed

The following decisions are intentionally left open until the relevant LUANAR infrastructure and organizational requirements are investigated:

| Decision                                 | Status |
| ---------------------------------------- | ------ |
| Production file-storage technology       | TBD    |
| Development/test file-storage equivalent | TBD    |
| Production database infrastructure       | TBD    |
| Institutional identity provider          | TBD    |
| Employee-data source/integration         | TBD    |
| Cache technology                         | TBD (dev uses Django's local-memory cache; no Redis dependency) |
| Background-job technology                | Confirmed: Django-Q2, Postgres as ORM broker (no Redis) |
| Email provider/institutional mail system | TBD    |
| Public-holiday data source and fallback  | TBD    |
| Personal-file/document integration       | TBD    |
| Exact deployment infrastructure          | TBD    |

These decisions should be added to this document once confirmed. They should not be assumed during implementation merely to fill architectural gaps.

```
```

