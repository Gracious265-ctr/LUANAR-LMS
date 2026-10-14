# Spec 32 — HR Guided Setup and Daily Operations

## 1. Purpose

The system's individual capabilities (specs 02–31) are complete, but the HR
administrator has to visit many separate, developer-shaped pages to get the
system ready and to keep it running. This spec adds a **guided layer** on top
of the existing configuration so that one generalist HR user can:

1. bring the institution from empty to "employees can apply" in a short,
   ordered session, and
2. run the recurring day-to-day work (approve leave, onboard staff, start a
   new financial year) without knowing the internal model.

Nothing here replaces the underlying pages; it sequences and simplifies them.

**Target user:** one non-technical HR generalist. No other administrator is
assumed.

## 2. Setup Hub

`/dashboard/hr-admin` is the HR home and the entry point of the guided path. It
renders a `SetupHub` component fed by `GET /api/v1/setup/status/`.

`SetupStatus` reports, per step, whether it is done and (for steps that create
data) how many objects exist:

| Step | Done when | Backed by |
|---|---|---|
| Financial year | an active financial year exists | `leave` financial-year |
| Leave types & rules | the expected leave types exist | `leave` type/rule |
| Entitlements | entitlement bands exist | grade entitlements |
| Approver roles | the six approver roles exist | `workflows` roles |
| Teams | at least one team is activatable | `workflows` teams |

Each step links to the page that owns it. When the configuration is empty, the
hub offers **Apply default configuration** (see §3). The hub is deliberately
read-only apart from that one action.

### 2.1 Apply default configuration

`POST /api/v1/setup/apply-defaults/` seeds the known-good baseline. It is:

- **Additive and idempotent** — it merges on natural keys and skips anything
  that already exists, so re-running never overwrites HR's edits.
- **Audited** — one `PRESET_APPLIED` summary row, plus per-object `CREATED`
  rows only when at least one object was created.
- **On demand** — never run automatically.

`GET /api/v1/setup/templates/` returns the approver role specs and the workflow
templates the UI renders as choices.

**Preset contents**

- Financial year 1 July – 30 June.
- Leave types with rules: annual (30, consumes balance), maternity (90, F),
  paternity (10, M), compassionate (5); none require a supporting document by
  default.
- Entitlement bands: grades A–C = 21, D–G = 24, H–U = 30.
- Six approver roles: `supervisor`, `hod`, `dean`, `registrar`,
  `campus_registrar`, `dvc`. `registrar` and `campus_registrar` are
  institution-wide; `hod` resolves within the same team.

### 2.2 Financial-year rollover

`POST /api/v1/setup/rollover/` copies the previous active year's **leave rules
only**. Entitlement bands are defined once and persist across years, and public
holidays are date-unique; neither is copied. Rollover deactivates the previous
active year (one active year at a time). It is a no-op when the active year
already starts after today (guards against double-rollover).

## 3. Guided Team Creation

`/dashboard/hr-admin/teams` lets HR create a team **and its approval chain in
one submit**, using code-defined workflow templates rather than a stage builder.

- Templates: *academic* — `supervisor → hod → registrar → dvc`; *administration*
  — `hod → dean → registrar → dvc`. Templates are code constants
  (`workflows/presets.py`), not database rows.
- The picker defaults to **Build it myself**, which creates a chainless draft
  (the existing behaviour).
- Choosing a template sends `new_workflow` on the team payload; `create_team`
  builds the chain atomically with the team, so a failure leaves neither behind.
- A template whose roles do not yet exist is disabled, with the hint to run
  **Apply default configuration** first.
- After creation the user lands on the team page (no forced detour into a
  secondary tab).

## 4. Single-Screen Onboarding

HR creates an employee from `/dashboard/hr-admin/employees` in one screen:
email, names, category, grade, and team (drawn from an existing-team picker).
The role is fixed to *employee*; approver standing is data (a role held), not an
account role. On create, the backend issues an unusable password and emails a
set-password link, so HR never chooses or sees a password; the form states this.

Team assignment is offered **on create only**; moves are handled by the team
roster so a hire and a transfer do not share one ambiguous control.

## 5. Daily Operations — Bulk Approval

Approvers review from `/dashboard/approvals`. On the **pending** tab only, rows
carry a checkbox; a toolbar shows `N of 25 selected` and offers **Approve
selected**.

- `POST /api/v1/approvals/bulk-decision/` — body
  `{ action: "approve", comment?, items: [{ id, stage_version }] }`.
- **Approve-only and capped at 25.** Reject and return require a per-item
  comment, so they stay one-at-a-time. More than 25 items, duplicate ids, or an
  empty selection are rejected with 400.
- Each item runs through the same locked `decide` path, with its own transaction
  and audit row, so **partial success** is expected: the response reports
  `{ results: [{ id, status, reason? }], approved, failed, limit }` and the UI
  surfaces successes and failures separately.
- `stage_version` is the pending stage's `decision_version`, surfaced on the
  list payload so a batch can be built without opening each application; it
  guards against deciding a stage that moved on (reported as `stage_changed`).

## 6. Navigation / Information Architecture

The HR rail is split into a short **everyday** set and a folded **Advanced**
group:

- Everyday: **Setup**, **Employees**, **Teams**, **Approvers**, **Campuses**.
- Advanced (collapsed by default, expandable): **Roles**, **Leave Types**,
  **Entitlements**, **Leave Rules**, **Calendar**, **Delegations**,
  **Reassignments**, **Document Template**, **Leave Day Plans**, **Audit View**.

Raw configuration pages stay reachable but no longer crowd the primary path. In
a collapsed rail the group header is omitted and its items render flat so icons
remain reachable.

## 7. Out of Scope

- A document-template editor, plan-settings editor, and audit viewer redesign.
- Bulk vacancy-fill / bulk role assignment (backlog).
- Any change to the underlying RBAC, audit, or approver-resolution invariants.

## 8. Backend Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/setup/status/` | guided-setup progress |
| GET | `/api/v1/setup/templates/` | role specs + workflow templates |
| POST | `/api/v1/setup/apply-defaults/` | seed the baseline |
| POST | `/api/v1/setup/rollover/` | copy rules into the new year |
| POST | `/api/v1/approvals/bulk-decision/` | approve up to 25 items |

All require an authenticated HR user (`IsAuthenticated`, `IsHRRole`), except the
bulk-decision endpoint, which requires approver access via the normal approval
permissions. Every write is audited.

## 9. UX Targets

- Setup: ≤ 10 actions across the first session.
- Team → activatable: ≤ 5 actions.
- Onboard an employee: ≤ 1 screen.
- Roll over the financial year: ≤ 3 actions.
