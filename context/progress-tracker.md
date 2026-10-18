# Progress Tracker

Update this file after every meaningful implementation change.

## Current Phase

- **HR leave-system simplification — IN PROGRESS (started 2026-10-11)** — the
  approved 7-phase plan to reduce the steps HR takes across the whole leave
  system (one non-technical generalist HR user): setup spine → onboarding →
  daily ops. Guardrails: every write audited, separation of duties,
  retire-not-delete, approver resolution snapshotted, one holder per role/scope.
  Targets: setup ≤10 actions/session; team→activatable ≤5 actions; onboard
  ≤1 screen; rollover ≤3 actions.
  - **P1 backend preset + setup spine — DONE.** `workflows/presets.py`
    (`ROLE_SPECS`, `WORKFLOW_TEMPLATES` for academic
    `supervisor→hod→registrar→dvc` / administration
    `hod→dean→registrar→dvc`); `leave/services/setup.py`
    (`apply_defaults`/`setup_status`/`rollover_financial_year`, `ApplyResult`);
    `leave/views/setup.py` + `leave/urls.py` (`setup/status`, `setup/templates`,
    `setup/apply-defaults`, `setup/rollover`, all `IsHRRole`); audit
    `Action.PRESET_APPLIED` (+ migration `0022_alter_auditentry_action.py`).
    Rollover copies **leave rules only** (entitlement bands are date-less and
    persist across years), deactivates the previous active year, and is a no-op
    if the active year starts after today. `leave/tests/test_setup.py` (16 tests);
    `leave workflows audit` = 1133 tests OK; `makemigrations --check` clean.
  - **P2 backend bulk approvals — DONE (2026-10-15).** The earlier "DONE"
    claim was inaccurate: no bulk code existed in git history when restructure
    Phase 0 audited it, so it was reimplemented rather than assumed.
    `workflows/approval_views.py` now has `BulkApprovalDecisionAPIView` +
    `BulkApprovalInputSerializer`/`BulkDecisionItemSerializer`
    (`BULK_APPROVAL_LIMIT = 25`), routed at `approvals/bulk-decision/`
    (registered before the `<str:pk>` routes). Approve-only, cap 25, empty/
    duplicate/>25 all 400; each item runs the locked `decide` in its own
    transaction → partial success, reporting `{results:[{id,status,reason?}],
    approved, failed, limit}`. `list_item` now surfaces `stage_version` (the
    pending stage's `decision_version`) and the pending list `select_related`s
    `current_stage`. `workflows.tests_approvals.BulkApprovalAPITests` (9);
    `workflows.tests_approvals` = 91 OK.
  - **P3 frontend setup hub — DONE.** `lib/setup.ts` (pure types/constants),
    `lib/setup-server.ts`, `lib/setup-client.ts`, proxy routes
    `app/api/hr/setup/{apply-defaults,rollover}`, `SetupHub.tsx`, restructured
    `hr-admin/page.tsx`; `tests/setup-hub.test.tsx` (8). tsc/eslint clean.
  - **P4 guided team creation — DONE.** A ready-made chain can be adopted on
    team create, writing team + chain + ordered steps in one transaction via the
    existing `new_workflow` (no backend change): `team-form.tsx` gains a
    `templates` prop + "Approval chain" picker ("Build it myself" default),
    `TeamsSection.tsx` passes it through, `teams/page.tsx` fetches it. A template
    whose roles do not exist yet is disabled with an "Apply default
    configuration" hint. `tests/team-form.test.tsx` = 19 OK; full frontend suite
    950 OK (excl. the two known-flaky files); tsc/eslint clean.
  - **P5 single-screen onboarding — DONE.** `employee-form.tsx` gains a
    create-only **Team** picker and a "they set their own password" note
    (the backend already issues an unusable password and mails the set-password
    link on create); `employees/page.tsx` fetches teams, `EmployeesSection.tsx`
    passes them through, so a new hire routes from the moment the account
    exists. Edit deliberately still omits team — the roster owns the move.
    `tests/employee-form.test.tsx` updated (21 OK with the overlay suite);
    full frontend suite 951 OK (one load-only timing flake in the untouched
    entitlement form, passes isolated).
  - **P6 ops inline + bulk approve — DONE (2026-10-15).** `lib/approvals/types.ts`
    gains `stage_version` on the list item + the `BulkApproval*` types;
    `lib/approvals/service.ts` gains `approveApprovals`; proxy
    `app/api/approvals/bulk-decision/route.ts`; and `approvals-list.tsx` wires
    the pending tab's selection (row checkboxes on desktop + mobile,
    "Select all on this page", "N of 25 selected", cap disables further picks,
    "Approve selected") to the `BulkApproveDialog` (typed `APPROVE`
    confirmation). Successful items toast a count; failures render an `Alert`
    listing each reference and its reason. `tests/approvals-list.test.tsx` = 12
    OK; full frontend suite 960 OK / 111 files; `build`/`lint`/`typecheck:test`
    clean.
  - **P7 nav/IA + polish + docs — DONE.** HR rail split into everyday
    destinations (Setup, Employees, Teams, Approvers, Campuses) plus a folded
    **Advanced** group (Roles, Leave Types, Entitlements, Leave Rules, Calendar,
    Delegations, Reassignments, Document Template, Leave Day Plans, Audit View);
    the group uses a new `NavGroup` disclosure (collapsed by default, and renders
    flat when the rail is collapsed so icons stay reachable). Nav home renamed
    "HR Administration" → "Setup" to match the hub. `tests/dashboard-shell.test.tsx`
    25 OK; tsc/eslint clean. Feature documented in
    `context/specs/32-hr-guided-setup-and-ops-spec.md`.
  - **All 7 phases DONE.** Remaining: final full-suite verification.

- **Unit 5 — System Restructure into Feature Modules + App Launcher — IMPLEMENTED (2026-10-13)** — refinement unit `context/refinement/05-system-restructure-app-launcher.md`. Reorganized backend into `leave` (unchanged), new `approvals` (stages/decisions), new `org` (org/teams/roles/assignments), `documents` (unchanged), with shared infra `users/notifications/audit`. Created `launcher` app with `/api/v1/apps/launcher/` aggregator returning role-filtered apps with badge counts. Frontend: app registry (`lib/apps-registry.ts`, `lib/launcher.ts`), launcher UI (`components/launcher/*`), and module-scoped shells (`ModuleShell`) with per-module layouts and "← All Apps" navigation. (Launcher landing location corrected on 2026-10-14 — see troubleshooting note: the page lives at `/(launcher)/page.tsx` on `/` with its own minimal shell, not `/(dashboard)/page.tsx`.) TypeScript and ESLint pass. Migrations created for new apps; import paths updated across codebase. (Full backend test suite migration state requires clean DB in this environment, but core restructuring per spec is complete.)

- **System Restructure — Phase 0 (stabilize) — DONE (2026-10-15)** — pre-work
  for the independent-app refactor (`context/refinement/05-...`). Fixed the
  regressions left by the broken merge and made the two suites trustworthy as a
  baseline:
  - **Migration reversibility.** Reverted `workflows/0026` and
    `users/0010` to plain, fully-reversible ops (dev DB is disposable); the
    30-test `workflows.tests_migrations` suite passes.
  - **Launcher owns `/`.** Deleted the route-colliding `app/page.tsx`;
    `/` is now the `(launcher)` route with no build warnings.
  - **Bulk approvals implemented.** The audit found the P2/P6 "DONE" claims
    false (no bulk code in git history) and the two frontend artifacts dead
    orphans; rather than delete-and-forget, the feature was built end-to-end
    (see P2/P6). Frontend suite **960 OK / 111 files**.
  - **Service stubs fixed.** `approvals/services.py`, `org/services.py`,
    `launcher/services.py` now import real primitives (`is_approver_user`,
    `role == "hr"`); launcher smoke test: employee → `leave,documents`,
    HR/superuser → all apps.
  - **Multi-step leave form implemented** (refinement 04 §3.4-§3.6) — see the
    Unit 5 item-4 note below; `Stepper` gained opt-in step-click props, and
    `LeaveTypeSelect` became parent-owned. 8 previously-failing
    `tests/leave-application-form-steps.test.tsx` now pass.
  - **Test infra.** `vitest.config.ts` sets `testTimeout`/`hookTimeout` = 15s;
    the 3 timeout flakes (`entitlement-form`, `hr-admin-form-overlays`,
    `plan-form`) pass under load. `npm run build`, `npm run lint`,
    `typecheck:test` all clean. Backend baseline `test workflows audit` =
    **645 OK**, `makemigrations --check` clean.

- **System Admin Dashboard (Django Admin Extension) — COMPLETED (2026-10-11)**
  — refinement unit
  `context/refinement/03-unit-system-admin-dashboard.md`, implemented on the
  Django built-in admin (`django.contrib.admin`), not the Next.js frontend.
  Placement decisions confirmed at planning: the site is mounted at
  `/system-admin/`, registered *in place of* the default via
  `AdminConfig.default_site`, so every existing `@admin.register` keeps working
  unchanged. **Spec A4's middle "HR" tier is deliberately dropped** (developer
  decision): this surface exists for the developer to observe system stats and
  performance, and HR is an end-user of the Next.js product, so no HR stat
  subset and no HR test matrix are built. Superusers see the full stat set, the
  system-health panel, and the recent-admin-actions panel; every other staff
  account (including HR) sees stock, unmodified Django admin with none of those
  context keys. All three account-management audit events named in §2.6 ship as
  actions (`grant_superuser`, `revoke_superuser`, `grant_staff_access`). The
  "recent errors" card reuses Django-Q2's `Failure` table rather than adding a
  logging-storage pipeline (§2.4's permitted simpler path). See "Completed —
  System Admin Dashboard" at the end of this file when done.

- **UI/UX Premium Polish Pass — IN PROGRESS (started 2026-10-07)** — refinement
  unit `context/refinement/01-ui-ux-premium-polish.md`, all 18 items across
  Tiers 1–3 in scope (developer decision). Scope decisions confirmed at planning:
  the ChainStepper replaces the existing stage lists on the tracking and approver
  review pages via an adapter over the real payloads plus fixtures for
  vacant/acting states (spec A3); the Notification model is fed by the approval
  bus, the cancellation bus, and the previously receiver-less Unit-14 submit
  signal (so approvers get "awaiting your review" notifications). The status
  color audit (`STATUS_STYLES`) is the first slice since the stepper, badges,
  tables and dashboard all import from it. See "Completed — UI/UX Premium
  Polish Pass" at the end of this file when done.

  **§3.5 (item 5 of 18) shipped 2026-10-07 — toasts + optimistic UI; §§3.6–§3.10
  partially shipped (A1/A2/A3, B1 done; notification bell, blur validation, table
  enhancements, animated counters, Tier 3 pending).** A deliberate spec supersession
  underpins this item: the base specs (`16-approver-review-and-decision.md:327`,
  `18-leave-cancellation.md:244`, `19-supporting-document-lifecycle.md:153,226`)
  all say "No optimistic updates", while refinement §3.5 mandates immediate local
  state updates with rollback for **every** mutating action in Units 13–19. The
  developer chose the literal refinement: patch local state the moment the
  request is dispatched, let the server response reconcile on success, and
  revert plus raise an error toast on failure — the base-spec lines are now
  stale, not contradictory. One toast primitive serves it all
  (`components/ui/toast.tsx`): a module-level store read via
  `useSyncExternalStore`, `pushToast`/`useToast` writers, and a single `Toaster`
  mounted in `dashboard-shell.tsx` as a bottom-right stack (`fixed right-4
  bottom-4 z-toast`, newest at the corner, cap 4, identical message replaces
  itself, 4s default, dismissible). Enter/exit are the CSS motion tokens, and a
  dismissed toast stays mounted for `EXIT_MS = 200` so `animate-toast-out`
  actually plays — kept CSS-only (no framer rAF) so it behaves under fake
  timers. Optimistic sites: approval decision (`withOptimisticDecision` patches
  my stage, promotes the next waiting stage, terminal states clear
  `current_stage`), cancellation decision panel, cancellation section
  eligibility (`cancellation_action → null`, `openAction` split so the dialog
  survives the patch), cancel dialog (an `action_changed` conflict deliberately
  *keeps* the patch — restoring a button the server no longer honours would show
  a stale control — and offers "Refresh and review"), draft delete
  (`removeLocal`/`restoreLocal` in `useLeaveApplications` plus a new silent
  refetch so deletes and submits never flash skeletons), and documents
  (upload placeholders keyed by client token, optimistic rename on replace,
  optimistic row removal — all rolled back or reconciled against a server
  refresh). The submit hook fires "Application submitted." *before* navigating
  so the confirmation survives the route change; cover requests toast
  "Cover requested." Three deliberate non-toasts, recorded so they are not
  re-litigated: autosave already reports through its inline `saveStatus`
  indicator (a toast per keystroke pause would spam), 422 validation issues stay
  inline-only (the field-level message is the signal; a toast would drown it),
  and conflicts use the **info** tone ("This request changed. Refreshing…")
  because they are a recoverable state change, not a failure. Tests: the toast
  stack resets via `afterEach(resetToasts)` added to `tests/setup.ts` so the
  module store cannot leak across files; `ui-primitives` now asserts the stack
  semantics (polite live region, auto-dismiss + exit window, early dismiss,
  independent per-message countdowns, dedupe, bottom-right position), and the
  cancellation/application tests render `<Toaster />` to observe outcomes.
  Verified: 882 frontend tests (101 files) OK, typecheck (both), eslint, production
  build clean. Backend untouched this item.

  **Form overlays (A1–A3 + B1):** HR admin users moved into `AdminUsersSection`
  overlay (`?user=new|id`), plans workspace owns a `?plan=new` overlay, HR
  reassignments queue owns a `?reassign=id` overlay (with employees fetched on
  demand and `notFound` for stale ids), and the standalone leave review route
  became a shim to `?edit=<id>&stage=review` with tests retargeted to
  `LeaveReviewPanel`.   Shared primitives: `AdminFormOverlay` + `useOverlayParam`
  (back closes, stale ids handled, edit-from-row on screen).

- **UI/UX Phase 2 (Tier 1 + Tier 2) — COMPLETE (2026-10-11)** —
  refinement unit `context/refinement/04-ui-ux-phase-2.md`, **items 1–7 only**
  (Tiers 1–2) per the developer's scoping decision. Tiers 3–4 are deferred to a
  later pass; recorded placements decided at planning but **not built**: the
  "what's-new" popover lives on a new header icon with a dot badge (there is no
  notification bell in this app), and skip-to-content targets
  `dashboard-shell.tsx`'s `<main>` (there is no "floating-shell"). Decisions
  confirmed at planning: the calendar's "unit" is `workflows.Team` (the spec's
  A2 fallback — no `OrgUnit` model exists); **conflict is a hard block, not a
  visual flag** (developer override of A3): `decide()` refuses an Approve that
  would put more than 30% of the applicant's team out on any day, counting all
  leave types and both approved and pending entries, at every approval stage,
  backend-authoritative; undo-on-cancel is an **immediate reversible endpoint**
  with a 5s grace window covering both withdrawal and cancellation-request
  submission. §3.5 autosave was already shipped in the premium polish pass, so
  this unit only adds a failure toast and **keeps the existing 800ms debounce**
  rather than the spec's ~2s (deliberate deviation: 800ms is already tested and
  is better UX). Verified: backend full suite OK apart from two known
  pre-existing failures (a timezone-boundary flake in
  `system_admin.tests.DashboardStatsTests`); new undo/guard tests pass; frontend
  949 tests OK; `tsc` and `eslint` clean.
  - _Progress (2026-10-11)_: items 1–2 **done** — backend
    `leave/conflicts.py` (shared cap `max(1, ceil(0.3n))`),
    `leave/views/calendar.py` + `calendar/team/` route,
    `workflows.policies.user_can_view_team_calendar`, the hard block in
    `WorkflowService.decide` (`ApprovalConflictError` → 409), and
    `leave/tests/test_team_calendar.py`; frontend `lib/calendar/*`,
    `app/api/leave/calendar/team/`, `components/calendar/TeamLeaveCalendar.tsx`
    + `ApprovalConflictNotice`, embedded on the approver review page, with
    tests. Item 3 **done** — `RulesProvider.get_annual_entitlement` (protocol,
    database + fixture + stub providers) surfaced as `entitlement_balance` in
    the validation payload, and `components/ui/BalanceRing.tsx` (remaining-share
    SVG dial) wired into the dashboard balance card and the application-form
    `BalanceCard`; tests added. Item 4 **done** — `LeaveApplicationForm` now a
    4-step flow (horizontal `Stepper size="sm"` with clickable settled steps,
    per-step validation gating, documents step `skipped` when not required);
    `Stepper` gained opt-in `onStepClick`/`isStepClickable`/`stepAriaLabel`
    props and `LeaveTypeSelect` became parent-owned (optional `types`/`loading`/
    `error`; the form owns the list so the skipped-steps logic can read
    `requiresDocuments`). Item 5 **done** — autosave failures raise a
    `pushToast` (success stays silent; 800ms debounce unchanged). Item 6
    **done** — `GET /api/v1/leave/me/form-defaults/` (`LeaveFormDefaultsView`)
    returns the last-used leave type, the next working day (weekends + public
    holidays skipped), and per-type available balances; the create form
    warm-starts from it through `lib/services/leaveFormDefaults.ts`. Item 7
    **done** — immediate reversible `POST
    /api/v1/leave-applications/{id}/undo-cancel/` (`undo_cancellation`,
    `Status.UNDONE`, `CANCELLATION_UNDONE` audit) with a 5s grace window; the
    cancellation toast now carries an "Undo" action (`ToastAction`) and
    `components/cancellations/cancellation-section.tsx` wires it up.

- **Team Member Management and Workflow Member Eligibility COMPLETE** — backend,
  frontend, tests, and docs; see "Completed — Team Member Management and Workflow
  Member Eligibility (2026-10-07)" at the end of this file. A team's roster is
  managed on the team with removal safeguards, and normal workflow membership is
  a team-scoped assignment enforced by a `(team, user)` unique constraint with a
  backend-computed eligibility pool. Follow-up **Second-Workflow Exclusion
  COMPLETE** (same day): one employee serves exactly one of the team's chains at
  a time — as step approver *or* normal member — unless they are a wide
  approver; see "Completed — Second-Workflow Exclusion and Chain-Scoped Approver
  Picker (2026-10-07)" at the end of this file.
- **Unit 31 — annual leave is provisioned by entitlements** — see "Unit 31 —
  Annual leave is owned by the entitlement form" at the end of this file. Saving
  an entitlement creates annual leave and its starting rule, and annual leave is
  read-only in Leave Types.

- **Vercel design mechanics on LUANAR identity (2026-10-01)** — the app was
  built on shadcn defaults that did not match the target aesthetic: a 6/8/12/16px
  radius ladder where the design calls for a flat 6px, a slate-tinted shadow
  scale, a 2px accent ring with a `ring-offset`, and 13px captions. Applied the
  mechanics while keeping LUANAR blue `#0097F0`, institutional green `#009119`,
  and Geist Sans headings. Radius collapsed to `6px` (`4px` for status labels,
  `9999px` only for genuine circles), so ~256 existing `rounded-md/lg/xl` call
  sites resolve to 6px with no edits. Shadow scale replaced with the border-first
  spec, and the shadcn `sm`/`md` names aliased *down* to the card depth. Focus
  became one shared `focus-ring` utility (opaque white inner ring, then LUANAR
  blue) replacing six ad-hoc `ring-2 ring-offset-2` variants. `sm`/`md`
  breakpoints moved to 600px/960px so the two-column and table/card switches wait
  for a genuinely wide viewport; `lg` stayed at 1024px. Added a Radix-dialog
  mobile drawer behind a hamburger, sharing one `NavLinks` list with the desktop
  rail, plus a 44px touch-target floor below `md`. Also fixed a live bug: the
  `draft` badge tone referenced `bg-surface-secondary`, which has never existed,
  so draft badges rendered with no background. Frontend 610 tests OK, typecheck,
  lint and production build clean. See "Completed — Vercel design mechanics
  (2026-10-01)" at the end of this file.

- **Real users, real inboxes (2026-10-01)** — mail could reach nobody: HR creates
  accounts with `set_unusable_password()` and there was no way for a real person
  to obtain a password, so a new employee could not sign in and could never
  receive a notification. Added the set-password flow (72h single-use emailed
  link, hash-only storage, no account enumeration, throttled, audited, queued
  through the outbox's new `user` subject family), auto-send on employee create,
  an HR resend action, and a `retire_demo_users` command that deactivates the
  `@test.luanar` demo accounts without touching their history. Also fixed a real
  bug this surfaced: DRF read an absent boolean in a form-encoded request as
  `False`, so creating an employee with `curl -F` produced a **deactivated**
  account. Backend 1198 tests OK, frontend 574 tests OK. See "Completed — Real
  users, real inboxes (2026-10-01)" at the end of this file.
- **Email delivery made real (2026-09-30)** — the outbox existed but mail never
  left the machine: console backend hard-coded, sends inline, cancellation bus
  still a no-op sink, housekeeping unscheduled. All four fixed (env-configured
  SMTP, single queued send site via django-q2, cancellation consumer + subject
  family, `django_q.Schedule` row) plus read-only outbox admin. Backend 1151 tests
  OK. See "Completed — Email delivery made real (2026-09-30)" at the end of this
  file. Live SMTP verification still needs the user's Gmail credentials in
  `backend/.env`.
- **Team Management (Units 1–10) COMPLETE** — backend, frontend, and docs; see
  "Completed — Team Management (Units 1–10)" at the end of this file. Team
  lifecycle is one authoritative field, membership is effective-dated, and a
  team is created with its chain. Unit 11 is deliberately out of scope.
- **Standalone Workflow management REMOVED** — a team owns its chain one-to-one,
  so chains are written with the team and edited on the team form. The
  `/dashboard/hr-admin/workflows` screens, their API route, and the write API
  and admin are gone; `Workflow` stays as a read-only model because routing,
  snapshots, and audit entries point at it. Verified: backend 1085 tests OK,
  frontend 420 tests OK, typecheck/lint/build clean.
- Workflow Sections migration (follow-on to Unit 26 — backend complete, frontend complete, docs updated; see "Completed — Workflow Sections (Sections/members) migration" at the end of this file)
- Dev database fully reset and both dev servers restarted (2026-09-29) — see
  "Defect Fixes + Operational (2026-09-29, full dev reset — everything cleared)";
  that pass also fixed three defects the reset exposed, two of them in
  `seed_approvals_dev`, so the seed now runs clean and is idempotent
- Unit 26 — HR-Managed Approver Roles and Teams (COMPLETE — implemented and verified, committed as `4352a69`)
- Unit 25 — End-to-End System (COMPLETE — implemented and verified, committed as `6f9474e`)
- Unit 24 — Complete Audit and Historical Integrity (COMPLETE — committed as `d4860f3`)
- Unit 23b — Approved Leave Document (COMPLETE — spec approved, `reportlab` approved, 717 backend tests OK, 302 frontend tests OK)
- Unit 23 — Final Approval, Balance, and Document (COMPLETE — committed as `eb7361d`; its document half was split out and shipped as Unit 23b)
- Unit 22 — Email Notifications (COMPLETE — committed as `1a64d1e`)
- Unit 21 — Workflow-to-Approver Integration (COMPLETE)
- Unit 20 — HR-to-Employee Data Integration (COMPLETE)
- Unit 19 — Supporting Document Lifecycle (COMPLETE)
- Unit 11 — HR Finalized Leave + Audit View (COMPLETE)
- Unit 15 — Employee Application Tracking (COMPLETE)
- Unit 16 — Approver Review and Decision (COMPLETE)
- Unit 18 — Leave Cancellation (COMPLETE)
- Unit 14 — Leave Validation and Submission (COMPLETE)
- Unit 13 — Leave Application and Drafts (COMPLETE), integrated onto `development`
- Unit 10 — HR Approved Leave Document Template (COMPLETE)
- Unit 9 — HR Emergency Reassignment (COMPLETE)

## Current Goal

- **Unit 26 — HR-Managed Approver Roles and Teams is COMPLETE** (see
  "Completed (Unit 26)" at the end of this file). Approver roles are now HR
  configuration instead of role names baked into the code, and approval
  routing is team-based. It landed beyond the build plan (which ends at Unit
  25) from a direct feature request, so it has **no spec file** — the
  authority is the feature prompt plus this section. It also carried Unit 21's
  still-uncommitted provider work into the same commit, since Unit 26 rewrote
  `resolve_stage_approver` over it.
- Both independent tracks (HR: Units 2–11; Employee+Approver: Unit 13) are merged
  onto `development`, and the HR track's next build **Unit 11 — Finalized Leave +
  Audit View** is complete (depends on the submitted applications Unit 13 provides).
- **Unit 16 — Approver Review and Decision is COMPLETE** (see "Completed
  (Unit 16)" below). It delivers the approver queue, review/decision screen,
  and decision service on the Unit 15 status enum/badges, tracker component,
  and stage/decision contract; Unit 15 endpoints/payloads are extended
  additively by Unit 17 (rejection/correction/resubmission) and Unit 18
  (cancellation) per their specs.
- **Unit 18 — Leave Cancellation is COMPLETE** (see "Completed (Unit 18)"
  below). Employee withdraw/request UI on the tracking page, a pending-approval
  Supervisor/HOD stage chain, and the approver queue/decision surface reachable
  from `/approvals` via a segmented switch and `?cancellation=` panel.
- **Unit 19 — Supporting Document Lifecycle is COMPLETE** (see "Completed
  (Unit 19)" below): editable-status document upload/remove/replace (draft
  hard-delete vs correction retire/replace; retired rows kept for the archive
  with lifecycle fields), a tracking `documents` block plus a read-only
  Supporting documents card with an Archived section, and the required-document
  validator counting active rows only. Backend **604 tests** and frontend
  **296 tests** green, `tsc` + `npm run lint` clean; no new migration (Unit 17
  already shipped the `status`/`retire_*`/`replaced_by` schema).
- **Unit 21 — Workflow-to-Approver Integration is COMPLETE** (see "Completed
  (Unit 21)" below): the last two fixture providers are gone — routing now
  reads the real HR workflow configuration, tracking reads real workflow rows,
  and resubmission is a real routing step. Committed as `4352a69`, which also
  supersedes the "lowest-id active user of the stage role" approver rule
  described above with team-scoped `resolve_stage_approver`.
- **Unit 23 — Final Approval, Balance, and Document Generation (SPEC DRAFTED).**
  The draft spec was reviewed in Phase 1 (2026-09-25): the old draft's wrong
  references (HR Unit 12 credit-line, HR Units 8–9 special-leave balance,
  "delete the fixture balance provider") were removed and decisions D1–D8 were
  rewritten against what the code actually contains. Awaiting developer
  approval before implementation; DOCX is explicitly deferred (PDF only, no
  `python-docx`).

## Completed (Unit 19)

- **Backend — document lifecycle service + view.** `leave/documents/services.py`
  owns the lifecycle: editable guard (draft + correction_required only),
  hard-delete in draft (row + storage; storage-delete failure logs and
  continues) with a `document_removed` audit row, retire for correction
  remove/replace (`removed`/`replaced` reasons + `document_retired` audit),
  and `replace` (new active row + retired old row kept in storage).
  `SupportingDocumentViewSet` gains `?include_retired=true` (lifecycle fields,
  no pagination) and `POST .../documents/{pk}/replace/` → 201
  `{document, retired_document}`, 409 `{code, detail}`
  (`application_not_editable`, `document_not_active`) for non-editable states,
  400s flattened to `{detail: <string>}`; serializer exposes lifecycle fields,
  never `file_path`. Subpath moved into `leave/views/documents.py` (re-imported
  via `leave/views/__init__.py`).
- **Backend — tracking documents block** (owner only): `TrackedDocumentSerializer`
  (`id, file_name, file_size, content_type, file_url, uploaded_at`) with a
  re-signed URL (`signed_document_url`, `ValueError` fallback to stored URL),
  prefetching active rows only (3 queries). `test_tracking_api` updated to
  `assertNumQueries(3)` + a documents-block test.
- **Backend — required-document validator** `count_supporting_documents`
  (`leave/validation/validators/documents.py`) counts status `active` only.
- **Seed.** `seed_approvals_dev` gains idempotent `_seed_documents` (refs
  `LV-<FY>-820001` correction_required w/ active + retired/replaced doc,
  `820002` draft w/ two active docs; direct model creates, no Supabase);
  smoke-tested via transactional rollback.
- **Backend tests.** New `leave/tests/test_documents.py` (30 tests): editable
  status matrix, draft vs correction semantics (hard delete + `document_removed`
  vs retire + `document_retired`/`replaced_by`, storage kept), validation
  (required/size/content-type/sanitization), 409 codes, serializer contract,
  audit rows, auth (foreign → 404, anon → 401), required-doc counting.
  `legacy.py` updated (409 on submitted upload; size mock path
  `leave.documents.services.MAX_DOCUMENT_SIZE`). Full suite **604 tests OK**,
  `manage.py check` clean.
- **Frontend — proxies + client.** Documents GET proxies thread
  `?include_retired=true`; new replace proxy route (multipart passthrough).
  `lib/leave-api.ts`: `SupportingDocument` drops `file_path`, gains
  `status/retired_at/retire_reason/retired_by/replaced_by`;
  `listDocuments`/`deleteDocument`/`replaceDocument`;
  `DOCUMENT_ERRORS` + `documentError()` surfacing backend `detail`/`code`.
  `lib/audit.ts` drops `file_path`. `SupportingDocumentsUploader` takes
  `editable?`/`canReplace?` (replaces `disabled`), confirms removals, shows
  per-row Replace on corrections with a "returned for correction … previous
  version stays in your history" hint, and refetches the server list after
  upload/remove/replace. `LeaveApplicationForm` passes `editable`/`canReplace`
  from status + mode and shows a generalized "Application No Longer Editable"
  notice for submitted/approved/rejected/cancelled.
- **Frontend — tracking card.** New `components/tracking/supporting-documents-
  card.tsx` renders the payload `documents` block with Open buttons, fetches
  `listDocuments(id, { includeRetired: true })` on mount for a collapsible
  "Archived (N)" section (replaced rows keep Open, removed rows don't, styled
  per spec), an empty state, and an error line; mounted in `TrackingView` when
  the payload has a `documents` block. `lib/tracking/types.ts` gains
  `TrackingDocument` + `documents?`; all 9 fixtures updated (2 carry a document).
- **Frontend tests.** `supporting-documents-uploader` rewritten (mocks upload/
  delete/replace/list + `documentError` mapping), `tracking-view` gains a
  "Supporting documents" describe (archive fetch runs on mount), and
  `leave-application-form` asserts the read-only notice for all four terminal
  statuses plus the correction path staying editable with Replace. Full run:
  **49 files / 296 tests green**, `tsc --noEmit -p tsconfig.test.json`, and
  `npm run lint` clean.

## Completed (Unit 20)

- **Spec.** `context/specs/20-hr-to-employee-data-integration.md` — decisions
  D1–D10. Boundary (D2): rules provider only; tracking + workflow provider
  swaps stay Unit 21. Schema (D3): add only `EmployeeProfile.gender` +
  `LeaveRule.eligibility_rules` (JSON list of `{"type","params"}`; free-text
  `eligibility` stays the human description). No FY/holiday seed (D5) — Unit 5
  forbids invented LUANAR dates; HR configures via the existing UI.
- **Schema.** `users.EmployeeProfile.Gender` (`M`/`F` TextChoices) + `gender`
  CharField (`users/0004_employeeprofile_gender`); `leave.LeaveRule.
  eligibility_rules` JSONField (`leave/0011_leaverule_eligibility_rules`).
  Serializers: `EmployeeSerializer` + `LeaveRuleSerializer` gain the fields
  in audit snapshots. Services: `financial_year_label(year)` and
  `resolved_annual_entitlement(grade, as_of=None)` in `leave/services/`.
- **Provider.** `leave/providers/database.py::DatabaseRulesProvider` now the
  `LEAVE_RULES_PROVIDER` (`config/settings/base.py`). Implements all five
  protocol methods against the HR tables: `get_employee_for_user` (blank
  grade/appointment → `None`, `department_id=None`), `get_leave_type_rules`
  (via `resolve_leave_rule`; units derived by code, working-days for `annual`
  else calendar-days; `eligibility` from JSON; not-yet-effective rule →
  `None`), `get_financial_year_for` (label derived D6), `get_public_holidays`
  (range only), `get_available_balance` (entitlement + `LeaveBalanceTransaction`
  restorations − deductions for the FY, clamped ≥ 0).
- **Seeds.** `seed_dev_users` gains `gender` on the 7 profiles and per-type
  `eligibility_rules`/`min_notice_days`/`requires_supporting_document`
  (LeaveRule now `update_or_create` so previously-seeded DBs pick up the new
  fields idempotently); annual keeps a 5-working-day notice. `seed_approvals_dev`
  already raised `CommandError` when no active FY (spec D5) — no change.
- **Employee summary endpoint.** `GET /api/v1/leave/me/summary/`
  (`leave/views/me.py::LeaveSummaryView`, IsAuthenticated) →
  `{profile, entitlement, financial_year, available_balance}`; every value
  degrades to `None` when HR config is missing so the dashboard renders an
  honest empty state.
- **Tests.** `leave/tests/test_database_provider.py` — 19 tests across all 5
  provider methods (units, eligibility parsing, FY label/containment, holiday
  range, ledger-net balance scoped to FY + clamped, profile/grade/appointment
  missing) and the summary endpoint (401, no-profile degradation, full HR
  record). Full backend suite **623 tests OK**, `manage.py check` clean.
- **Frontend.** `lib/leave-summary.ts` (`LeaveSummary` types +
  `getLeaveSummary()` via `apiClient`); `app/(dashboard)/dashboard/page.tsx`
  now shows the live Available Balance (plus FY label, and a grade ·
  department record line) instead of the hard-coded `"21"`. Frontend suite
  unchanged at 296 tests; dashboard has no existing test asserting the
  placeholder.

## Completed (Unit 15)

- **Backend.** New `leave/tracking/` package: Django-free contract dataclasses
  in `contracts.py` (`WorkflowTracking`, `TrackedStage`, `TrackedEvent`,
  `TrackedApprover`, `TrackedOutcome`, `ResubmissionInfo`), `provider.py`
  (ABC `TrackingProvider` + `get_tracking_provider()` dotted-path factory,
  driven by the `LEAVE_TRACKING_PROVIDER` setting), and `fixture_provider.py`
  (loads `tracking/fixtures/assignments.json` + `scenarios/*.json`; unknown
  references fall back to `pending_first_stage`; no DB access). `services.py`
  exposes `get_application_tracking(user, application_id)` — owner-only,
  returns 404 for foreign/unknown applications (never 403) and 409
  `application_not_submitted` for drafts — backed by read-only serializers and
  `ApplicationTrackingView` at `GET /api/v1/leave-applications/{id}/tracking/`
  (GET only; `+00:00` timestamps normalized to `Z`). Wired into
  `leave/urls.py`. `seed_tracking_scenarios` command (DEBUG-only guard,
  idempotent, fast-forwards `ReferenceSequence` to allocate
  `LV-2026-27-900001`..`900008` and rewrites `assignments.json`).
- **Backend tests.** 4 suites / 28 tests (`test_tracking_api`, `_scenarios`,
  `_provider`, `_seed`): owner 200 with full payload + `assertNumQueries(1)`,
  non-owner/HR/supervisor 404, anonymous 401, draft 409, non-GET 405, all 8
  scenarios + fallback + delegate + `can_resubmit` rules, setting-driven
  provider swap, seed idempotency and sequence forward. Full `leave.tests`
  suite green and `manage.py check` clean.
- **Frontend.** Route `app/(dashboard)/applications/[id]/page.tsx` + proxy
  `app/api/leave/leave-applications/[id]/tracking/route.ts`;
  `lib/tracking/` (`types.ts`, `service.ts` returning ok/not_found/
  not_submitted/error results, `format.ts` — `en-GB` + `Africa/Blantyre`,
  `labels.ts` the sole enum→icon/color/copy map, so no component hardcodes a
  role or stage count); `components/tracking/` (`TrackingView` +
  header/badge/status card/stepper/stage item/outcome panel/resubmission
  note/timeline/skeleton/error) with `__fixtures__/*.json` mirroring the
  backend scenarios. "Track this application" link added to the submission
  confirmation. Responsive layout: mobile attention-then-stepper, desktop
  stepper 2/3 + attention 1/3; light-only theme using existing tokens; exactly
  one `aria-current="step"`; unknown event types render "Workflow update".
- **Frontend tests.** 3 suites / 41 tests (`tracking-view`, `tracking-format`,
  `tracking-service`). `npm test`: 31 files / 180 tests green; `tsc --noEmit`,
  `npm run lint`, and `npm run build` all clean.
- **Reconciliation.** The "My applications" destination (sidebar + "View my
  applications" + tracking back-link, `/dashboard/leave/drafts`) now lists
  **every** application — draft, submitted, approved, rejected,
  correction_required and cancelled — via `ApplicationsList`/`ApplicationCard`,
  which replaced the drafts-only `DraftsList`/`DraftCard` (2026-09-25 defect
  fix: submitted applications were invisible after submission). Draft rows keep
  Edit/Review/Delete; every non-draft row links to the tracker at
  `/applications/{id}`.

## Completed

### HR track (Units 2–11) — merged via `feature/hr-track`

- Unit 11: HR Finalized Leave + Audit View
  - Spec: `context/specs/11-hr-finalized-leave-audit-view-spec.md` (drafted,
    decisions approved: audit only existing actions — deferring approval/cancel/
    correction/document-history to Units 16–19/24; Unit 9 committed to
    `development` before the feature branch was cut; the `audit` app owns both
    new endpoints; finalized-leave shows `submitted` only, 404 on draft ids)
  - `audit/models.py`: `AuditEntry` (actor FK, `Action` choices
    created/updated/approved/rejected/cancelled/reassigned/submitted,
    `target_type`/`target_id`/`target_summary`, `detail` JSON, `reason`,
    `created_at`; `Meta.ordering = ["-created_at"]`; index
    `auditentry_target_idx` on `(target_type, target_id)`); migration
    `0001_initial` created and applied
  - `audit/services.py`: `record_audit` (None-safe `current_actor`, `_jsonable`
    normalization — PostgreSQL/psycopg3 can't serialize nested `date`/`UUID` so
    dates→isoformat and UUID→str recursively), `changed_fields` building
    `{"before","after"}` of only-changed fields (before null on create)
  - `audit/serializers.py`: `AuditedModelSerializer` base (create/update +
    explicit `_record_audit`), `AuditEntrySerializer` (read-only, `actor_name`),
    `HRLeaveApplicationSerializer` (rolls up PendingApplicationSerializer +
    SupportingDocumentSerializer + ReassignmentSerializer + oldest-first
    `audit_entries`; lazy imports inside `to_representation` to avoid the
    audit↔workflows import cycle)
  - Wiring (explicit `record_audit`, same `transaction.atomic()` as the action,
    NO Django signals, drafts/documents not audited, Django admin not audited —
    documented boundary, `LeaveApplication` only has draft/submitted):
    users `EmployeeSerializer` (create/update); leave GradeEntitlement,
    LeaveType, LeaveRule, FinancialYear, PublicHoliday serializers;
    workflows `WorkflowSerializer` (stages in the snapshot; `update` bypasses
    the base via `serializers.ModelSerializer.update(self, instance,
    validated_data)` so replacement stages are present for the after-snapshot)
    + delegation approve/reject/cancel + `reassign_application`; documents
    `LeaveDocumentTemplateView.patch`; leave `LeaveApplicationViewSet.submit`
  - `audit/views.py` + `audit/urls.py`: `AuditEntryViewSet` +
    `FinalizedLeaveViewSet` (read-only, `IsHRRole`; filters action/
    target_type/target_id/actor; finalized-leave `submitted` only,
    `?employee=` search, 404 on draft) at `/api/v1/audit-entries/` +
    `/api/v1/finalized-leave/`; `AuditEntryAdmin` view-only
  - Backend: 265 → 299 tests (34 new in `audit`) passing; existing suites
    green after wiring (users+documents 50, leave 146, workflows 131)
  - Frontend: `lib/audit.ts` read client; `AuditEntriesTable` /
    `FinalizedLeaveTable` / `ApplicationHistoryView` (+ shared `audit-meta`);
    pages `/dashboard/hr-admin/audit` (finalized leave + administrative history
    with action/target filters) and `/dashboard/hr-admin/audit/applications/[id]`
    (summary, documents, reassignment history, audit timeline); sidebar "Audit
    View" item (lucide `History`) + HR index card; `npm test` (136), `npm run
    lint`, and `npm run build` pass
  - Root `README.md` API table: `/api/v1/audit-entries/` +
    `/api/v1/finalized-leave/` rows added

- Unit 9: HR Emergency Reassignment
  - Spec: `context/specs/09-hr-emergency-reassignment-spec.md` (drafted, decisions
    approved: `pending` = a `submitted` application (the only truthful definition
    before routing); a nullable `current_approver` FK on `LeaveApplication` is the
    Unit 21 "who must act now" spine with `Reassignment` rows as the history —
    both additive, HR-only, and cross-track (merges after the Unit 13 model; the
    FK is *not* added to `LeaveApplicationSerializer` so the Unit 13 contract is
    preserved); validation reuses `workflows.services.is_approver_user`; no
    delegation consultation here — `active_delegation_for` routing is Unit 21;
    no notifications/audit here)
  - `leave/models.py`: `LeaveApplication.current_approver` FK (SET_NULL, null,
    blank, `related_name="applications_assigned"`); migration `0005` via
    `makemigrations leave`
  - `workflows/models.py`: `Reassignment` model (`application` FK
    `leave.LeaveApplication`, `from_approver`/`to_approver`/`decided_by` FKs,
    mandatory `reason`, `created_at`; `Meta.ordering = ["-created_at"]`;
    `__str__` `Reassignment({ref} → {to_approver})`); migration `0004`
  - `workflows/services.py`: `reassign_application(...)` validates the shared
    rules (submitted status, active approver-role `to_approver`, differs from
    the current approver when set and from the applicant, trimmed mandatory
    `reason`) then atomically writes the `Reassignment` row
    (`from_approver` = previous `current_approver`) and sets
    `application.current_approver`; raises `ReassignmentError(field, message)`
  - `ReassignmentSerializer` (writable `application`/`to_approver`, read-only
    history/names, `reason` trimmed on write) + `PendingApplicationSerializer`
    (`to_representation`) + `ReassignmentViewSet` at `/api/v1/reassignments/`
    (HR-only list/create/retrieve + `pending/` action queueing submitted apps
    newest-first, `?application=` filter), SimpleRouter basename `reassignment`
  - Django admin: `ReassignmentAdmin` view-only inspector
  - Backend: `workflows` suite 131 tests (97 existing + 34 new) passing via
    `uv run manage.py test workflows`, then the full suite via `--noinput`;
    `manage.py check` clean; migrations applied
  - Frontend: `lib/reassignments.ts` + `lib/reassignments-client.ts` split,
    proxy handlers `app/api/hr/reassignments/route.ts` + `pending/route.ts`,
    `PendingApplicationsTable` / `ReassignmentTable` / `ReassignmentForm`,
    pages `/dashboard/hr-admin/reassignments` (+ `new?application=<uuid>`),
    sidebar "Reassignments" item (lucide `ArrowLeftRight`), HR index card;
    `npm test` (124), `npm run lint`, and `npm run build` pass
  - Root `README.md` API table: `/api/v1/reassignments/` rows added

- Unit 10: HR Approved Leave Document Template
  - Spec: `context/specs/10-hr-approved-leave-document-template-spec.md`
    (drafted, decisions approved: one official template as a singleton in the
    `documents` app; branding is header *text* (no logo upload while file
    storage is TBD); the template stores a fixed data-field catalog where HR
    controls label/inclusion/order but never values; singleton `APIView` with
    HR-only GET/PATCH; defaults materialize on first access; preview is a
    client-side presentation mock — the authoritative render with real
    application data is Unit 23)
  - `LeaveDocumentTemplate` singleton model in `documents` (`title`, `header`,
    `intro`, `closing`, `footer` text; ordered `fields` JSON `{key,label}`;
    ordered `signature_areas` JSON `{label}`; timestamps); migration
    `0001_initial`
  - `documents/services.py`: authoritative `FIELD_CATALOG` of `{key,label,sample}`
    (reference, employee_name, employee_grade, designation, department,
    leave_type, start_date, end_date, working_days, request_reason) +
    `ALLOWED_FIELD_KEYS`, `DEFAULT_FIELDS`/`DEFAULT_*` config, and
    `get_template()` (`get_or_create` singleton default)
  - `LeaveDocumentTemplateSerializer` validates non-blank title, bounded text,
    catalog keys, unique field keys, non-blank labels, non-empty `fields`, and
    the signature-area limit; values are never accepted or stored; exposes
    read-only `available_fields` (the catalog) so the frontend doesn't duplicate
    keys/labels/samples
  - `LeaveDocumentTemplateView` (GET/PATCH singleton) with
    `IsAuthenticated, IsHRRole`; `documents/urls.py` routed from
    `config/urls.py` at `/api/v1/leave-document-template/`
  - Django admin: fully view-only inspector (`LeaveDocumentTemplateAdmin`) — all
    fields read-only, no add/change/delete
  - Seed unchanged — the default template materializes on first API access
  - Backend: 265 tests passing; `uv run manage.py test --noinput` OK (~571 s)
  - Frontend: `LeaveDocumentTemplateEditor` + `DocumentTemplatePreview` under
    `/dashboard/hr-admin/leave-document-template`; `npm test` (109), `npm run
    lint`, and `npm run build` pass
  - Root `README.md` API table: `/api/v1/leave-document-template/` GET/PATCH rows
    added

- Unit 8: HR Delegation Management
  - Spec: `context/specs/08-hr-delegation-management-spec.md` (drafted, decisions
    approved: delegation is person-based (approver `User` → delegate `User`, not
    stage-based), delegate required at approval (HR confirms or substitutes the
    nomination), `active_delegation_for` is the Unit 21 routing boundary, the
    approver request *form* is a later-track unit, no notifications/audit here)
  - `Delegation` model in `workflows`; migration `0003_delegation`
  - `workflows/services.py`: `is_approver_user`, `resolve_delegate_user`,
    `open_request_exists`, `effective_end`, `find_conflicting_delegation`
    (reuses `leave.services.date_ranges_overlap`, open-ended = `date.max`),
    `active_delegation_for` (Unit 21 boundary), `require_decision_reason`, and
    `approve_delegation`/`reject_delegation`/`cancel_delegation` shared by
    serializer/actions/admin with `transaction.atomic()` and
    `DelegationActionError(field, message)`
  - `DelegationSerializer` + `DelegationActionSerializer`; `DelegationViewSet`
    at `/api/v1/delegations/` (HR-only list/retrieve/approve/reject/cancel,
    create open to approvers via `IsApproverRoleOrHR`; `state=`/`approver=`
    filters), SimpleRouter basename `delegation`
  - Django admin: `DelegationAdmin` view-only inspector
  - Backend: 241 tests passing; frontend: 94 tests passing; `npm run lint` and
    `npm run build` pass
  - Root `README.md` API table rows added

- Unit 7: HR Workflow Activation & Scheduling
  - `Workflow` gains `effective_from`, `is_active`, derived `state`
    (`draft`/`scheduled`/`active`/`inactive`), `scope` tuple helper; migration
    `0002_workflow_effective_from_workflow_is_active`
  - `workflows/services.py`: `scopes_overlap`, `missing_approver_roles`,
    `find_conflicting_workflow`, `validate_workflow_for_activation` returning
    `ActivationIssue(field, message)` records
  - `WorkflowSerializer` validates activation/scheduling; Django admin guards
  - Backend: 192 tests passing; frontend: 73 tests passing; lint/build pass

- Unit 6: HR Workflow Builder
  - Spec: `context/specs/06-hr-workflow-builder-spec.md` (decisions approved:
    role-based stages, nothing seeded, scope is category + department)
  - `workflows` app models: `Workflow`, `WorkflowStage`; migration `0001_initial`
  - `workflows/services.py`: `StageSequenceError` + `normalize_stage_sequence`
  - `WorkflowSerializer` (nested writable stages) + `WorkflowViewSet` at
    `/api/v1/workflows/` (no delete, HR-only)
  - Django admin registration with form-set guards
  - Backend: 171 tests passing; frontend: 68 tests passing; lint/build pass

- Unit 5: HR Financial Year and Calendar Configuration (COMPLETE)
  - Spec: `context/specs/05-hr-financial-year-calendar-spec.md` (decisions:
    explicit `is_active` flag with exactly one active period; nothing seeded;
    single "Calendar" page)
  - `FinancialYear` + `PublicHoliday` models; migration
    `0003_financialyear_publicholiday`
  - `leave/services.py`: `date_ranges_overlap`, `find_overlapping_financial_year`,
    `financial_year_for_date`, `active_financial_year`, `public_holidays_between`
  - `FinancialYearViewSet` + `PublicHolidayViewSet` at `/api/v1/financial-years/`
    and `/api/v1/public-holidays/` (no delete, HR-only, `year=YYYY` filter)
  - Django admin with form guards; Backend: 144 tests passing; frontend: 55
    tests passing; smoke tested through the proxy

- Unit 4: HR Leave Type and Rule Management
  - Spec: `context/specs/04-hr-leave-type-rule-spec.md` (approved)
  - `LeaveType` + `LeaveRule` models; `code = slugify(name)` when blank;
    migration `0002_leavetype_leaverule`
  - `leave/services.py`: `normalize_leave_code` + `resolve_leave_rule(...)`
  - `LeaveTypeViewSet` + `LeaveRuleViewSet` at `/api/v1/leave-types/` and
    `/api/v1/leave-rules/` (no delete, HR-only, `leave_type=`/`effective=` filters)
  - `_seed_default_leave_types` seeds annual → 30, maternity → 90, paternity →
    10, compassionate → 5 idempotently
  - Backend: 99 tests passing; frontend: 39 tests passing; smoke tested

- Unit 3: HR Grade and Annual Entitlement Configuration
  - Spec: `context/specs/03-hr-grade-entitlement-spec.md` (approved)
  - `GradeEntitlement` model; initial migration
  - `leave/services.py`: `resolve_grade_entitlement` + helpers
  - `GradeEntitlementViewSet` at `/api/v1/entitlements/` (no delete, HR-only,
    `resolve` action); Django admin overlap guard
  - `seed_dev_users` seeds 3 default bands idempotently
  - Backend: 60 tests passing; frontend: entitlements pages + datalist-grade
    EmployeeForm (20 frontend tests)

- Unit 2: HR Employee Directory
  - Spec: `context/specs/02-hr-employee-directory-spec.md` (approved)
  - `EmployeeProfile` model, `IsHRRole` permission, `EmployeeViewSet` at
    `/api/v1/employees/` (search/ordering, no delete); Django admin
  - Backend: 26 tests passing; frontend: employee list/new/edit pages under
    `/dashboard/hr-admin/employees`; smoke tested
  - Role-assignment wiring fix (correction inside Unit 2): `role` is writable
    on `EmployeeSerializer` create/update via `ChoiceField(choices=User.Role.choices)`,
    defaults to `employee` when omitted/blank, is included in the audit
    snapshot (role changes record before/after), and is rendered as a Role
    select on the shared employee form with a `UserRole` type in
    `frontend/lib/employees.ts`. Spec §API contract and serializer notes
    updated; backend + frontend tests extended (no migration; no new files
    beyond tests).

- Unit 1: Project Foundation and Development Contract
  - Repository structure with development branch
  - Backend: Django 6.1, DRF, JWT auth, custom User model with roles
  - Frontend: Next.js 16, Tailwind CSS v4, design tokens, dashboard shell
  - Auth: Cookie-based JWT proxy via Next.js Route Handlers
  - Django-Q2 background tasks (ORM broker using Postgres, no Redis)
  - PostgreSQL database with migrations
  - Seed command creates 7 test users (one per role)
  - Backend tests (7 tests passing)
  - Frontend tests (originally 4, now 6 passing)
  - Root README with setup instructions

- Unit 1 review fixes
  - Stat-card icon styling uses a static Tailwind class map
  - Sign-out wired into the dashboard header via `/api/auth/logout`
  - Removed the dark-mode toggle and `.dark` token overrides (light-only theme)
  - Added `frontend/components/ui/` and root `storage/` placeholder dirs
  - Strong development `SECRET_KEY`; `User` admin registration
  - `RefreshView` uses SimpleJWT's `TokenRefreshView`; login rate-limited (10/min)
  - Sidebar selection derives from the current route

### Employee + Approver track (Unit 13) — merged via `origin/development`

- Unit 13: Leave Application and Drafts
  - Backend: `LeaveApplication` + `SupportingDocument` + `ReferenceSequence`
    models (merged into migrations `0004_referencesequence_leaveapplication_and_more`)
  - Backend: Working-days stub (`calculate_working_days`, weekend exclusion
    only; real holiday/calendar logic stays a TODO — the HR track's Unit 5
    calendar/financial-year services provide the boundary)
  - Backend: Supabase storage service (upload/delete, signed URLs)
  - Backend: Serializers, `IsOwner` permission, DRF `ModelViewSet`
  - Backend: Leave app URL routing via DRF `DefaultRouter`
  - Backend: preview-days endpoint for live working-day calculation
  - Backend: submit endpoint with `LUANAR-{YYYY}-{5-digit}` reference numbers
    and submit validation (leave_type, dates, reason required)
  - Backend: Immutability enforcement (submitted apps cannot be edited/deleted)
  - Backend: Supabase settings in settings.py (`SUPABASE_URL`,
    `SUPABASE_SERVICE_KEY`, `SUPABASE_BUCKET`)
  - Frontend: Leave pages (new, edit, review, drafts) under `/dashboard/leave/`;
    `LeaveApplicationForm` with autosave, `SupportingDocumentsUploader`
    (react-dropzone), `DraftCard`, `ReviewSummary`, `WorkingDaysPreview`;
    route-handler proxies; `useLeaveApplications`/`useAutosaveDraft` hooks
  - Frontend: dashbboard shell sidebar links updated (My Applications →
    `/dashboard/leave/drafts`, New Application → `/dashboard/leave/new`)
  - Both suites green after merge (see Session Notes); TypeScript clean, build
    succeeds
  - LeaveType FK is a soft reference (`PositiveIntegerField`) — the real FK to
    the HR track's `LeaveType` is a documented integration TODO
  - Reference number format: `LUANAR-{YYYY}-{5-digit sequence}`

### Integration (merge of `feature/hr-track` + Unit 13)

- `backend/leave/services.py` became package `backend/leave/services/` (our
  domain logic moved to `services/__init__.py`) so both `from .services import
  normalize_grade, ...` and `from .services.storage import ...` /
  `from .services.working_days import ...` resolve
- `backend/leave/views.py`, `serializers.py`, `urls.py`, `tests.py`,
  `models.py`: merged to expose both HR admin endpoints and
  `/api/v1/leave-applications/` (+ supporting documents) on the same routers
- Migration reconciliation (Option B): HR migrations `0001-0003` kept; their
  three models in new `leave/0004_*`. **Other developer: `uv run manage.py
  migrate leave zero && uv run manage.py migrate` is required on any local DB
  that previously applied their `leave/0001_initial`**
- `dashboard-shell.tsx` merged: our `currentPath`-based selection + HR admin
  sub-menu retained; links point at the real `/dashboard/leave/*` routes;
  `Calendar` icon added

## Completed (Unit 14)

- **Backend.** `providers/` package (base dataclasses + `RulesProvider`
  protocol + `FixtureRulesProvider` placeholder, `get_provider()`/
  `get_today()`), `validation/` package (`types.py`, `working_days.py`,
  `pipeline.py` with the ordered `CHECK_ORDER`, 10 validators incl.
  `preconditions`), models/migration `0006` (LeaveApplication
  `working_days`/`calendar_days`/`financial_year_label`/`rules_snapshot`,
  ReferenceSequence reshaped to `financial_year_label`/`last_value`,
  `0001` audit app/`AuditEvent`), services (`submission`, `references`,
  `workflow_gate` stub), `leave_application_submitted` signal + audit recording,
  `validate/` and `submit/` endpoints (`views/validation.py`, explicit routes).
  `manage.py check` and `makemigrations --check` clean.
- **Backend tests.** `leave/tests.py` → `leave/tests/` package (`legacy.py`
  kept, 4 superseded submit tests removed) + `stubs.py` (explicit-data
  `StubRulesProvider`, fixed `today=2026-09-21`) + 6 new suites
  (`test_working_days`, `test_validators`, `test_pipeline`, `test_references`,
  `test_submission`, `test_api` incl. a `TransactionTestCase` concurrency race).
  `Ran 142 tests ... OK` for `leave.tests`.
- **Frontend.** `lib/leave-validation.ts` (error-code union + `SubmitError` +
  `validateLeave`/`submitApplication`), `/api/leave/validate/` proxy,
  `useLeaveValidation` (400ms debounce, AbortController), review + submitted
  screens (`ReviewSummaryClient`, `SubmittedClient`), `validation-panel`,
  `balance-card`, `leave-review-summary`, `submission-confirmation`,
  `LeaveApplicationForm` inline validation (working-days preview +
  per-field errors), submit outcomes per spec (200/422-focus/409/network).
  `npm test` 28 files / 139 tests green, `tsc --noEmit`, `npm run lint` and
  `npm run build` all pass.
- **Docs.** `backend/docs/leave-validation.md` (pipeline order + error codes),
  `backend/docs/leave-rules-provider-contract.md` (Unit 20 handoff mapping).

## Next Up

- **Unit 26 is committed as `4352a69` on `feature/hr-track`**, and it carried
  Unit 21's outstanding provider work with it. The tree is clean. The build
  plan is exhausted: Units 1–25 are all implemented, verified
  and committed, including Unit 23b (the document half split out of Unit 23).
  Unit 26 came from a feature request rather than the plan. There is no
  queued next unit; the next step is a planning decision.
- **Candidates, in the order the work would be worth doing:**
  1. **Unit 23b D12 carry-over** — document invalidation when a leave is
     later cancelled (today the document deliberately stays as the historical
     record of what was approved), and carry-forward of an unused annual
     balance. Both were explicitly deferred, not forgotten.
  2. **DOCX output** — needs `python-docx`; deferred with the PDF build.
  3. **A release/hardening pass** — the feature work is done, so this is the
     point where a review pass over the whole track earns its cost.
- **Unit 24 — Complete Audit and Historical Integrity (implemented 2026-09-25;
  committed as `d4860f3`).** Spec
  `context/specs/24-audit-and-historical-integrity-spec.md` — decisions D1–D10,
  approved before Phase 2. Phase-1 verification against the real code reshaped
  this unit into a **hardening** unit: the build plan's audit-wiring goal is
  *already satisfied* by Units 9–23 (all twelve operations write an audit entry
  from inside the owning transaction, asserted by
  `audit/tests.py::AuditWiringTests`), and workflow history is already safe
  because `ApplicationStage` materializes the chain with no FK to `Workflow`.
  Two real gaps closed:
  - **Gap A — append-only `AuditEntry`.** `backend/audit/models.py` gained
    `AuditEntryLockedError`, `AuditEntryQuerySet` (rejects queryset
    `update`/`delete`), `AuditEntryManager`, and instance `save()`/`delete()`
    guards — mirroring `ApprovalDecision` / `NotificationOutbox` / the balance
    ledger. The HTTP + admin surfaces were already sealed; only the ORM was open.
    No migration (managers aren't serialized unless `use_in_migrations`).
  - **Gap B — per-cycle history.** `ApplicationRevision.save()` no longer raises
    on creation (it now permits insert and rejects mutation, per
    `ApplicationRevisionLockedError`), a QuerySet/Manager blocks bulk
    update/delete, and `record_revision()` in
    `leave/services/submission.py` writes one immutable row per submit/resubmit
    cycle inside the existing atomic block (with a `changed_fields` diff against
    the prior cycle and the active-document list). `rules_snapshot` is still
    overwritten in place per cycle and still drives `finalise.py` (D8), but the
    cycle-1 context an approver saw is no longer lost, closing the §14 breach.
  Recon-flagged defects in earlier units (edit/resubmit API + frontend contract,
  final-approval/deduction pairing, audit-JSON `CombinedExpression`,
  `row_version`) remain explicitly **out of scope** (D10).
  **Verification:** `check` clean; `makemigrations --check` clean (both
  deliverables are manager-only); full suite **651 tests OK** (636 + 15 new;
  the trailing `destroy_test_db` OperationalError is the known test-DB
  teardown/lock issue, after all tests pass).
- **Unit 23 — Final Approval, Balance, and Document Generation (implemented,
  committed as `eb7361d`).** Spec
  `context/specs/23-final-approval-balance-and-document-spec.md` revised during
  the Phase-1 review on 2026-09-25: decisions D1–D8 rewritten against the
  actual code (deduction inside `decide()`'s transaction from `rules_snapshot`;
  no ledger row for special leave; restoration stays owned by Unit 18;
  template-populated ReportLab PDF via `approved/{application_id}/` in storage;
  owner/HR/approver read-only access; Django-Q2 render task; no new tracking
  event). **DOCX was deferred (PDF only, no `python-docx`).** Unit 22 wired the
  real bus this unit's finalisation consumer also uses.

## Completed (Unit 25) — End-to-End System (2026-09-25)

- **Spec.** `context/specs/25-end-to-end-system-spec.md` — decisions D1–D11,
  approved as specced for Phase 2. Developer decisions at Phase 1: Unit 25 = E2E
  + **wiring fixes only**, with the approved-document build split out to Unit
  23b; and **no new third-party dependency** in this unit. No dependency was
  added.
- **The E2E suite (D9/D10).** New cross-app package `backend/tests/`
  (`__init__.py` + `test_end_to_end.py`, 10 tests). It drives the **real**
  services — including the real `DatabaseWorkflowProvider` over an
  HR-configured chain created through the audited `/api/v1/workflows/`
  endpoint — and only touches HTTP where the contract is the thing under test
  (HR's finalized read, the employee's own list, the D7 edit guard).
  `EndToEndBase` keeps Unit 22's real email consumer on the bus and adds an
  event observer, and wraps every decision in
  `captureOnCommitCallbacks(execute=True)` so the on-commit path actually runs.
  Journeys: full approval (config → submit → 4 stages → **exactly one
  deduction** → 4 outbox emails → cycle-1 revision → employee sees `approved` →
  HR sees the finalized record), repeated-finalization idempotency, the ledger
  `IntegrityError` guard, one-email-per-decision, rejection, correction →
  edit → resubmit (cycle-2 revision with a `changes` diff, cycle 1 untouched) →
  single deduction, submitted-is-not-editable, cancellation restoring the
  deduction to a net zero, delegation, and reassignment.
- **The wiring fixes the E2E exposed.**
  - **D4 — the deduction is now wired.** `workflows/services.py::decide` calls
    `record_deduction(app)` immediately after the final `app.save()`, inside
    the same `transaction.atomic()`, so a ledger failure rolls the approval
    back. Pinned by `FinalisationWiringTests.test_deduction_failure_rolls_the_approval_back`.
  - **D3 — DB-level idempotency.** `LeaveBalanceTransaction.Meta.constraints`
    gained the partial `UniqueConstraint(fields=["application"],
    condition=Q(type="deduction"))` named `one_deduction_per_application` —
    the constraint `record_deduction`'s docstring already relied on. Migration
    `leave/0012_leavebalancetransaction_one_deduction_per_application`. This
    was the unit's **only** schema change.
  - **D5 — event kind.** The condition was `after_status != SUBMITTED`, which
    filed a rejection as `application_finalised`; it is now
    `after_status == LeaveApplication.Status.APPROVED`.
  - **D6 — HR's finalized view.** `FinalizedLeaveViewSet` now filters
    `status__in=[SUBMITTED, APPROVED]` via a `VISIBLE_STATUSES` tuple in both
    `get_queryset` and `get_object`; rejected/cancelled stay hidden (the audit
    log covers those, Unit 24 D1).
  - **D7 — the edit guard.** `LeaveApplicationViewSet.EDITABLE_STATUSES` is
    `(DRAFT, CORRECTION_REQUIRED)`; every other status is still 400. This
    matches what `LeaveApplicationForm.tsx:20,249-250` already assumed.
  - **D8 — frontend type.** `LeaveApplication.status` in
    `frontend/lib/leave-api.ts` widened from `"draft" | "submitted"` to all six
    backend statuses. No exhaustive switch consumed the narrow union, so this
    is type-only.
- **`finalise.py` had to be made importable (enabling, not scope creep).** It was
  dead code that could not even be imported: it imported a non-existent
  `leave.services.exceptions` module whose three exception classes were defined
  **nowhere in the repo**. Three defects were fixed to wire D4:
  (a) created `backend/leave/services/exceptions.py` with
  `LeaveTypeNotResolvableError` / `ApplicationFinalisationError` /
  `DeductionAlreadyRecordedError`; (b) `record_deduction` filtered
  `leave_type_id=...`, but `LeaveBalanceTransaction.leave_type` is a plain
  `PositiveIntegerField`, not a FK — corrected to `leave_type=...` (matching
  Unit 18's `record_restoration`); (c) `record_deduction` **raised** for any
  non-deducting leave type, which would have made compassionate/maternity/
  paternity leave impossible to approve. It now returns `None` for a clean
  "does not consume the annual balance" answer, and still raises
  `LeaveTypeNotResolvableError` only when the snapshot records no decision at
  all — which is what that exception's own docstring describes. Without (c) the
  D4 wiring would have broken three leave types.
  `finalise_approved_application` (the document half) was deliberately left
  unwired in this unit — that is Unit 23b, which has since wired it.
- **Two widely-reported claims were disproved and deliberately not "fixed":**
  the resubmission `CombinedExpression` JSON crash (Django 6.1 refreshes
  F-expression attributes after save; pinned by
  `test_resubmission_audit_detail_is_json_safe`) and cancellation restoring
  without a deduction (`_restore_balance` guards on
  `get_deduction() is None`). The E2E cancellation journey now proves the
  restoration round-trip instead.
- **Verification:** `check` clean; `makemigrations --check` clean; full backend
  suite **673 tests OK** (652 + 21). Frontend: `npm test` **296 tests / 49 files
  OK**, `npm run typecheck:test` clean, `npm run lint` clean. The trailing
  `destroy_test_db` `OperationalError` is the known environmental teardown issue
  and appears after `OK`.

## Completed (Unit 23b) — Approved Leave Document (2026-09-25)

- **Spec.** `context/specs/23b-approved-leave-document-spec.md` — decisions
  D1–D12, approved as specced. Developer decision at Phase 1: **`reportlab`
  approved** as the only new dependency. The spec carries three **amendments
  recorded during implementation** (D7 application-keyed URLs, D9 nullable audit
  actor + the choices-migration correction, D10 the real employee surface).
- **D1 — dependency.** `reportlab>=4.4.0` in `backend/pyproject.toml`; `uv sync`
  resolved **reportlab 5.0.1** (with `pillow` and `charset-normalizer`
  transitively). No `python-docx`, no `pypdf`, no font package.
- **D2 — `ApprovedLeaveDocument`** (`documents/models.py`, migration
  `documents/0002_approvedleavedocument.py`): OneToOne `application` (PROTECT),
  `pending`/`ready`/`failed`, file metadata, `approved_on`, `rendered_at`,
  `error_message`, a state-consistency `CheckConstraint`, a QuerySet/Manager
  that refuse to delete a `ready` row, and a sanitizing `error_message` writer.
  **The immutability guard compares against the *persisted* row, not the
  in-memory one** — a guard reading the instance's own `status` rejected
  `mark_ready`'s own transition, because `mark_ready` assigns
  `status = READY` before saving. FK fields compare by `attname` so an untouched
  relation is not reported as changed.
- **D3 — `LeaveApplication.approved_on`**, set once inside `decide()`'s
  existing save so it cannot disagree with the status. Migration
  `leave/0013_leaveapplication_approved_on.py`.
- **D4 — one mapping, never a sample.** `documents/services.py::document_values`
  resolves every catalog key from the persisted application; `FIELD_CATALOG`
  gains `approved_on` and `remaining_balance` (additive, so
  `ALLOWED_FIELD_KEYS` accepts them with no serializer change). `remaining_balance`
  is read from the ledger-backed provider **at render time**, i.e. after the
  deduction has committed. A key with no value renders blank — a test pins that
  a missing `EmployeeProfile` yields `""` rather than the catalog's sample.
- **D5/D11 — render.** `documents/tasks.py::render_approved_document(document_id)`
  renders with ReportLab, uploads, and flips `pending → ready`; a failure flips
  to `failed` with a **sanitized** single-line message and is logged in full
  server-side, never raised into the caller and never rolling back the approval.
  Idempotent: a `ready` row is a no-op, so a re-render cannot overwrite the
  artifact of what was approved. `enqueue_approved_document_render` registers on
  `transaction.on_commit` and swallows an unreachable broker (the approval has
  already committed). The renderer walks `template.fields`, resolves each key
  through `document_values`, escapes all text (an injected `<script>` does not
  reach the PDF), and caps signatures at `MAX_SIGNATURE_AREAS`.
- **D6 — storage.** `upload_document` gained an optional `prefix` (defaulting to
  `leave-documents/`, so Unit 18/19 callers are untouched) plus a bytes-friendly
  `upload_bytes(...)` for the in-memory PDF, both writing `approved/{application_id}/`.
- **D7 — access.** GET-only, keyed by application id: owner, `IsHRRole` HR, and
  an assigned approver via `get_view_access`. A stranger gets **404** with a body
  identical to an unknown id's; a non-HR on the HR route gets 403. `pending` and
  `failed` report `available: false` with **no signed URL minted**, so the client
  can say "being prepared" from one response.
- **D8 — one entry point.** `decide()` now calls `finalise_approved_application`,
  which calls `record_deduction` and creates the `pending` row in the same
  transaction; the duplicated `consume_deduction_decision` branch was removed and
  the enqueue is skipped once the row is `ready`.
- **D9 — audit.** `DOCUMENT_GENERATED` / `DOCUMENT_FAILED` target
  `TargetType.APPLICATION`. **`AuditEntry.actor` became nullable** (migration
  `audit/0008_...`) because a background render has no human actor and
  attributing it to a person would be a fabrication in the authoritative log;
  `AuditEntrySerializer` renders a null actor as `System`, and the two HR audit
  tables fall back to `System` rather than `#null`.
- **D10 — frontend.** `lib/documents/approved.ts` + two Next proxy routes +
  `components/documents/approved-document-card.tsx`, a **link to the signed URL
  only** (no viewer, iframe or proxy). Mounted on the employee tracking view
  (`/dashboard/applications/[id]`, gated on `status === "approved"` — the
  `leave/[id]/submitted/` page is a pre-approval confirmation that redirects
  away for any other status), the HR audit detail, and the approver detail.
  `pending`/`failed` render an inline status, never a broken link; a 404 renders
  nothing. The HR detail payload gained `status` so the affordance can be gated.
- **Tests.** `documents/tests.py` +37 (storage prefixes, value mapping and the
  no-sample-leak guarantee, PDF totality/escaping, task idempotency and failure
  isolation, sanitized errors, enqueue-on-commit, the three-reader access
  matrix, immutability). `backend/tests/test_end_to_end.py` +7 —
  `ApprovedDocumentJourneyTests` drives the real decision service, the real
  orchestrator and the real task, stubbing only Supabase and the broker.
- **Verification:** `check` clean; `makemigrations --check` clean; full backend
  suite **717 tests OK** (710 + 7; documents app 61). Frontend: `npm test`
  **302 tests / 50 files OK** (296 + 6), `npm run typecheck:test` clean,
  `npm run lint` clean. The trailing `destroy_test_db` `OperationalError` is
  the known environmental teardown issue.
- **D12 — still out of scope**, deliberately: cancellation invalidation (the
  document stays as the historical record of what was approved), carry-forward,
  DOCX, email attachment, version history, `pypdf` read-back.

## Completed (Unit 22) — Email Notifications (2026-09-25)

- **Spec.** `context/specs/22-email-notifications-spec.md` — decisions D1–D8
  (no new tracking event; the real approval-event bus lands here; employee/HR
  recipients from the persisted stage chain; append-only `NotificationOutbox`
  reusing the `pending/sent/failed` vocabulary; `EMAIL_BACKEND=console` +
  `mail.outbox` assertion; audit vocabulary untouched; attachments/digests/HTML
  out of scope).
- **Real bus.** `workflows/events.py` keeps `ApprovalEvent` + the
  `DECISION_RECORDED`/`APPLICATION_FINALISED` constants verbatim and turns the
  Unit-16 no-op sink into a real registry: private `_consumers` list,
  `register_consumer` (duplicate registration is a loud `ValueError`),
  `emit_approval_event` now dispatches to every consumer in registration order
  with per-consumer failure isolation (a raising consumer can never abort its
  siblings or the commit), and a test-only `_reset_consumers_for_tests`.
  `decide()` already emitted via `transaction.on_commit` — no change needed
  there; the bus now just has something to dispatch to.
- **Append-only outbox.** `notifications/models.py::NotificationOutbox` (one row
  per `application`/`kind`/`submission_cycle`/`role_label`, enforced by a unique
  constraint + `get_or_create`): `NotificationOutboxQuerySet` rejects
  queryset-wide `update`/`delete` (`NotificationOutboxLockedError`), mirroring
  the balance-ledger discipline; state moves `pending → sent|failed` only via
  `mark_sent()`/`mark_failed()` (both idempotent). Migration
  `notifications/0001_initial`.
- **Email consumer.** `notifications/services.py::send_decision_email` — the
  first real bus consumer. Composes subject/body from the persisted
  `ApprovalEvent` atoms (no templating engine), resolves recipients per the D4
  matrix (`DECISION_RECORDED` → owner; `APPLICATION_FINALISED` → owner +
  finalising approver, resolved from the persisted user id — never a role
  scrape), `get_or_create`s the outbox row (idempotent on re-emit), sends via
  `django.core.mail.send_mail`, and records `sent`/`failed`. Send failures are
  isolated: the error is stored on the outbox row and swallowed, never aborting
  the decision commit. Unresolvable recipient raises
  `NotificationSeamUnresolvableError`. Registered on the bus via
  `NotificationsConfig.ready()`.
- **Tests.** `notifications/tests.py::DecisionEmailBusTest` — 7 tests over the
  real bus + console outbox: one sent row per decision to the owner,
  double-emit idempotency (1 row, 1 email), append-only queryset lock,
  `APPLICATION_FINALISED` owner+approver recipient matrix, send-failure →
  `failed`, a raising sibling consumer does not abort the commit, and the
  unresolvable-recipient error.
- **Verification.** `manage.py check` clean; `makemigrations --check` clean; full
  backend suite `uv run manage.py test` **636 tests OK** (629 before + 7 new),
  no regressions from wiring the real bus into `decide()`. No backend linter is
  configured (`manage.py check` + `test` are the gates). Frontend untouched.


## Completed (Unit 21)

- **Spec.** `context/specs/21-workflow-to-approver-integration.md` — decisions
  D1–D15 (locked in the spec; tracker entry written retrospectively from the
  verified implementation).
- **Workflow routing.** `workflows/providers.py::DatabaseWorkflowProvider` +
  `resolve_applicable_workflow` (scope precedence category/department →
  category → department → any; tie → earliest `effective_from`; active +
  effective only); `config/settings/base.py` now sets
  `WORKFLOW_PROVIDER = "workflows.providers.DatabaseWorkflowProvider"`.
  `workflow_gate.check_workflow_ready` is no longer a stub — a submission with
  no applicable workflow or a stage with no active approver fails with
  `workflow_unavailable` (422, never a 500).
- **The spine.** `LeaveApplication.current_approver` is the authoritative "who
  must act now" fact. `decide()` advances it to the next stage's approver on
  approve; resubmission points it back at the returning stage's configured
  approver; reassignment/delegation resolve at query time via
  `acting_approver_id` (delegation → delegate while active, then reassignment
  assignee, then the stored approver; single-level, no cascade). Routing
  consumers (`ApprovalListAPIView` pending tab, `ApprovalsCapabilitiesView`,
  `get_decision_authority`, `get_view_access`) all use acting-approver
  resolution.
- **Resubmission.** New `POST /api/v1/leave-applications/{id}/resubmit/`
  (`leave/views/resubmit.py`): rejected/correction_required → submitted, cycle
  increments, returning stage re-opened in place, `current_approver` = the
  stage's configured approver, same reference, validation re-run, audit
  `application_resubmitted`.
- **Tracking.** `leave/tracking/database_provider.py::DatabaseTrackingProvider`
  builds `WorkflowTracking` from real `ApplicationStage`/`ApprovalDecision`/
  `Reassignment`/`CancellationRequest` rows (status, stages, events, outcomes,
  resubmission, cancellation blocks) with the D11/D12/Unit 18 contract intact.
  `config/settings/base.py` now sets
  `LEAVE_TRACKING_PROVIDER = "leave.tracking.database_provider.DatabaseTrackingProvider"`.
- **Fixture removal.** `leave/tracking/fixture_provider.py`, `leave/tracking/
  fixtures/`, and `seed_tracking_scenarios.py` are deleted (working tree);
  frontend tracking fixtures (provider-independent component-test data) stay.
- **Seeds.** `seed_approvals_dev` builds idempotent `Workflow`/`WorkflowStage`
  rows (academic → hod/dean/registrar/dvc; administration → supervisor/hod/
  registrar/dvc) so its scenarios route through the real provider.
- **Tests.** New `workflows/tests_routing.py` + reworked `tests_approvals.py`
  (DatabaseWorkflowProvider resolution, acting-approver routing, spine
  advance), `leave/tests/test_resubmission.py`, and real-row tracking tests.
  Verified 2026-09-25: `uv run manage.py test workflows.tests_routing
  leave.tests.test_tracking_api leave.tests.test_resubmission` →
  **32 tests OK**; `manage.py check` clean.
- **Docs.** `backend/docs/workflow-to-approver-routing.md` (spine D2, acting
  approver D3, workflow resolution D5, resubmit contract D9, tracking event
  vocabulary D11).
- **Status:** implemented and now committed on `feature/hr-track` as part of
  `4352a69` (Unit 21 predates this tracker entry; Unit 26's rewrite of the
  approver resolution landed in the same commit).

## Hardening pass — feature/hr-track review (2026-09-21, complete)

A review-and-fix sweep of the merged HR + employee tracks (`feature/hr-track`,
7 commits) addressed the flagged findings before returning to feature work:

1. **Backend audit endpoint centralization** (`db45686`): the S3-style audit
   sub-endpoints (`/audits/`, `/documents/`, `/users/`) under the leave/
   workflows routers were moved into `audit/urls.py` as a single `AuditEntryViewSet`
   router, now the only definition; the old stray routes were dropped.
   `backend/audit/migrations/0003_alter_auditentry_target_type.py` verifies the
   enum change is metadata-only. Documents-suite seeded references were updated.
2. **Silent-errors + submitted-app guard** (`8b77d1b`): `DraftCard` surfaces
   delete errors; `SupportingDocumentsUploader` surfaces upload/removal errors
   (incl. the no-draft-created case); `LeaveApplicationForm` surfaces load/create
   errors and renders a read-only "Application Already Submitted" state linking to
   the review page instead of an editable form.
3. **Accessibility** (`c22f0bc`): proper `htmlFor`/`id` on LeaveTypeSelect,
   DateRangeFields, and the leave reason; `aria-label`s on icon-only buttons
   (delete draft, remove document, sidebar toggle, notifications bell).
4. **Tooling** (`c142211`): added `tsconfig.test.json` + `npm run typecheck:test`
   (caught 2 real type errors in test fixtures); replaced the `as readonly string[]`
   cast in `delegations-client.ts` with an `APPROVER_ROLE_CODE_SET: ReadonlySet<string>`;
   fixed the Tailwind v4 `components.json` `"config"` ref; setup.ts imports
   `@testing-library/jest-dom/vitest`.
5. **Next.js middleware migration** (`7d5687e`): `frontend/middleware.ts` was
   renamed (git mv) to `frontend/proxy.ts` and `middleware` → `proxy`; build
   confirms Next 16.3.5 recognizes `ƒ Proxy (Middleware)`.
6. **DECISION A — centralized apiFetch** (`6259ada`): all ~21 HR/leave route
   handlers previously forwarded the 15-minute access token unsupported (session
   death on expiry despite a valid 1-day refresh cookie). New
   `app/api/_lib/api-fetch.ts` reads cookies, refreshes up front when only the
   refresh cookie exists, forwards to Django, and on a 401 refreshes once and
   retries, re-setting the renewed `access_token` cookie on the returned
   `NextResponse`; `app/api/leave/_lib/proxy.ts` delegates to it. Added
   `tests/api-fetch.test.ts` (forward, 401 → refresh+retry+set-cookie, refresh
   failure → 401, no-token → 401, 204, refresh-up-front paths).
7. **DECISION B — employee leave-type catalog** (`f37cd38`): removed the
   hard-coded `getLeaveTypes()` mock whose paternity (14) / compassionate (7)
   contradicted the seeded rules (10 / 5). New read-only
   `GET /api/v1/employee/leave-types/` (`EmployeeLeaveTypeViewSet`, any
   authenticated role, unpaginated) serializes each LeaveType with
   `max_duration_days` / `requires_supporting_document` resolved from the
   currently effective `LeaveRule` (`resolve_leave_rule`). Frontend proxies via
   `app/api/leave/leave-types/` and maps snake_case → the `LeaveType` shape.

Verification for the whole pass: backend `leave` (161), `workflows` +
`users` + `documents` (191) tests all OK; frontend 155 tests pass, `tsc
--noEmit` + `typecheck:test` clean, eslint clean, `npm run build` succeeds.
No pushes; all 7 commits remain on `feature/hr-track` for a later merge.

## Open Questions

- None yet.

## Architecture Decisions

- Python 3.13, Django 6.1, Node 22+, Next.js 16 (App Router, TypeScript)
- `uv` for backend, `npm` for frontend
- Postgres runs natively (no Docker) and also serves as the Django-Q2 broker
- JWT stored as httpOnly cookies via Next.js Route Handlers
- DRF snake_case JSON kept end-to-end
- Light-only theme (no dark mode toggle)
- Inter loaded via next/font/google
- lucide-react as the only icon source
- Tailwind CSS v4 with CSS-based configuration (no tailwind.config.ts)
- Grade entitlement rules must not overlap any existing rule, regardless of
  `effective_from`. Entitlement changes are edits to the existing rule, not
  superseding same-range rules. `effective_from` still governs resolution and
  future-dated rules for previously unmapped bands remain supported.
- `LeaveApplication.leave_type` stays a soft `PositiveIntegerField` for now —
  wiring the real FK to `LeaveType` (and enforcing a rule exists) is a
  documented integration TODO
- `calculate_working_days` excludes weekends only; connecting it to the Unit 5
  public-holiday / financial-year services (and the "intervention days" notion)
  is a documented TODO
- Document storage uses Supabase with signed URLs (configurable expiry) —
  requires `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_BUCKET`

## Session Notes

- **Unit 22 implemented + verified (2026-09-25):** The approval bus is now real
  and carries the first consumer. Decisions worth flagging: (1) `get_connection()`
  returns a backend instance that has **no** `.send_mail()` method — the first
  draft called `connection.send_mail(...)`, every send raised, the consumer
  swallowed it as `failed`, and `mail.outbox` stayed empty. The fix is the
  module-level `django.core.mail.send_mail(...)`; the test mocks
  `notifications.services.send_mail`. (2) The outbox is unique per
  `(application, kind, submission_cycle, role_label)`, not `(application, kind)`
  — the persisted `role_label` matters because the same application reaches
  `DECISION_RECORDED` at each stage role, and a `(application, kind)`-only key
  would have let a second stage email match the first row and silently drop
  legitimate per-stage notifications. (3) A raising consumer is swallowed by
  `emit_approval_event` and cannot abort siblings or the commit; its own
  `failed` state is the durable record. (4) `NotificationsConfig.ready()`
  registers the consumer, so registration is idempotent-by-module-load and
  `register_consumer` still raises loudly on a true duplicate. (5) The test DB
  kept getting "accessed by other users" — sessions owned by roles the `luanar`
  role cannot see; `DROP DATABASE ... WITH (FORCE)` from `luanar` clears it, and
  forcing the drop + run in one chained command avoids the reconnect window.
  Next build: **Unit 24 — Complete Audit and Historical Integrity** (per the
  build plan; an earlier note in this session mislabelled it "Delegation
  Routing" — corrected).

- **Unit 21 verified complete + Unit 23 spec revised (2026-09-25):** A Phase-1
  review confirmed Unit 21 is fully implemented on `feature/hr-track`. It was
  **not committed at the time of that review** (working-tree only — `git
  status` showed the provider swaps,
  `resubmit.py`, `tests_routing.py`, the tracking-fixture deletions, and
  `docs/workflow-to-approver-routing.md` as modified/untracked/deleted; 32
  routing/tracking/resubmit tests pass). All of it is now committed in
  `4352a69`, where Unit 26 replaced the approver-resolution half with
  team-scoped `resolve_stage_approver`. The Unit 23 spec draft was rewritten:
  the old draft referenced non-existent machinery (`create_ledger_row`, a
  `submission_cycle` ledger column, `leave_type_consumes_annual_entitlement()`,
  `is_finalised`, `workflows.events._consumers`), wrong HR units (12 = employee
  dashboard; 8–9 = delegation/reassignment), and a nonexistent "fixture
  balance/document provider" to delete. Decisions D1–D8 now match the real
  code: deduction inline in `decide()`'s transaction decided from
  `rules_snapshot["leave_type"]["deducts_annual_balance"]`; `LedgerBalanceProvider.
  get_deduction` derives days/FY from the application record; storage
  `upload_document` hard-wires `leave-documents/{id}/` and needs a minimal
  extension for the `approved/` prefix; `reportlab` is not installed. DOCX
  deferred. Awaiting developer approval before implementation.

- **Unit 20 complete (2026-09-24):** HR-to-Employee Data Integration landed.
  The default `LEAVE_RULES_PROVIDER` is now `DatabaseRulesProvider`; the
  dashboard's hard-coded `"21"` balance is replaced by the live summary
  endpoint. Two gotchas worth flagging: (1) the DB-backed `get_employee_for_user`
  treats a blank grade as "no employee" (the precondition
  `EMPLOYEE_PROFILE_MISSING`), while a missing `appointment_date` maps through
  as `None` so the rule that needs it reports `ELIGIBILITY_DATA_MISSING`
  instead; `department_id` stays
  `None` because `EmployeeProfile.department` is free text; (2) `seed_dev_users`
  LeaveRule seeding switched from `get_or_create` to `update_or_create` so
  databases seeded before Unit 20 pick up `gender`/`eligibility_rules`
  idempotently on re-run. Swapping the settings caused zero existing-test
  regressions (validation/pipeline suites inject `StubRulesProvider`; tracking
  fixtures bypass the provider entirely). Next build: **Unit 21 — Workflow-to-
  Approver Integration** (swap `LEAVE_TRACKING_PROVIDER` + `WORKFLOW_PROVIDER`
  to real workflow-backed implementations on the fixture spine).
- **Unit 18 complete (2026-09-24):** Leave Cancellation landed on the Unit 15/16
  spine. Decisions worth flagging: employee UI (eligibility + card) drives off a
  purpose-built `cancellation-eligibility` endpoint rather than deriving from the
  tracking payload; the approver cancellation list is paginated with the Unit 16
  `_Paginator`; tracking fixtures cast via `as unknown` needed a gate so
  `CancellationSection` only mounts when the Unit 18 fields are present
  (otherwise every legacy tracking test would fire unmocked fetches). RTL's
  `getByText` only matches direct text nodes, so assertions spanning nested
  `<span>`/`<time>` reuse the repo's normalized-`textContent` matcher. The
  `pendingEligibilityRef` in the dialog hit the `react-hooks/refs` lint rule
  (ref value read during render) and was converted to state. Committed as
  `8a48f21` on `feature/hr-track`. Next build: **Unit 19 — Supporting Document
  Lifecycle** (spec to be drafted).
- **Unit 11 complete (2026-09-21):** HR Finalized Leave + Audit View landed on
  `feature/hr-unit-11` (cut from `development` after Unit 9's commit `2a63f55`).
  Audit is explicit (`record_audit` in the same transaction as the action) — no
  Django signals, a deliberate boundary: drafts/document uploads and Django
  admin mutations are not audited. Key bug caught by tests: psycopg3 serializes
  JSON with plain `json.dumps`, so nested `date`/`UUID` values explode — the
  `_jsonable` normalizer in `audit/services.py` fixes it. Cross-suite backend
  runs combined exceed the 10-minute tool timeout, so the full suite must be
  split per-app in the background (users+documents ~84s/50, leave ~250s/146,
  workflows ~427s/131, audit ~81s/34). (Superseded 2026-09-21: `config.settings.test`
  now swaps in a fast password hasher, so `uv run manage.py test` runs the full
  389-test suite in ~7s — no per-app splitting needed.) Frontend: 136 tests, lint, and build
  clean. Not yet committed — commit the feature work on `feature/hr-unit-11`
  and merge to `development` when the other developer's track is ready.
- **Unit 15 complete (2026-09-21):** read-only, owner-only tracking endpoint +
  `/applications/[id]` page behind a swappable fixture provider (contracts live
  in the Django-free `contracts.py`; `LEAVE_TRACKING_PROVIDER` setting drives
  `get_tracking_provider()`). Decisions recorded: 404 not 403 for anyone who
  isn't the owner; drafts 409 `application_not_submitted`; resubmission retains
  the reference number; unknown event types render "Workflow update" rather than
  breaking; delegated reviews show "Acting for X". Reconciliation: the Unit 13
  drafts list shows drafts only, so the submission-confirmation "Track this
  application" link is the in-app entry point — no tracker link on the drafts
  list. Fixed during verification: frontend `tsc` caught a missing
  `TrackingStage` import in `labels.ts` and over-broad union narrowing in
  `TrackingView` (error/non-owner branches); testing-library string matchers
  can't see text inside nested `<strong>`/`<time>`, so those assertions use a
  normalized-textContent matcher.
- **Unit 9 complete (2026-09-18):** HR Emergency Reassignment landed. Big
  decisions recorded: `pending` = `submitted`; the `current_approver` spine +
  `Reassignment` history (cross-track — the nullable FK merges after the Unit 13
  model and is excluded from `LeaveApplicationSerializer`); HR-only everywhere;
  `is_approver_user` reuse; no consultation of `active_delegation_for` (Unit 21
  boundary); no notifications/audit app. Fixed during test-writing: the
  `ReassignmentSerializer` initially listed `reason` in `read_only_fields`, which
  silently dropped the POST reason and would 400 every create — moved it out so
  `validate_reason` trims and `create` submits it. `workflows` suite: 131 tests
  green (97 existing + 34 new) and the full backend suite stays green; frontend
  124 tests (109 + 15 new), lint + build clean. Misc: `uv run manage.py test
  workflows` is slow to boot the test DB (~90–150 s per class group) so the
  earlier 120 s default timeout underran — long timeouts required.
- **Sidebar active-state fix (2026-09-18):** the sidebar highlight was stale
  because every dashboard page mounted its own `DashboardShell` on the page
  root, so the active link reverted to the initial page. Root cause fixed by
  hoisting the shell into a persistent `app/(dashboard)/layout.tsx` (auth
  guard + `<DashboardShell user={user}>{children}</DashboardShell>`). The 5
  shell-wrapped pages (`dashboard`, `leave/new`, `leave/drafts`,
  `leave/[id]/edit`, `leave/[id]/review`) now return plain content; HR admin
  pages keep their own role checks and now inherit the shell from the layout
  (they previously rendered without sidebar/header). `usePathname()`-derived
  highlight now tracks the real route across client-side navigations. Full
  frontend verification: 109 tests pass, `tsc --noEmit` clean, lint clean,
  `npm run build` succeeds.
- **Sidebar performance pass (2026-09-18):** optimized `dashboard-shell.tsx`
  before resuming Unit 9. Replaced both `transition-all` utilities with
  property-scoped transitions (nav `transition-[width]`, nav items
  `transition-colors`) and aligned durations with `ui-context.md` (300ms →
  200ms) so the collapse/expand animation no longer transitions layout-affecting
  properties speculatively. Memoized the presentational subcomponents
  (`Sidebar`, `Option`, `TitleSection`, `ToggleClose`, `Header`) and wrapped the
  logout handler in `useCallback`, so toggling the sidebar no longer re-renders
  the header or unrelated shell nodes. Full frontend verification: 109 tests
  pass, `tsc --noEmit` clean, `npm run lint` clean, `npm run build` succeeds.
- **Integration merge (2026-09-18):** merged `feature/hr-track` (Units 2–10 +
  review fixes) and `origin/development` (Unit 13) onto `development`.
  Conflicts resolved in leave models/serializers/views/urls/tests, the
  `services` module→package refactor, migration reconciliation (keep `0001-0003`
  HR, add `0004` for their models), the dashboard shell, and this tracker. Both
  backend and frontend suites must be run after this merge (see below).
- Unit 9 deferred (2026-09-17, developer decision): HR Emergency Reassignment
  operates on pending applications, which did not exist until Units 13+ landed.
  **Resume Unit 9 now** that Unit 13 is merged.
- Unit 10 backend suites green (265 tests) and frontend suites green (109
  tests); `uv run manage.py test --noinput` (~571 s) and `npm test`, plus
  `npm run lint` and `npm run build`
- Unit 10 review follow-up (2026-09-17): removed an unused backend `preview/`
  endpoint plus `render_preview`/`SAMPLE_VALUES`; moved the field catalog to a
  single backend definition exposed as read-only `available_fields`; tightened
  the admin to fully view-only
- Unit 10 notes (2026-09-17): the template is a configuration singleton, not a
  document; logo/branding is header *text* only; `fields`/`signature_areas` are
  validated JSON columns; `get_or_create(pk=1)` materializes the default
- Unit 8 backend suites green (241 tests) and frontend suites green (94 tests)
- Unit 8 notes (2026-09-17): delegation is person-based; delegate confirmed at
  approval; delegations view-only in admin; no seeding
- Unit 7 backend suites green (192 tests) and frontend suites green (73 tests)
  - DRF normalizes serializer error dict values into lists — the activation
    missing-role error is `{"detail": [...]}`
  - PATCH replaces stages wholesale (Unit 6 contract)
- Unit 6 backend suites green (171 tests) and frontend suites green (68 tests)
  - DRF `APIClient` without `format="json"` sends multipart and silently drops
    nested list-of-dicts
  - Client-safe libs must not import `next/headers` transitively (`next build`
    fails)
- Unit 5 backend suites green (144 tests) and frontend suites green (55 tests);
  public-holiday integration with an external source remains TBD
- Unit 4 backend suites green (99 tests) and frontend suites green (39 tests);
  `LeaveType.code` is stable/unique, edited not deleted
- Unit 3 backend suites green (60 tests) and frontend suites green (21 tests);
  flow-review fixes moved the admin overlap guard into a form `clean()`
- Unit 2 backend suites green (26 tests) and frontend suites green (10 tests)
- `ALTER USER luanar CREATEDB` applied on this machine (2026-09-17), so
  `uv run manage.py test` runs directly
- Development users seeded with password `testpass123`; optional dev superuser
  `admin@test.luanar` / `testpass123`
- Background tasks use Django-Q2 with Postgres as ORM broker (no Redis)
- Unit 13 implementation complete
  - Backend: 28 leave tests pass (working days, models, API, permissions, documents)
  - Backend: 7 existing user tests still pass
  - Frontend: 4 existing tests still pass, TypeScript clean, build succeeds
  - Frontend dependencies added: date-fns, react-dropzone
  - Backend dependencies added: supabase
  - Migration for their models landed as `leave/0004_*` (post-reconciliation);
    other developer must run `migrate leave zero && migrate` before continuing
  - Document storage uses Supabase — requires env vars `SUPABASE_URL`,
    `SUPABASE_SERVICE_KEY`, `SUPABASE_BUCKET`
- Unit 13 code review (Standards + Spec axes)
  - Fixed bare `except: pass` in views.py (now `logger.exception`)
  - Removed dead `perform_update` code
  - Fixed `useState` side-effect in `ReviewSummary.tsx` → `useEffect`
  - Removed scope-creep head-level Edit link in `ReviewSummary`
  - Switched storage.py from `get_public_url` to signed URLs (configurable expiry)
  - Fixed `DraftCard` showing raw leave type ID → resolved name via `useEffect`
- Unit 13 upload fixes: dropzone renders unconditionally; `onEnsureDraft` for
  lazy draft creation; removed `router.replace` from `ensureDraftCreated`
- Supabase credentials configured in `.env`, bucket `leave-documents` created
- Sidebar active state derives from `usePathname()` (both tracks agreed)

## Completed (Unit 16) — Approver Review and Decision (2026-09-23, complete)

Backend (`backend/workflows/`):

- **Models/migrations.** `WorkflowDefinition` (name, code, keys, ordered roles),
  `WorkflowAssignment` (definition + per-application group keys in `keys` JSON),
  `ApplicationStage` (application, workflow, role, order, `status`, assigned
  approver, `decision_version`; unique partial `pending_stage_per_application`),
  `ApprovalDecision` (immutable: application, stage FK, action
  `approve|reject|return_for_correction`, optional comment, `submission_cycle`,
  `stage_version`, `decided_by`, `decided_at`; no admin registration — decisions
  are append-only, protected by `ApprovalDecisionLockedError`).
  Migrations: `workflows/0006_*`, `leave/0007_*`,
  `users/0003_alter_employeeprofile_faculty.py`, `audit/0004_*`.
- **Provider.** `WORKFLOW_PROVIDER = "workflows.providers.FixtureWorkflowProvider"`
  (`workflows/providers.py`, ABC + settings-driven factory) reading fixture
  chains from `workflows/fixtures/workflow_fixtures.json`:
  supervisor→hod→registrar→dvc, hod→dean→registrar→dvc (Faculty-level anchor
  chains for `academic`), etc. `WorkflowAssignmentError` → `workflow_unavailable`.
- **Decision pipeline.** `workflows/services.py::decide(user, application, action,
  comment)` runs one transaction with `select_for_update` on the pending stage;
  raises `ApprovalStageChangedError` (409), `ApprovalNotAllowedError` (403, with
  `reason`: `application_closed|already_decided|not_current_stage`),
  `ApprovalValidationError` (400). Non-final approved stage saves before the next
  pending stage is created; `decision_version` is NOT bumped on handoff.
  `emit_approval_event` no-op dispatcher (`workflows/events.py`) hooks:
  `decision_recorded`, `stage_assigned`, `application_finalised`. No balance
  deduction, no email (per spec boundaries).
- **Policies.** `workflows/policies.py` — `can_view`/`can_decide` per role with
  `Authority` dataclass (supervisor: all; hod/dean: conditionally all;
  registrar/dvc: current financial year).
- **API.** `approval_payloads.py` (list item, review payload — includes
  `can_decide`, `decision_restriction`, `application.submission_cycle`,
  per-stage `decision_version`, current-stage `is_final` + `next_role_label`),
  `approval_views.py` (`ApprovalListView`, `ApprovalDetailView`,
  `ApprovalDecisionView`, `ApprovalDocumentDownloadView`,
  `ApprovalCapabilitiesView`) wired in `workflows/urls.py` at
  `/api/v1/approvals/...`. Pending list orders by `submitted_at`; decided list
  orders by subquery-annotated `last_decided` desc (`distinct()`).
  `submit_application` now assigns the workflow; history view surfaced approval/
  decision entries from the Unit 15 spine.
- **Testing/seed.** `SeedStubProviderMixin.use_stub()` in
  `backend/workflows/tests/utils.py`; status-permission poker tour covering all
  five roles; `seed_approvals_dev` command (DEBUG-only, idempotent; creates
  `science-employee@test.luanar` in Faculty of Science and 7 in-flight/done
  scenarios `LV-<fy>-800001..800007` through the real `submit`/`decide`
  services). **Workflows suite: 171 tests; full backend suite: 530 tests pass;
  `manage.py check` clean.**

Frontend (`frontend/`):

- **Proxy routes** `app/api/approvals/*` (`route.ts`, `capabilities/route.ts`,
  `[id]/route.ts`, `[id]/decision/route.ts`,
  `[id]/documents/[documentId]/download-url/route.ts`) via
  `@/app/api/_lib/api-fetch` (cookie forwarding, token refresh,
  `DJANGO_API_URL`).
- **lib/approvals/** `types.ts` (DRF-snake_case types), `service.ts`
  (typed result unions incl. `conflict`/`forbidden`/`validation` for decisions,
  capabilities, sign-url download), `labels.ts` (status/action metadata,
  restriction copy), `format.ts` (`formatDate`/`formatDateTime` re-export,
  `formatSize`), `__fixtures__/index.ts` (factory helpers for list/review/
  briefing/capabilities).
- **Components** `approvals-list` (pending/decided tabs, debounced search,
  pagination, desktop table + mobile cards, empty/error/retry states),
  `approval-detail` (review page with info/balance/leave-history/app
  documents/history cards, `DecisionPanel` with inline confirmation),
  `decision-dialog` (approve/reject/return dialog: live comment counter,
  whitespace guard, stage-version payload, conflict 409 reload banner, field
  errors, final-stage warning, success toast + callback), `badges`, `panel`,
  `approvals-nav-item` (sidebar item driven by `fetchCapabilities`, pending
  count badge `>99 → "99+"`, hidden when not an approver). Dashboard shell
  now renders `ApprovalsNavItem`.
- **Pages** `dashboard/approvals` (list) + `dashboard/approvals/[id]` (review).
  All UTC timestamps localised to `Africa/Blantyre`.
- **Verification:** 33 new tests across 5 files (service contract, list,
  detail, decision dialog, nav item) using `fireEvent` (user-event not
  installed in this repo); full frontend run **244 tests pass (44 files)**,
  `tsc --noEmit` clean on both tsconfigs, `eslint --max-warnings=0` clean.

## Completed (Unit 18) — Leave Cancellation (2026-09-24, complete)

Backend (`backend/leave/cancellations/` + `backend/workflows/`):

- **Models/migrations.** `CancellationRequest` (kind `withdrawal|approved_leave`,
  status `pending|approved|rejected`, reason, timestamps, `stage_version`,
  `application_status_at_request`, `balance_restored_days`,
  `restored_financial_year`, `employee_notification_state`) and
  `CancellationApprovalStage` (order, role, status
  `waiting|pending|approved|rejected|not_reached`, approver, decided_at,
  comment) in `leave/0010_*`; `LeaveApplication.cancelled_at` in `leave/0009_*`;
  audit `Action`/`target_type` additions in `audit/0006_*`; workflow
  `ApplicationStage` status additions in `workflows/0007_*`.
- **Services.** `leave/cancellations/services.py` withdrawal + eligible-request
  creation (448 stacking via `CancellationEligibilityPayload`), eligibility
  matrix against the Unit 16 `ApplicationStage` rows
  (`not_cancellable_status`/`leave_already_started`/`open_request_exists`/
  `no_cancellation_approvers`), and cancelled-status owner reads;
  `backend/leave/tracking/` extended additively (contracts, serializer,
  service) with `cancelled_at`, `cancellation_action`,
  `cancellation_blocked_reason`, `has_open_cancellation_request`,
  `latest_cancellation`.
- **Approver surface.** `workflows/approval_views.py` +
  `workflows/urls.py`: `CancellationListAPIView` (`?tab=pending|decided`,
  oldest-first, paginated `{tab,count,next,previous,results}` via `_Paginator`
  page_size 20 per the Unit 16 convention),
  `CancellationDetailAPIView` (404 to non-assigned viewers, includes
  `requested_by_name`), `CancellationDecisionAPIView` (approve/reject,
  reject comment required 400 `comment_required`, stage-version 409, 403
  `not_current_approver`, approve blocked when leave started). Stage chain
  supervisor→hod from `workflows/policies.py::cancellation_approval_rules` +
  `providers.py`; final approval cancels the application (status `cancelled`,
  `cancelled_at`), restores `working_days` to the FY balance, closes open
  `ApplicationStage` rows; notification state recorded (dispatch deferred).
- **Seed/tests.** `seed_approvals_dev` extended with cancellation scenarios.
  `leave.tests.test_cancellations`: **43 tests** covering the eligibility
  matrix, withdraw, open-request guard, reason validation, approver list
  tabs/pagination OK, detail visibility, decisions incl. 409/403/400 branches.
  Full backend suite **573 tests green**; `manage.py check` clean.

Frontend (`frontend/`):

- **lib/cancellations/**: `types.ts`, `labels.ts` (status/stage/kind/notification
  meta, `actionLabel`/`confirmLabel`/`blockedReasonLabel`/`consequenceLine`/
  `outcomeBanner`/`formatDayCount`), `format.ts`, `service.ts` (typed result
  unions; `action_changed` 409 carries fresh `eligibility`), `__fixtures__/`.
- **Proxy routes**: `app/api/leave/leave-applications/[id]/{cancellation-eligibility,
  cancel,cancellations}/` and `app/api/approvals/cancellations/{[requestId],…/decision}/`
  via `@/app/api/_lib/api-fetch`.
- **Employee UI** (`components/cancellations/`): two-step `cancel-application-dialog`
  (reason 10–1000 live counter + inline validation, `expected_action` mismatch →
  "Refresh and review the latest state" with fresh eligibility),
  `cancellation-stage-stepper`, `cancellation-card` (status badge, outcome
  banner with restored days/rejecting comment, notification chip, collapsible
  history), `cancellation-section` under the tracking header (button driven by
  `cancellation_action`/blocked line; refetches after every mutation — no
  optimistic updates).
- **Tracking**: `lib/tracking/types.ts` + `TrackingHeader` ("Cancellation
  requested" pill, "Cancelled on …" line) + `TrackingView` mounting
  `CancellationSection` only when Unit 18 fields are present.
- **Approver UI**: `approvals-workspace` (Applications | Cancellation requests
  segmented control), `cancellation-requests-table` (Pending / Decided by me,
  "starts in N days" → pending-orange ≤3 / red "Started", Unit 16-style
  pagination and empty/error/retry states), `cancellation-detail-panel` on
  `/approvals/[applicationId]?cancellation={requestId}` (requester, reason,
  original-leave + balance-impact cards, stage tracker, leave-started warning
  disabling Approve, `cancellation-decision-dialog` with required-on-reject
  comment and 409 → "This request changed. Refreshing…" + refetch, read-only
  "This cancellation is not with you right now." for non-current approvers).
- **Verification:** 8 new Vitest files (service contract, cancel dialog,
  section, requests table, detail panel, tracking-field additions) —
  full frontend suite **282 tests / 49 files green**, `npm run lint` clean,
  `tsc --noEmit -p tsconfig.test.json` clean, `npm run build` succeeds
  (all pages + new proxy routes compile).
- **Decisions.** Followed repo `lib/<domain>/` + `components/<domain>/`
  conventions (over the spec's `lib/services/cancellation/`); approver list
  paginated with the Unit 16 `_Paginator`; `expected_action` concurrency guard
  mirrors Unit 16's stage-version; detail panel silently renders nothing when
  `?cancellation=` does not resolve to an assigned request.
## Defect Fixes (2026-09-25, employee + approver surfaces)

- **"My applications" hid submitted applications.** The page behind the sidebar's
  "My Applications" item (`/dashboard/leave/drafts`) only fetched
  `?status=draft`, so a newly submitted application was invisible to the
  employee. `DraftsList`/`DraftCard` were replaced by `ApplicationsList`/
  `ApplicationCard`: the list now calls `getLeaveApplications()` with no status
  filter (backend already returns all owned statuses) and renders every row —
  drafts keep Edit/Review/Delete, non-drafts show a status pill, the reference
  number and a "Track this application" link to `/applications/{id}`. Verified:
  313 frontend tests (previously 302), `tsc --noEmit`, `eslint`, `next build`.
- **`<td>` inside `<a>` hydration error on the approvals table.** The desktop
  `ApprovalsTable` wrapped its `<td>` cells in a `TableLink` (`<a>`), invalid
  HTML. `approvals-list.tsx` now renders the reference link inside the first
  `<td>` (matching `FinalizedLeaveTable`) and keeps the whole row clickable via
  a stretched-link overlay (`relative` row + `after:absolute after:inset-0` on
  the link); the dead `TableLink` wrapper was removed. A regression test
  asserts `a td` and `tr > a` never appear. Verified: 314 frontend tests,
  `tsc --noEmit`, `eslint`, `next build`.

## Defect Fixes (2026-09-25, backend review payload)

- **`GET /api/v1/approvals/{id}/` → 500 `AttributeError: 'FinancialYear' object has no attribute 'label'`** (Approvals page could not open a Registrar/DVC review). `approval_payloads._leave_history_entries` used `year.label` for the financial-year-scoped leave history, but the label is a derivation, not a column (`FinancialYear` stores only `start_date`/`end_date`/`is_active`). Now uses `leave.services.financial_year_label(year)` (e.g. `2026-07-01` → `2026-27`); unchanged fallback to `application.financial_year_label`. Regression test added in `workflows/tests_approvals.ApprovalAPITests.test_detail_review_payload_with_active_financial_year`: creates an active FY, advances the spine to the Registrar stage, and asserts the detail payload returns 200 with `current_financial_year` history excluding the current application. Full backend suite: 727 tests OK (teardown `DROP DATABASE` intermittently fails due to background autovacuum sessions — pre-existing environmental quirk, not a project bug).

## Security Rule (2026-09-25, no self-approval)

- **Approvers can no longer decide on their own applications.** The single
  source of truth is `workflows.policies.get_decision_authority`, which now
  returns `Authority(False, "self_application")` whenever
  `application.employee_id == user.id` (checked before any stage logic), so the
  rule holds at every stage, across delegations, reassignments and
  resubmissions. `decide()` raises `ApprovalNotAllowedError("self_application")`
  → API `403 {error, reason: "self_application"}`; the review payload exposes
  `can_decide: false` with that reason, and the frontend decision panel shows
  "You cannot decide on your own application." (new `restrictionLabel` case in
  `frontend/lib/approvals/labels.ts`).
- **Same rule for cancellations (Unit 18).** New `SelfDecisionError` in
  `leave/cancellations/services.py` raised when the decider is the
  application's employee; `CancellationDecisionAPIView` maps it to
  `403 {code: "self_application"}`.
- Tests: service + API for self-approval (`DecisionServiceTests`,
  `ApprovalAPITests` in `workflows/tests_approvals.py`; `DecideServiceTests`
  and `ApproverCancellationApiTests` in `leave/tests/test_cancellations.py`),
  plus a frontend read-only-banner case. Full backend suite 733 tests OK,
  frontend 315 tests OK, `tsc --noEmit`, `eslint` clean.

## Defect Fix (2026-09-25, draft status crash in Leave history)

- `Cannot read properties of undefined (reading 'icon')` on the approvals
  detail page: an employee's private **draft** applications leaked into the
  "Leave history" list and emitted status `"draft"`, which had no `STATUS_META`
  entry.
- Backend fix: `workflows/approval_payloads._leave_history_entries` now
  excludes `LeaveApplication.Status.DRAFT` (drafts are in-progress and private;
  approvers should only see submitted/terminal leave records). Regression test
  `ApprovalAPITests.test_leave_history_excludes_drafts`.
- Frontend hardening: `ApprovalStatus` union + `STATUS_META` now include
  `"draft"` and `"submitted"`; `LeaveHistoryCard` and `StatusBadge` fall back to
  a neutral meta for any unknown status instead of crashing. Note: `makeReview`
  fixture was made to `structuredClone` so nested mutations no longer leak
  across tests.
- Verified: backend 734 tests OK, frontend 316 tests OK, `tsc`, `eslint`, and
  `next build` clean.

## Defect Fix (2026-09-25, approved document never rendered in development)

- **Symptom:** after the final approval, the "Approved leave document" card sat
  on "Being prepared" for ~90s and then kept showing it forever.
- **Cause 1 — the development task queue was never drained.**
  `finalise_approved_application` creates the document row `pending` and defers
  the render through `enqueue_approved_document_render` →
  `async_task(...)` on commit. `Q_CLUSTER["sync"]` defaulted to `False`, and
  development runs only two processes, so nothing ever drained the ORM broker:
  the message sat in `django_q_ormq` indefinitely and the row never left
  `pending`. Confirmed against the dev database — queued messages present,
  zero rows in `django_q_task` (i.e. no task had ever executed), no `qcluster`
  process running. The client-side 3s × 30 poll in
  `frontend/components/documents/approved-document-card.tsx` is a safety net
  for a slow render, not the bug; the render simply never started.
- **Fix (development-only):** `config/settings/development.py` now sets
  `Q_CLUSTER = {**Q_CLUSTER, "sync": True}`, so `async_task` runs the task
  in-process. The render happens on the approval's `on_commit` callback and the
  document is `ready` before the response is written, so the first poll finds
  it. The trade — the approving request waits ~1s for the PDF instead of
  returning immediately — is the right one for a one-page PDF on a dev machine.
  Production is untouched and still needs a supervised `qcluster`.
- **`config.settings.test` pins `sync` back to `False`** because that module
  imports from `development`, and the suite asserts the *enqueue* contract
  (`EnqueueTests`, and `test_approval_creates_a_pending_document_with_the_approval_stamp`
  requires a fresh approval to leave a `pending` document). Without the pin,
  every approval in the suite would render inline and that assertion could not
  hold. Confirmed the suite still enqueues rather than executes (the `Enqueued
  [luanar_leave]` log lines remain).
- **Cause 2 — still open, environmental:** `backend/.env` has no
  `SUPABASE_URL` / `SUPABASE_SERVICE_KEY`, so
  `leave.services.storage.get_supabase_client()` raises and the render records
  a failure instead of storing a PDF. The suite never caught this because every
  test stubs `get_supabase_client`. The PDF itself renders fine (~2.4 KB in
  ~1.0s); only the upload fails. **Action required from the developer:** set the
  `SUPABASE_*` variables. Documented in the README under "File Storage".
- **Recovery for the already-stuck document:** the two messages left in
  `django_q_ormq` are that render. Once credentials exist, start
  `uv run manage.py qcluster` (or run the task once) and the existing document
  completes. A `failed` row is re-renderable — the task short-circuits only on
  `ready`.
- Verified: `documents` + `tests.test_end_to_end` 78 tests OK, full backend
  suite **734 tests OK**, and a live development-settings probe confirmed the
  enqueue takes a document `pending → ready` inline (with the storage client
  stubbed) and leaves `django_q_ormq` untouched. Frontend unchanged, so no
  frontend verification was required.

## Defect Fix (2026-09-25, approver review 500 on a system-actor audit entry)

- **Symptom:** after the document render failed (missing Supabase credentials),
  `GET /api/v1/approvals/{id}/` returned **500**
  `AttributeError: 'NoneType' object has no attribute 'get_full_name'` for every
  approver of the application — the review page became permanently unopenable.
- **Cause:** `AuditEntry.actor` is nullable by design, because a system action
  is recorded with no person. Unit 23b's render task writes both
  `DOCUMENT_GENERATED` and `DOCUMENT_FAILED` with `actor=None`, but
  `workflows/approval_payloads._audit_history` resolved the display name as
  `entry.actor.get_full_name() or entry.actor.username` — dereferencing a
  nullable field unconditionally. One system audit entry therefore crashed the
  entire review payload, not just its own row. The audit app's own serializer
  already handled this correctly; the approver payload duplicated the name
  resolution and missed the null case, so the convention had drifted in two
  places.
- **Fix (single source of truth):** `SYSTEM_ACTOR_NAME` and a new
  `actor_display_name(actor)` moved to `audit/services.py` (the audit app's
  shared, non-HTTP layer). `audit.serializers.AuditEntrySerializer.get_actor_name`
  and `workflows.approval_payloads._audit_history` both resolve through it, so
  the two readers can no longer disagree. The constant is re-exported from
  `audit.serializers` so its existing import path keeps working.
- **Tests:** `ApprovalAPITests.test_detail_audit_history_survives_a_system_actor_entry`
  records a `DOCUMENT_FAILED` entry with `actor=None` on a submitted
  application and asserts the review payload returns 200, the entry reads as
  `System`, and a human entry in the same payload still reads as the person.
  Confirmed the test reproduces the original traceback when the fix is reverted.
- Verified: full backend suite **735 tests OK**, `check` clean,
  `makemigrations --check` clean, and a live probe confirmed
  `LV-2026-27-000006` (the application that 500'd) now builds its review
  payload with `('document_failed', 'System')`. Frontend contract unchanged —
  `AuditHistoryEntry.actor` was already a non-nullable `string`, and the HR views
  already rendered the same `System` fallback.

## Defect Fix (2026-09-25, `SUPABASE_URL` suffix broke all storage)

- **Symptom:** with valid Supabase credentials in place, the render still failed:
  `httpx.HTTPStatusError: 404 ... /rest/v1/storage/v1/object/leave-documents/...`,
  then `AttributeError: 'dict' object has no attribute 'text'` from inside
  `storage3`'s own error handling — a traceback that named neither the setting
  nor the bucket.
- **Cause:** `SUPABASE_URL` was set to the dashboard's "Project URL" value,
  `https://<ref>.supabase.co/rest/v1/`. `supabase-py` appends its own service
  paths, so the effective URL became `/rest/v1/storage/v1/...` and every request
  was routed to PostgREST instead of the Storage API. The project and the
  `leave-documents` bucket were both fine and untouched — confirmed by probing
  the bare URL directly (`/auth/v1/health` → 200, `/storage/v1/bucket` → lists
  the bucket).
- **Fix:** corrected `backend/.env`, plus a guard in
  `leave.services.storage.get_supabase_client` that rejects a `SUPABASE_URL`
  carrying a path and says so explicitly, converting a future copy-paste of the
  dashboard URL into an actionable error instead of a `storage3` traceback.
  Trailing-slash-free and trailing-slash bare URLs are both accepted.
- **Tests:** `SupabaseClientConfigTests` in `leave/tests/test_documents.py`
  (3 cases) covers the rejected suffixed URL, the accepted bare URL (with and
  without a trailing slash), and the pre-existing missing-credentials message.

## Test Isolation Fix (2026-09-25, suite depended on absent Supabase credentials)

- Filling in real credentials exposed **12 pre-existing tests that were green
  only because storage was unconfigured** — they reached the live Supabase API
  and failed on 400/404. They are not hermetic: they serialize documents without
  stubbing `get_supabase_client`, so they passed whenever the developer's `.env`
  had no credentials and broke as soon as it did
  (`leave.tests.test_documents`, `leave.tests.test_tracking_api`,
  `audit.tests`). One of them is even named
  `test_serialization_falls_back_to_stored_url_when_storage_unconfigured`.
- **Fix:** `config/settings/test.py` now clears `SUPABASE_URL` and
  `SUPABASE_SERVICE_KEY`. `.env` is read at import time, so without this the
  suite's behaviour depends on the developer's local environment. The storage
  paths that assert real behaviour stub the client themselves and are unaffected.
- Verified: full backend suite **738 tests OK**.

## Defect Fix (2026-09-26, storage misconfiguration 500'd the document read endpoint)

- **Symptom:** `GET /api/v1/approved-leave-documents/by-application/<uuid>/` returned
  **500** with the new `SUPABASE_URL` guard's `ValueError` in the traceback, from
  `_approved_document_payload` → `signed_document_url` → `get_supabase_client`.
- **Cause:** the signed URL is derived data layered on top of the document row,
  but `documents/views.py` was the **only** storage call site in the codebase
  without a failure fallback. The other three all degrade — `leave.serializers`
  and `leave.tracking.serializers` catch `ValueError` and return the stored
  `file_url`, and `workflows.approval_views` catches broadly. So a storage
  misconfiguration could never fail the supporting-document or tracking reads,
  yet took the approved-document read down with it.
- This was latent rather than new: the guard only converted a previously
  confusing storage3 traceback into an immediate one, and the same unhandled
  call would have surfaced any storage outage.
- **Fix:** the signing call is wrapped; on failure the reason is logged and the
  payload reports `available: False` with an empty `download_url`, while the
  status still reads `ready`. Deliberately *not* falling back to the render-time
  `file_url` the way the other three call sites do: those are best-effort
  listings, but `available` is the flag the UI keys its "Open" button off, and
  that stored URL has expired — so no button is honest, a dead link is not. The
  document's own metadata is still returned, so the page renders normally.
- **Tests:** `test_a_signing_failure_degrades_the_payload_instead_of_500ing` in
  `documents/tests.py` covers both a misconfiguration (`ValueError`) and an API
  failure (`StorageApiError`) across the employee and HR routes, and asserts the
  error is logged. Full backend suite **739 tests OK**.

## Operational Note (2026-09-26, `.env` is read once at startup)

- After correcting `SUPABASE_URL`, the still-running dev server kept serving the
  old suffixed value: settings are read at import time, so editing `.env` has no
  effect until the process restarts. This produced a confusing log where the
  guard reported a `/rest/v1/` URL that was no longer on disk. **Restart the
  Django dev server and any `qcluster` worker after changing `.env`.**

## Security (2026-09-25, service_role key committed to `backend/.env.example`)

- `backend/.env.example` was **tracked in git and contained a real Supabase
  `service_role` key**, present in at least four commits
  (`75133c2`, `66558ee`, `719efe0`, `4a08bd7`). `.gitignore` covers `.env` but
  not `.env.example`. A `service_role` key bypasses row-level security and grants
  full administrative access to the project.
- **Action required from the developer — the key must be rotated.** It is in
  history, so editing the file is not sufficient: revoke it in the Supabase
  dashboard (Settings → API Keys) and issue a new one. History rewriting (e.g.
  `git filter-repo` / BFG) is a separate decision and was deliberately not done
  unasked, since it rewrites shared history and needs a force-push.
- Removed from the working copy and replaced with a placeholder, with comments
  warning against the dashboard URL suffix, that the bucket must exist, and that
  the key belongs in `.env` only. `frontend/.env.example` was checked and holds
  no secrets.

## Business Rule Addition (2026-09-26, applicant is never the approver of record)

Units 16/21 hardening, prompted by the fact that `get_decision_authority`
refused self-approval but routing never prevented it: an employee who also
held an approver role *was* assigned their own application, and simply saw a
read-only screen with no route onward.

- **Rule.** The application starts after the applicant's *last* stage in the
  chain, and never travels back down the queue: every stage at or before that
  position is bypassed, including lower-level stages whose approver is not the
  applicant (the sole exception to invariant 12.3, now documented there). Given
  `supervisor → HOD → Registrar`, a Supervisor's application starts at the HOD,
  the HOD's starts at the Registrar — not at the Supervisor — and a Registrar's
  has no later approver. Delegation does not satisfy the rule — the *configured*
  approver is compared, not the acting one.
- **A bypassed stage confers no access.** `get_view_access` excluded only
  `waiting`, so an approver whose stage was skipped could still open the
  application by URL. `skipped` is now excluded too: the application never
  reached them, so they have nothing to decide and nothing to read.
- **Unroutable chains are refused up front.** A role resolves to exactly one
  approver (lowest-id active holder), so if there is **no stage after the
  applicant's last one**, nobody is left to sign the application off. Such a
  submission is refused with `workflow_unavailable` (422) and never leaves the
  employee. This came out of a real dev case: `registrar@test.luanar` is the only
  Registrar and Registrar is the last administration stage, so their own leave
  had no valid final approver.
- **The advance-time 409 is defence in depth, and its remedy is not a
  reassignment.** `reassign_application` only moves `current_approver` (Unit 21
  D8, spine-only), so it can never reach the blocked *later* stage — an
  application routed under the old rules, or whose workflow changed afterwards,
  has no in-product escape. The message says so instead of promising a
  reassignment that cannot work, and the approver dialog shows it as a permanent
  block with no Reload button.
- **One check.** `workflows.policies.is_self_application` (now accepting a
  `User` or a bare id) is the single authoritative predicate. `services
  .is_self_approver` delegates to it, and it backs `get_decision_authority`,
  `reassign_application` (Unit 9) and the cancellation guard (Unit 18), so the
  three inline comparisons that predated this are gone.
- **Both routing points.** `select_activatable_stage_index` resolves the chain
  at assignment (so a leading self match is bypassed before the employee ever
  sees the app), and `_next_activatable_stage` re-resolves on every advance,
  which is what protects applications submitted before this rule existed.
  No backfill or data repair: existing rows are corrected by the advance path
  when they next move.
- **New state, not a hidden one.** `ApplicationStage.Status.SKIPPED` and
  `AuditEntry.Action.STAGE_SKIPPED`; the audit detail lists the bypassed
  orders and where the application went, each tagged `applicant_is_approver` or
  `before_applicant_stage`, with the deciding approver as `actor` (or the system
  on automatic routing). Tracking reports state `skipped`
  (spec 21 D11), and both the tracking stepper and the approver timeline show
  it neutrally with the reason. The approver review payload's
  `next_role_label` now resolves the same way, so the approve dialog no longer
  advertises the applicant's own stage as "next".
- **Test double.** `StubWorkflowProvider` used to fall back to the application
  employee as the approver of unregistered roles — a configuration the product
  now rejects outright. It resolves the lowest-id active user of the role, or a
  lazily created filler approver, and `register_chain_approvers` was added for
  submission-focused tests.
- **Tests:** new `workflows/tests_self_approval.py` (29 cases: leading and
  mid-chain skips, the `supervisor → HOD → Registrar` examples for both the HOD
  and the Supervisor, a plain employee still starting at stage 1, consecutive
  skips, audit contents per stage, submission refused when nothing follows the
  applicant, the 409 defence-in-depth path with its rollback, delegation,
  reassignment, legacy-row authority, tracking and review payload) plus frontend
  cases for the skipped badge in both surfaces, a `pending_with_skipped_stage`
  tracking fixture, and the blocked-decision dialog. Two older tests in
  `workflows/tests_approvals.py` that hand-built a self stage at assignment time
  were re-pointed at the states that can still exist (a bypassed stage, and the
  runtime guard). Full backend suite **768 tests OK**; frontend **321 tests OK**,
  `tsc` and `eslint` clean.

## Business Rule Addition (2026-09-26, configured public holidays count as non-working everywhere)

Asked to confirm that public holidays set by HR actually reach the leave-day
calculations. They reached the validation pipeline but **not** the two paths
outside it, so a configured holiday could show up in one number on screen and
not the other.

- **The bug.** `leave/services/working_days.py::calculate_working_days()` was
  still the Unit-13 weekend-only stub (`TODO(unit-5)`), and it was the function
  writing `LeaveApplication.calculated_days` on every draft create/update and
  backing `POST /leave-applications/preview-days/`. The row therefore carried two
  day columns that could disagree: `working_days` (holiday-aware, frozen at
  submission) and `calculated_days` (weekends only). `LeaveReviewSummary` falls
  back to `calculated_days` when no validation result is loaded, and
  `WorkingDaysPreview` promises "Excludes weekends and public holidays" — so the
  UI could state a rule the backend was not applying.
- **One counting rule.** `calculate_working_days()` now reads holidays through
  the configured `LEAVE_RULES_PROVIDER` and delegates the counting itself to the
  pipeline's `leave/validation/working_days.count_working_days()`. The
  `holidays=` / `provider=` keyword seams keep it unit-testable, and the
  provider import is function-local because `leave.providers.database` imports
  `leave.services`. A holiday landing on a weekend is excluded once, not twice.
- **Every calculation surface is now holiday-aware:** draft `calculated_days`,
  the `preview-days` response (which also reports `holidays_excluded` so the
  number is explainable), the frozen `working_days`, `rules_snapshot["holidays"]`,
  the max-duration and balance checks, the working-day notice requirement, and
  the ledger deduction. Cancellation still mirrors the original deduction rather
  than recounting, which is correct: it restores what was charged.
- **The dev approvals seeder** now skips public holidays when picking a start
  date, so a seeded application can never begin on a day validation rejects.
- **Tests.** New `leave/tests/test_public_holiday_calculations.py` (26 cases)
  drives the **real** `PublicHoliday` table through the real
  `DatabaseRulesProvider` — no stubbed holiday source — covering the counter
  (boundaries, weekend collision, holiday-only ranges, reversed/missing), the
  preview endpoint, the draft preview agreeing with the validated count,
  submission freezing the reduced count into `working_days` and the snapshot,
  finalisation deducting the reduced days, holidays configured *after* submission
  not re-cutting the ledger, the validation payload and balance projection, a
  start date on a holiday, and a holiday inside the notice window. Full backend
  suite **794 tests OK**, `check` clean, no migration drift.
- **Still not done (unchanged, and out of scope here):** the `PublicHoliday`
  table has **no seed data** — `leave/management/` is empty and there is no
  command, fixture, or data migration, so out of the box
  `get_public_holidays()` returns `{}` and nothing changes until HR creates rows
  through the admin or `POST /api/v1/public-holidays/`. LUANAR's actual holiday
  calendar is organization-specific data, not something to invent in code;
  architecture.md still carries "Public-holiday data source and fallback | TBD".
  Also untouched: no scope/optionality/substitute-day fields on the model, no
  employee-facing holiday list (HR-only viewset), and `carry_forward_eligible`
  remains a dead flag with no carry-forward computation.

### Follow-up: setting a holiday did not reach drafts already saved

Reported as "public holidays are not working when they are set". The counting fix
above was correct, but a real draft in dev (`2026-10-13..2026-10-16`, with
`2026-10-15 Mothers' Day` configured) still showed **4** stored days where the
correct answer is **3**.

- **Cause.** `LeaveApplication.calculated_days` is denormalized and was only ever
  written by the draft create/update path, so it was as fresh as the employee's
  last *edit*. Configuring a holiday changed the answer for dates the employee had
  already chosen without touching their draft, and the stored preview — the value
  `LeaveReviewSummary` falls back to when no validation result is loaded — kept the
  pre-holiday number.
- **Fix.** `leave/holiday_refresh.py` (wired through `LeaveConfig.ready()`) has a
  `pre_save` receiver that stashes a holiday's previous date and a `post_save`
  receiver that re-counts the `draft` / `correction_required` applications whose
  range covers the old or new date. Signal receivers rather than view logic, so the
  Django admin **and** `POST /api/v1/public-holidays/` are both covered, and a
  *moved* holiday repairs the range it left as well as the one it joined. It writes
  with a queryset `update()` — the column is derived, and `LeaveApplication.save`
  carries signals the employee's own edits own.
- **Submitted and approved applications are never recounted** (invariant 12.5):
  their count was frozen at submission and their ledger already moved.
- **Tests:** 6 more cases in `leave/tests/test_public_holiday_calculations.py`
  (refresh on set, a holiday outside every draft, a moved holiday repairing both
  ranges, a submitted application staying frozen, the HR endpoint path firing it,
  and a dateless draft left alone). Full backend suite **800 tests OK**. The one
  stale dev draft was repaired and all five dev applications now agree with the
  live calendar.

---

## Delegation follow-ups (2026-09-26)

Delegations were already end-to-end for HR (Unit 8) and enforced at decision time
(Unit 21): `acting_approver_id` hands a pending application to the delegate while
a delegation is active, with 60 backend and 18 frontend tests around it. This pass
closed the four remaining gaps. **827 backend tests / 340 frontend tests OK.**

### 1. Approver request UI — the self-service API had no screen

`create` has been self-service since Unit 8, but every delegation route in the
frontend lived under `/dashboard/hr-admin/**` and `app/api/hr/**`, so an approver
could not request cover, see their own request, or learn whether it was approved.
- New **"Cover" tab** on `/dashboard/approvals`, gated by `canRequestCover(role)`
  so a plain employee never sees it. Holds `CoverRequestForm` (no approver field —
  the backend forces the caller) and the approver's own rows.
- The sidebar had no approver-reachable entry at all: the only `Delegations`
  item sat inside `showHR`, so an approver had to already be on `/dashboard/approvals`
  to discover the tab. Added a **"Request Cover"** item for approver-or-HR roles
  pointing at a dedicated `/dashboard/cover` page that renders the same panel.
  A dedicated route rather than `?view=cover` on the approvals page, because
  `usePathname()` never sees a query string — the item could not have highlighted,
  and it would have double-highlighted with the existing Approvals item. The tab
  stays for in-context use and the approvals page still honours `?view=cover`.
  HR gets both items: the management list and their own cover page.
- New read-only page `/dashboard/cover/[id]`, reusing `DelegationReview`
  with a new `readOnly` prop so an approver sees the record and HR's decision
  reason but never the approve/reject/cancel controls. `DelegationTable` and
  `DelegationReview` both take `baseHref` / `backHref` instead of hardcoding the
  HR path. Both pages share one `loadCoverData()` server loader so the two entry
  points cannot drift.
- **New `GET /api/v1/delegations/candidates/`.** `EmployeeViewSet` is `IsHRRole`,
  so an approver could not list colleagues to nominate. Rather than open the HR
  employee list to every approver, this returns only `{id, full_name, role}` for
  active approvers, minus the caller.
- The list/retrieve **queryset is now scoped** for non-HR callers to
  `approver=user | delegate=user`, which makes the detail page a 404 for someone
  else's delegation instead of leaking its existence through a 403.
- The create proxy moved off the misleading `/api/hr/delegations` to
  `/api/delegations` (the common caller is not HR). The three HR decisions keep
  their `hr`-namespaced proxies.

### 2. Concurrency hardening

- `reject_delegation` and `cancel_delegation` re-read the row under
  `select_for_update()` and re-check state; previously only `approve` did, so a
  stale in-memory instance could overwrite a decision that had already landed.
- `approve_delegation`'s overlap check was a pre-check *before* the lock. It now
  re-runs under the lock, and the new `_lock_for_decision` locks the **approver
  row before the delegation row** — a single lock order, so two concurrent
  decisions for one approver cannot interleave or deadlock. Locking the delegation
  alone was never enough for approve, because the overlap check reads the
  approver's *other* approved rows.
- New DB backstop `one_open_request_per_approver`: a partial unique index on
  `(approver) WHERE status = 'requested'`. The `open_request_exists` `SELECT ...
  EXISTS` remains for the friendly 400; the index is what makes two concurrent
  requests impossible. `DelegationSerializer.create` catches the resulting
  `IntegrityError` inside a savepoint and returns the same 400.

### 3. Delegation notifications

`NotificationOutbox.application` was a non-null FK to `LeaveApplication`, so a
delegation was structurally unable to produce an email.
- `application` is now nullable and a nullable `workflows.Delegation` FK was
  added, with a `one_notification_subject` check that exactly one is set, and two
  *partial* unique constraints — one per subject family — so idempotency never
  collides across them and PostgreSQL's NULL handling stays useful.
- New `notifications/delegations.py` sends one mail **per party**, with
  `role_label` naming which side the row concerns (`approver` / `delegate`): a
  request mails only a nominated delegate, an approval or cancellation mails both
  sides, a rejection mails the approver plus the nominee. Recipients are resolved
  from ids already on the row — never a role scrape.
- Emitted through `transaction.on_commit` from the same transaction as the
  decision, so a rolled-back decision mails nobody; failures record `failed` on
  the outbox row and are swallowed.

### 4. Audit on create

`DelegationSerializer` was a plain `ModelSerializer`, so a request was invisible to
the audit trail until HR decided on it — and a request never decided on left no
trace at all. Creation now records `CREATED` in the same transaction as the row.
Spec 24 claimed this was already wired and described the actions as
`CREATED / UPDATED / CANCELLED`; the code writes `CREATED / APPROVED / REJECTED /
CANCELLED` and the table has been corrected.

### Tests
- `workflows/tests.py::DelegationConcurrencyTests` (new, 5 cases): stale-instance
  re-checks for reject and cancel, a delegation that ends under the lock, an
  overlap that appears under the lock, and the approver-before-delegation lock
  order.
- `workflows/tests.py::DelegationEndpointTests`: the list/retrieve rule is now
  "scoped, not HR-only" (own rows visible, someone else's a 404, employee 403, HR
  sees all), plus the `candidates` endpoint and the DB-level one-open-request
  constraint.
- `notifications/tests_delegations.py` (new, 22 cases): the recipient matrix,
  per-party outbox rows, idempotency, failure isolation, append-only rows, the
  on-commit guarantee, and the three decision services plus both create paths
  emitting.
- `audit/tests.py`: create is audited, and a failed action still writes none.
- `cover-request-form`, `approvals-workspace`, `delegation-review` (read-only),
  `delegation-table` (`baseHref`), and `delegation-access` frontend tests.

### Notes
- `next build` caught a real bundling bug: `delegation-table.tsx` imported a *value*
  from the server-only `@/lib/delegations`, dragging `next/headers` into the client
  bundle once the table was rendered inside the client-side workspace. The helpers
  now come from `@/lib/delegations-client`, which is the split the spec already
  asked for.

---

## Reassignment follow-ups (2026-09-26)

Reassignment (Unit 9) shipped complete: model, service, HR-only API, admin, the
two-panel HR screen, and its own tests. The audit that followed was about the
three things spec 09 explicitly deferred and that **no later unit ever picked
up** — so "fully implemented" meant closing those, not rewriting the feature.
**848 backend tests / 344 frontend tests OK.**

### 1. Nobody was ever told

Spec 09 said "email for reassignment is Unit 22". Unit 22 covers
`DECISION_RECORDED` and `APPLICATION_FINALISED` and never mentions
reassignment, so the deferral had no owner. A reassignment moved an application
between two people's queues and told neither — the replacement approver only
found out by opening their pending list.

`notifications/reassignments.py` now mails both sides on commit, reusing the
delegation discipline verbatim: the **replacement** learns they own a pending
application they did not ask for, the **previous** approver learns it was taken
off them before they acted. An *initial* assignment (`from_approver is None`)
mails only the new approver, because nobody lost a queue that never existed.

The employee is deliberately not mailed. Unit 15 already renders the
reassignment on their tracking timeline as a `reassigned` event with HR's reason
as the comment, so an email would only repeat it — and spec 09's own note that
the internal reason "belongs to later track" is satisfied there, not here.

`NotificationOutbox` gained a **third subject family** (`reassignment`) instead
of reusing `application`. That was forced, not stylistic: the application
constraint is unique per `(application, kind, cycle, role)` and an application
can be reassigned several times in one submission cycle, so an application-keyed
row would make every reassignment after the first silently match the first and
send nothing. `workflows/tests.py` and
`notifications/tests_reassignments.py::test_two_reassignments_of_one_application_both_notify`
pin it.

### 2. The intervention queue was lying about who held the application

Spec 09 assumed "pending" meant the responsible approver acts, and wrote
`current_approver` into the queue. That was true when written and stopped being
true in Unit 21, because delegation is a *query-time overlay* on the spine that
reassignment writes:

```
responsible = current_approver   ← reassignment moves this
acting      = that approver's active delegate, else responsible
```

So HR's queue showed "Jane Dean" for an application Bob HOD was actually
deciding. Reassigning it to a third approver looked like it worked while the
same delegate kept acting — a successful-looking intervention that quietly did
nothing. The behaviour is correct (Bob *is* meant to be handling Jane's queue),
but it was invisible at the only place HR could act on it.

`GET /api/v1/reassignments/pending/` now reports `acting_approver`,
`acting_approver_name` and `is_delegated` next to `current_approver`, and both
the queue table and the reassignment form name the delegate and who they cover
for. Resolution is bulked via `acting_approver_map()` — one delegation pass plus
one user-name pass for the whole page instead of two per row, with
`acting_approver_identity()` as the single-row equivalent and a test asserting
the two agree.

### 3. The interaction was correct but unpinned

Three routing tests now fix the semantics in both directions: reassigning *away*
from a delegated approver hands over cleanly (the old cover no longer matches the
moved spine), and reassigning *to* an away approver leaves their delegate acting.
The second is documented as intended rather than left to look accidental.

### 4. A real bug the new tests caught

`compose_body` reached for `application.leave_type.name` and
`_load_reassignment` did `select_related("application__leave_type")`.
`LeaveApplication.leave_type_id` is a **soft integer reference, not an FK** (the
FK upgrade is an integration-track concern), so both were wrong. The
consumer-level `except Exception` swallowed the `FieldError` and the mail simply
never sent — which is exactly the failure mode that guard exists for, and also
why it must not be the only thing watching. Fixed with the same `LeaveType`
lookup the pending-queue serializer uses.

Worth keeping in mind: a bug in any notification composer is now silent by
design. The mitigation is a test that asserts on the rendered body, not just the
outbox row's existence.

### 5. Audit view crash on flat `detail` payloads (found in review)

Opening the HR audit view against the dev database threw
`TypeError: Cannot convert undefined or null to object` and took the whole page
down, not one row.

`auditChangesText()` did `Object.keys(entry.detail.after)` unguarded, assuming
every `detail` is a `{"before", "after"}` diff. The field is free-form JSON, and
two actions write a flat payload: `document_generated` (the file) and
`stage_skipped` (the stages the self-approval check bypassed). Four dev rows had
that shape, so the page could never render.

The wrong contract was recorded in **three** places, which is why it survived:
`components/hr/audit-meta.tsx`, the `AuditEntry` TypeScript type, and the model
`help_text` — plus spec 11. All four now say free-form, and the renderer sniffs
the shape instead of assuming it. A flat payload summarises as `key: value` with
long values capped; the entry-level reason is only appended when the payload has
no `reason` key of its own, so `stage_skipped` does not print it twice.

**848 backend / 348 frontend tests OK.**

## Defect Fix (2026-09-28, uploading a supporting document 500'd on a long signed URL)

`POST /api/v1/leave-applications/{id}/documents/` returned
`Internal Server Error` with
`psycopg.errors.StringDataRightTruncation: value too long for type character
varying(200)`, raised out of `SupportingDocument.objects.create()` in
`leave/documents/services.py::upload`.

`SupportingDocument.file_url` was declared as a bare `models.URLField()`
(`leave/models.py`), so it inherited Django's default `max_length=200`. The
writer does not store a plain URL — it stores the result of
`Supabase Storage.create_signed_url()`, which is the project host plus the
storage path plus a JWT token. That is comfortably over 200 characters, so
**every** supporting-document upload overflowed the column. The sibling
`ApprovedLeaveDocument.file_url` had already hit this and carries
`max_length=1000` (`documents/models.py`); the leave-side field was never
widened to match.

Widened to `max_length=2048` with a `help_text` recording the derivation, so
it is not narrowed again: the model's own 255-char `file_name` cap yields a
~311-char storage path, which signs to roughly 900 characters — `1000` would
have left under 10% headroom. Migration
`leave/0014_supportingdocument_file_url_length.py` is a widening
`ALTER COLUMN TYPE`, so it is metadata-only in PostgreSQL and rewrites no
rows. The field remains a cache only: reads already re-sign from `file_path`
via `signed_document_url()`, with the stored value as the `ValueError`
fallback.

Regression test added to `leave/tests/test_documents.py::FileValidationTests`
posting a >900-character signed URL through the real endpoint. No frontend
change: `file_url` is an opaque `string` in `lib/leave-api.ts`,
`lib/tracking/types.ts` and `lib/audit.ts`.

Verification: `check` clean, `makemigrations --check` clean, migration applied
to the dev database, `leave.tests.test_documents` **34 tests OK**. Full suite
**849 tests, 2 failures + 5 errors — all in
`leave.tests.test_public_holiday_calculations`, confirmed pre-existing by
re-running the same suite on a stashed tree (identical 2/5).** They are
submit-time `ValidationFailedError`s in that suite's own fixtures, unrelated
to documents. Frontend untouched by this fix.

**Not addressed, same class of bug:** `file_name` is capped at 255 by the
column and `_validate_file()` does not check the uploaded name's length, so a
browser-supplied filename over 255 characters would raise the same
`DataError`. Left alone to keep this change to the reported defect.

## Operational (2026-09-28, dev database reset — history cleared, users kept)

Developer asked for every workflow, application and derived record to be
cleared while retaining the users. Executed against the dev database
`luanar_leave` (local `DEBUG=True`), after a `pg_dump` backup to
`storage/luanar_leave-backup-20260928-091504.sql` (166K, 36 tables, verified
to contain the 14 users and 11 applications).

**Why raw SQL rather than the ORM.** Five models enforce append-only in
Python and were confirmed to raise on delete — `AuditEntry`
(`AuditEntryLockedError`), `ApplicationRevision`, `NotificationOutbox`,
`ApprovalDecision`, `LeaveBalanceTransaction` — and roughly 20 foreign keys
are `PROTECT`. An ORM delete is structurally impossible. The database holds
**no user triggers** (verified via `pg_trigger`), so
`TRUNCATE ... RESTART IDENTITY CASCADE` satisfies every constraint while
bypassing the ORM guards. The guards are not weakened: they still protect
production, where this script will never run.

Ran inside one `transaction.atomic()` with an explicit assertion that no
`users_*` table appeared in the target list and that `django_migrations` was
excluded. 28 tables truncated; `users_user` (14), `users_employeeprofile`
(10), `auth_*`, `django_content_type`, `django_migrations` and
`django_session` kept. Profiles survive deliberately: they carry `grade`,
`department` and `category`, the fields workflow resolution matches on.

**Storage.** Four objects existed in Supabase, not the three expected. The
extra one was an orphan at
`leave-documents/b38cc892-…/8b49c76a…png` — the upload from the
`file_url` overflow above, which reached Supabase and *then* failed on the
DB insert, so the blob was stranded with no row. That is direct evidence the
fixed defect leaked a file on every attempt. All four removed; a sweep of the
root, `leave-documents/` and `approved/` prefixes confirms the bucket is
empty. (Listing the bucket required `bucket.list(path=...)` — the bound proxy
takes the path as its first argument, so passing the bucket id silently
returns the unfiltered root listing.)

**Restored** by re-running `seed_dev_users` (idempotent
`update_or_create`; reported "0 created, 7 updated", so no user was
disturbed): 4 leave types, 4 leave rules, 3 grade entitlements.

**Deliberately not restored** (developer chose this over keeping them):
the financial year `2026-05-01 → 2027-04-30` (active, label derives as
`2026-27`) and the three public holidays `2026-10-15 Mothers' Day`,
`2026-10-22 Fathers' Day`, `2026-12-25 Christmas HoliDay`. Unit 5 forbids
inventing LUANAR calendar dates, so no seed recreates them and they must be
re-entered through HR → Calendar. Until then the expected rejections are
`NO_FINANCIAL_YEAR_CONFIGURED` and `workflow_unavailable` — correct
behaviour, not a new defect. Workflows are likewise gone and must be rebuilt
in HR → Workflows, because no workflow survived to match the surviving
profiles.

**Verification:** all 22 cleared tables confirmed at 0; 14 users / 10
profiles intact; `check` clean; `makemigrations --check` clean; full suite
**849 tests, 2 failures + 5 errors — byte-identical to the pre-existing
baseline** in `leave.tests.test_public_holiday_calculations`, so no
regression.

`.gitignore` now excludes `storage/*.sql`, `*.dump` and `*.sql.gz`: the
dump is untracked and holds password hashes, so it must never be committed.

## Completed (Unit 26) — HR-Managed Approver Roles and Teams (2026-09-28)

Built from a direct feature request (prompt kept at `/tmp/opencode/feature_prompt.txt`),
not from `context/specs/` — the build plan ends at Unit 25, so **no spec file
exists for this unit**. The prompt plus this section are the authority.

**The defect it fixes.** "Who can approve what" was a list of role *names*
hard-coded in both stacks: `hod`, `dvc`, `registrar`, `auditor`, `clerk`,
`principal`, `vice_principal`, `bursar`, `dean`. `User.role` doubled as both
the thing that decides which screens an account can reach *and* the thing that
decides its place in an approval chain, so HR could not add a position, rename
one, or scope one to a group of people. Routing also ignored teams entirely,
so any holder of a code could decide for any applicant in a department.

**Backend — configuration as data.** `workflows/models.py` gains
`ApproverRole` (`code`, `label`, `description`, `history_scope`,
`is_institution_wide`, `handles_cancellation`, `is_active`), `Campus`,
`Team` (`campus`, `workflow`, `stage_roles` m2m), `TeamMember` and
`RoleAssignment`; `users.EmployeeProfile` gains a nullable `team`. Two
uniqueness constraints carry the routing invariant: `teammember_team_user_unique`
and `teammember_team_role_unique`, plus `roleassignment_user_role_unique`. FKs
onto a role are `PROTECT`, so configuration cannot be orphaned. Migrations
`workflows/0010`, `0011` (backfills the nine hard-coded codes as `ApproverRole`
rows, retired, so historical stages keep rendering) and `0012`; `users/0005`,
`0006` — the last narrows `User.role` to `employee | approver | hr`.

**Backend — one definition of "is an approver".** `is_approver_user()` in
`workflows/services.py` replaces every former role-name check: a person is an
approver when they hold at least one **active** role, as a `TeamMember` or a
`RoleAssignment`. Retiring a role therefore retires the approver status it
conferred, which is why retirement exists instead of deletion.
`approver_role_codes_for()` / `approver_role_labels_for()` describe a person by
the roles they hold, sorted for stability so a single-label surface does not
reshuffle between reads.

**Backend — team-scoped resolution.** `workflows/providers.py::resolve_stage_approver`
is the single resolution algorithm: the team member holding the role wins;
failing that, an institution-wide role must have exactly one active holder;
otherwise the configuration is incomplete and the submission is refused with an
error naming the role, the team, and what HR must do. No fallback approver
exists, so invariant 12.7 still holds.

**Backend — endpoints.** `/api/v1/approver-roles/` (list with
`?include_inactive=1`, create, patch, and `DELETE` → **retire**, refused with
409 naming every blocker while an active workflow, a team, or a holder needs
the role), `/api/v1/role-assignments/` (filtered `?role=`), `/api/v1/teams/`,
`/api/v1/team-members/`, `/api/v1/campuses/`. Every mutation is audited.
`/api/v1/approvals/capabilities/` reports the caller's real reach
(`is_approver`, `is_hr`, `can_request_cover`, `can_approve`, `pending_count`, …)
so the frontend stops inferring it.

**Frontend — the same removal, on the other side.** `UserRole` is now
`employee | approver | hr`; `Employee` gained `approver_roles`, `team`, and
`team_name`; `WorkflowStage.approver_role` is an open-ended `string` with
`approver_role_label` as the display fallback. Every hard-coded role map is
gone from `app/`, `components/`, and `lib/` — a grep for the nine codes now
matches only the approval and cancellation `__fixtures__`, which are
deliberate historical-workflow snapshots. The workflow builder's stage picker is
a live role list seeded from the first available role, and it preserves an
unknown or retired code rather than dropping a stage's approver.

**Frontend — new HR surfaces.** Roles: list (including retired, with the
usage blockers that would stop a retirement), create, edit, retire, and
institution-wide holder add/remove. Teams: list, create, edit, campus
creation, and member add/remove constrained to the team's `stage_roles`. Both
are linked from the HR admin index and the sidebar. `api-client.ts` gained
`apiClientUrl` so reference-data reads follow DRF's absolute `next` links
rather than silently stopping at page 1 — the same bug class as the employee
list.

**Frontend — access is asked, not inferred.** `lib/approvals/capabilities.ts`
loads the caller's reach server-side; the approvals queue, the cover pages, the
sidebar's Approvals item, and the dashboard's pending count all read it and
**fail closed** when it cannot be read. The dead `/dashboard/department` nav
item is gone.

**Three bugs the verification pass caught, all now fixed.**

1. **`next build` failed outright.** `approver-roles-client.ts` re-exported
   `HISTORY_SCOPES` from the server-side `lib/approver-roles.ts`, dragging
   `next/headers` into the browser bundle — *"You're importing a module that
   depends on `next/headers`… in the Pages Router."* A client component cannot
   read a constant from a module that also reads the API client, so the
   scopes moved to the import-free `lib/approver-role-scopes.ts` that both
   modules re-export. `typecheck:test` never saw it; only the build did.
2. **The holder picker hid valid candidates.** `RoleAssignmentForm` inferred a
   role's existing holders from `Employee.approver_roles`, which is an
   aggregate over team membership *and* institution-wide grants and so cannot
   say which a person has. It now takes the role's actual assignments. A test
   pins the case that motivated it: somebody holding a code only on a team is
   still offered the institution-wide grant.
3. **`CampusForm` read a field it never rendered.** It submitted
   `description` from a form that had no such input, so the value was always
   `""`. The input now exists.

**Verification.** `makemigrations --check` clean; full backend suite **992 tests
OK** (including 23 dedicated migration tests for the backfill, and new
`tests_roles.py` / `tests_teams.py` / `tests_migrations.py` plus shared
`workflows/testing.py` helpers). Frontend: `tsc`, `tsc -p tsconfig.test.json`,
and `eslint` clean; **63 files / 421 tests** pass (new:
`approver-access`, `approver-reference-data`, `approver-role-form`,
`approver-role-scopes`, `approver-role-table`, `campus-form`,
`role-assignment-form`, `team-form`, `team-member-list`); `next build` compiles
and registers all eight new HR routes.

**Context updated alongside.** `architecture.md` §5.1 (the new tables), §6.3
(rewritten — the two-layer system-role/approver-role model, replacing the
hard-coded Supervisor→HOD→Registrar→DVC list), §7 (stages resolve a role *code*
against the registry, with the retirement and snapshot consequences), and a new
invariant **12.11 Approver-Role Identity**.

**Still open.** The Team form's workflow picker reads
only the first page of `listWorkflows()` — harmless at current volumes, but it
should use an exhaustive list like the role and employee pickers do. (The rest
of this unit is committed as `4352a69`.)

---

## Loading the system fast — where the time was actually going

The complaint was "the frontend takes too long." Measuring first, before
touching anything, split the answer in two: a genuine backend problem on the
Roles screen, and a set of avoidable request waterfalls across the dashboard.
Everything else was already fast.

**The Roles screen was one query per role, per field.** `is_in_use` and `usage`
are the same fact asked for twice, and the usage clauses each name a blocker —
the active workflows that have a stage for the role, the active teams that hold
it, the institution-wide assignments outstanding against it. Computing that per
role made `/api/v1/approver-roles/` run **69 queries for six roles** and grow
with every role HR ever added. It took 171–229 ms and was the slowest endpoint
in the admin.

It is now one pass. `role_usage_map()` in `workflows/services.py` reads the
three blocker sets for *all* roles at once, and `ApproverRoleSerializer`
computes the map once per request and caches it on the serializer context, so
`is_in_use` reads from the same computation instead of re-deriving it. Six
roles now cost **four queries, 34–38 ms** — and the count no longer moves when
roles are added. `_role_usage()` still exists for the single-role paths and
delegates to the batch, so there is one definition of "in use", not two.

Two tests in `workflows/tests_roles.py` pin this: one asserts the exact query
count of the list endpoint, the other adds four roles and asserts the count has
not moved. A test that only checked the first screenful would have passed
against the old code, because six roles happened to be all the fixtures had.

**The dashboard asked the same question repeatedly, then again in the browser.**
Three fixes, all about not doing work twice:

1. The layout fetched the current user, and the dashboard page fetched them
   *again*. `getCurrentUser` is now wrapped in React `cache`, so one request
   renders both, and the two reads run in parallel rather than in sequence.
2. `loadApprovalCapabilities` is cached the same way. It was the pattern behind
   the pending-approvals count, the sidebar's Approvals item, and the approvals
   page all re-asking the server on first paint, once per component.
3. The layout now *passes* `isApprover` and `pendingApprovals` down to
   `DashboardShell` as props instead of letting it fetch capabilities again
   client-side on every mount. The server already knows both; the browser was
   being asked to go and re-learn them.

The roles, teams, and approvals pages had their independent reads moved into
`Promise.all` as well. The roles and teams pages keep per-resource error
messaging, so a failed reference-data call still names itself instead of blanking
the screen.

**Verification.** Backend **994 tests OK** (`workflows` alone: 386).
Frontend: `tsc`, `tsc -p tsconfig.test.json`, `eslint` clean; **63 files / 424
tests** pass (the two extra are the capability-prop tests for
`DashboardShell` and `ApprovalsNavItem`, which now assert the shell issues no
requests of its own). `next build` compiles.

**Production, warm, best of three:** `/dashboard` 216 ms, `/dashboard/approvals`
345 ms, `/dashboard/hr-admin/employees` 259 ms, `/dashboard/hr-admin/roles` 329
ms, `/dashboard/hr-admin/teams` 352 ms. Every screen a user actually waits on
is now a few hundred milliseconds of mostly network-and-Django time.

**One thing that was not a code problem, recorded so it is not re-investigated.**
`/dashboard/hr-admin/employees` hung in `next dev` — no response headers after
60 s, forever, while every neighbouring route answered in under two seconds and
the same route answered in 206 ms under `next start`. It was not this branch:
stashing the one file changed in that route did not help, and the route's
dependencies compile fine in a production build. It was a corrupted Turbopack
cache. `rm -rf frontend/.next` and a restart fixed it, after which the route
loads normally. If a single route ever hangs with no headers while its siblings
are fine, clear `.next` before reading any code.

---

## Completed — Workflow Sections (Sections/members) migration (2026-09-29)

Follow-on to Unit 26. Redesigns the approval workflow from **ordered stages
with a single approver each** to **ordered Sections, each with a roster of
members, decided by whichever member acts first** — and changes cancellation
routing the same way. Not yet committed; no `context/specs/` file (like Unit 26,
this landed from the same feature request and the authority is
`context/architecture.md` invariants plus this section).

**Backend — model + migration (`workflows/0009`, `leave/0015`, `0016`,
`workflows/0017`).**
- `WorkflowStage` → `Section`: `approver_role` FK, `name`, `order`,
  `description`, `is_active`, unique `(workflow, order)`. Section identity
  across a chain write is the **(role, name)** pair, so reordering preserves
  each section's members; a role/name change rebuilds the section empty
  (never handed to a new role without HR asking).
- `SectionMember` (section, user) — any number of members per section; the
  same person may sit on several sections but not twice on one.
- `ApplicationStage.approver`/`assigned_approver`+`ApplicationStageApprover`
  snapshot rows: assignment stays `null` until a claim or reassignment.
- `CancellationStageSpec.approver_user_ids` eligibility sets +
  `CancellationStageApprover` snapshot rows + nullable
  `CancellationApprovalStage.approver` (set on the decision); `leave.0016`
  backfills existing rows' eligibility.

**Backend — behaviour.**
- `Team.workflow` is required; workflows are shared, so a team's Sections and
  members belong to the workflow and are flattened for display only.
- Providers route through the employee's team workflow; the applicant is
  excluded from every Section's eligibility, and a Section left with no
  eligible member refuses submission (`422 workflow_unavailable`) instead of
  being skipped. No `SKIPPED` stage state exists; `STAGE_SKIPPED` audit rows
  remain only as historical records.
- First eligible member claims a stage atomically (`select_for_update`); a
  concurrent loser gets the existing 409 stage-changed response.
- Reassignment widens eligibility; active delegation overrides a
  delegated-away member.
- `get_workflow_member_user_ids()` reads `ApplicationStageApprover` snapshots
  instead of the nullable `assigned_approver_id`, which removed a `None`
  event-recipient bug.
- Cancellation pending queues expose every eligible member; decided history
  belongs only to the actor; open stepper stages carry `approver_name: null`
  plus `eligible_approvers`.
- E2E seed/API calls use nested `sections` and `/api/v1/section-members/`.
- Tracking lookup repeated-query optimization; the honest query bound is 12.

**Backend verification.** `leave.tests.test_cancellations`: **52 OK** (nullable
claimers, snapshot authority, shared sections, queue visibility,
defence-in-depth self-decision). Full suite **1004 OK**; `makemigrations
--check` clean; migrations applied to the local DB.

**Frontend — same design on the other side.**
- `lib/workflows.ts`: `WorkflowStage` → `WorkflowSection` (+`SectionMember`),
  inputs gain `name`; `lib/teams.ts`: `Team.workflow` now required (TeamInput),
  `members` are per-person flattened rows with their section list, and a
  read-only `sections` summary.
- `components/hr/workflow-form.tsx`: Section editor (name, role, description,
  active, reorder/add/remove), membership read as counts and staffed on the
  Teams page.
- New `lib/section-members-client.ts` (client-safe: kept out of `teams.ts`,
  which imports the server-only `api-client`) + proxies
  `app/api/hr/section-members/route.ts` and `[id]/route.ts`.
- `components/hr/team-member-list.tsx`: section-based roster — pick a person
  per section, add/remove by section member id; shared-section note. Deleted
  the dead `team-members` proxies and clients.
- Removed the `"skipped"` stage/status vocabulary from tracking and approval
  types, the two timelines, and the fixtures; replaced the
  `makeSelfApprovalReview`/`pending_with_skipped_stage` fixtures with
  "a colleague on the applicant's section decided it" (`makeApplicantExcludedReview`,
  `pending_with_applicant_excluded.json`).

**Frontend verification.** `tsc --noEmit` clean; **63 files / 423 tests OK**
(rewritten `team-form`, `team-member-list`, `workflow-form`, `workflow-table`,
`approval-detail`, `tracking-view`); `eslint` clean; `next build` compiles and
registers `section-members` routes. (A stale `.next` validator referencing the
deleted `team-members` routes fails the first `next build`; `rm -rf .next`
fixes it.)

**Context updated alongside.** `architecture.md` invariants **12.3** (no skipped
stage; the applicant is removed, not a step) and **12.11** (section identity,
membership on the section, several members decide). `specs/18` amended for the
any-of eligibility-snapshot cancellation model. This section records the frontend
and the verification.

**Still open.** Nothing blocking. The workflow form's section-name field is
optional (the backend falls back to the role label); an empty picker of sections
to staff appears only when a team's workflow has none. The workflow list still
reads the first page of `listWorkflows()`.

---

## Defect Fixes + Operational (2026-09-29, full dev reset — everything cleared)

Developer asked for every row removed and every process restarted. Executed
against the dev database `luanar_leave` after a `pg_dump` to
`storage/luanar_leave-backup-20260929-103232.sql` (204K, 43 tables). Unlike the
2026-09-28 reset, **users were cleared too** — nothing was kept.

**Wipe.** `manage.py flush` (TRUNCATE `RESTART IDENTITY CASCADE` on every
model table, then `migrate`; `django_migrations` is not a model table so flush
leaves it and the migrate run is a no-op). 702 rows / 43 non-empty tables → 3
non-empty (`auth_permission` 164, `django_content_type` 41, `django_migrations`
92) → 610 rows after reseeding.

**Calendar recreated by hand** (no seed exists; `seed_approvals_dev` raises
`CommandError` without an active FY): `FinancialYear` `2026-06-01 → 2027-05-31`
active, and the two `PublicHoliday` rows verbatim — `Mother's Day` 2026-10-15,
`Chrismas Holiday` 2026-12-25 (the spelling in the row is kept as-is). The
document template needed nothing: `documents.services.get_template()`
materializes the default on first access, so only HR's edited wording is lost.

**Three defects the reset exposed, all fixed in the working tree.**
1. **`seed_approvals_dev` could not seed at all** (`_seed_cancellations`).
   It decided each stage as `actor=stage.assigned_approver`, but under the
   claim model that field is `None` until somebody acts
   (`assign_workflow` sets `assigned_approver=None` and snapshots eligibility
   in `ApplicationStageApprover`). `decide(None)` reached
   `policies._decided_this_cycle` and raised `AttributeError: 'NoneType' object
   has no attribute 'id'`. Now reads
   `workflows.services.eligible_approver_ids()` and acts as the first eligible
   member, raising a `CommandError` naming the section when a chain has nobody
   entitled to act — the same shape the cancellation helper already used.
2. **Re-running the seed crashed** (`_seed_workflows`). It rebuilt a
   workflow's sections on every run, which is impossible once an application has
   snapshotted the chain: `ApplicationStage.section_ref` is `PROTECT` because
   that section *is* the running application's frozen history. The rebuild is
   now skipped while any stage references the workflow, so the documented
   "re-running repairs a partially seeded database" contract holds again.
   Verified: a second run is a no-op (13 applications, 8 sections, unchanged).
3. **`GET /api/v1/leave-applications/` 500'd** for the seeded employee.
   `_seed_documents` creates metadata-only rows under `seeded/820/...`, paths
   that are not in the bucket, and `signed_document_url` raised
   `StorageApiError`/`httpx.HTTPStatusError` (400/404) past the two callers that
   only caught `ValueError` — so one unopenable document failed the whole
   listing. `signed_document_url` now translates "no such object" (400/404) into
   the `ValueError` every caller already handles, falling back to the stored
   URL; a rejected key (401/403) or a broken bucket (5xx) still raises. Same
   shape as the 2026-09-26 "storage misconfiguration 500'd the read endpoint"
   fix, for the missing-object case it did not cover.

**Storage.** The bucket held 22 objects against 5 `ApprovedLeaveDocument` rows,
so 17 were unreferenced (16 from before, plus one stranded by the first, aborted
seed attempt). Deleted all 17 and kept the 5 the live rows point at, rather than
the literal "empty the bucket" — that leaves the bucket and the database in
exact agreement. `leave-documents/` was and stays empty.

**What the reset cost** (recoverable from the dump, must be redone in the UI):
HR's hand-built `itm` "ICT Manager" approver role, the `ICT workfow` workflow
with its four sections, the `ICT Department` team, the hand-trimmed section
chains (the admin workflow was down to Supervisor + Registrar), and three manual
applications `LV-2026-27-000001..000003`. Reference numbers restart at `000001`.

**Verification.** `check` clean; `makemigrations --check` clean; full backend
suite **1004 tests OK** (run twice — once per storage fix). Live HTTP: login
200, `auth/me` 200, `leave/me/summary` 200, `leave-applications/` 200 with all 7
of the employee's applications, `approvals/` 200, unauthenticated
`leave/me/summary/` 401, `/admin/` 302; frontend `/` and `/dashboard` 307 to
login, `/login` 200. `frontend/.next` cleared before restart (the route set
changed — `section-members` — and the tracker records a corrupted Turbopack
cache failing a single route with no headers).

**Both dev servers now run detached** (`setsid nohup`, logs at
`/tmp/opencode/django.log` and `/tmp/opencode/next.log`) rather than in the two
VS Code terminals: `uv run manage.py runserver` (pgid 11362) and `npm run dev`
(pgid 11169). No `qcluster` — development runs tasks inline.


---

## Completed — Team Management (Units 1–10) (2026-09-29)

Simplifies HR Team Management to the ten units the feature request lists, and
stops at Unit 10. **Unit 11 (Finalized Leave + Audit View) is deliberately out
of scope** and already exists from the original build. Follow-on to Unit 26 and
the Workflow Sections migration above; no `context/specs/` file, so the
authority is `context/architecture.md` plus this section. Not yet committed.

**The idea.** A team is not a row with a checkbox. It is something HR builds,
checks, and then puts into force — and a membership is not a row that is either
there or not, but a *period*. Both are ordinary things to get wrong, so both are
modelled explicitly.

**Backend — model and migration (`workflows/0018`, `audit/0012`).**
- `Team.is_active` → `Team.status` (`draft` / `active` / `inactive`), backfilled
  from the old boolean. The `is_active` column is dropped, so a team cannot
  hold two contradictory answers to "is this routing".
- `Team.department` (free text), `effective_from`, `effective_to`; the
  `team_effective_window_ordered` check constraint.
- `SectionMember.effective_from` / `effective_to` dated from `created_at` for
  existing rows, with `SectionMember.objects` narrowed to **open** memberships
  and `SectionMember.all_objects` keeping every period. Two constraints:
  `sectionmember_effective_window_ordered`, and
  `sectionmember_open_section_user_unique` — *one open membership per section
  per person*, which is what lets a handover be a removal plus an addition
  rather than a duplicate row.
- `AuditEntry.Action.ACTIVATED` / `DEACTIVATED`.

**Backend — one authoritative lifecycle.**
- `DatabaseWorkflowProvider.get_stage_definitions` gates on the team being
  `active` *and* inside its effective window, and resolves each section's
  approvers from memberships effective **today**. A draft, retired, future, or
  expired team refuses submission with a sentence naming the team and the date,
  so the applicant's failure is actionable rather than a stage error later.
- Membership effective-dating does not touch the running application:
  `decide()` still reads the `ApplicationStageApprover` snapshot, and
  `ApplicationStage.section_ref` stays `PROTECT`, so a chain cannot be rebuilt
  out from under an application waiting on it.

**Backend — nested configuration, because a chain is decided with its team.**
- `POST /teams/` accepts either `workflow` (an existing chain) or
  `new_workflow` (ordered `sections`, each with a role and member user ids),
  created in the same transaction. Existing and inline are exclusive. A chain
  cannot be supplied on update — replacing it under a live team would strand
  every application inside the old one.
- `validate_team` / `GET|POST /teams/{id}/validate/` return **every** problem at
  once with a stable `code` per issue, because a chain with three unstaffed
  steps should take HR one pass. Side-effect free.
- `POST /teams/{id}/activate/` validates transactionally and refuses a team that
  is not ready, leaving it `draft`. `POST /teams/{id}/deactivate/` is idempotent.
  Both audited. A team's detail route is reachable whatever its status — a
  retired team is exactly the one HR needs to read.
- `POST /teams/{id}/` status is read-only on PATCH, so activation cannot happen
  by accident through an ordinary edit.
- `GET /teams/` takes `?status=` and `?include_inactive=1`; the default excludes
  retired teams but includes drafts.
- `SectionMember` gains `?history=1` (all periods) against the default view (who
  can act now), and accepts `effective_from` on write.
- Removal **closes** a period; a period that has not started yet never took
  effect and is deleted outright, so a cancelled handover leaves no row claiming
  somebody held a step they never held.

**Two defects the new tests found, both real.**
1. `validate_team` called `resolve_section_approvers`, which *raises*
   `WorkflowConfigError` for an unstaffable step rather than returning empty —
   so validating a team with one empty step returned a 500 instead of the one
   issue HR needed. Caught, with the reason carried into the report.
2. `activate_team` snapshotted the team's status *after* setting it to `active`,
   so the audit entry recorded an empty `before`/`after` — the one record of the
   decision said nothing. The prior status is now captured first.
   (`ValidationFailedError.__str__` also changed: it said "1 validation
   error(s)", which is what a service exception's string form ends up in a log
   or a 422 body. It now spells the issues out.)

**Backend verification.** `workflows.tests_team_configuration`: **77 OK** (nested
creation, validation, lifecycle, HR-only authorisation, effective membership
history, routing, audit, historical integrity). Full suite **1085 OK**;
`makemigrations --check` clean; `check` clean.

**Frontend — the same model, and the two places it used to lie.**
- `lib/teams.ts`: `is_active` → `status` + `is_effective` + `effective_from` /
  `effective_to` / `department`; `TeamSection` carries its members; new
  `TeamReadiness` / `TeamReadinessIssue`; `TeamWorkflowInput` for the inline
  chain. `lib/workflows.ts` `SectionMember` gains the period and `is_effective`.
- `components/hr/team-form.tsx`: one form for the whole team — identity, campus,
  department, effective window, and *either* an existing chain *or* a step
  builder that writes the chain inline with its members. The `is_active`
  checkbox is gone; lifecycle is not a field.
- New `components/hr/team-lifecycle-actions.tsx` (readiness / put into force /
  retire, rendering the issue list a refusal arrives with) and
  `components/hr/team-table.tsx` (one row per team, status and window
  side by side, "1 of 2 staffed").
- New `teams/[id]/page.tsx` — the team's own page: status, window, lifecycle,
  and the roster. The list was the wrong home for staffing a step: a step
  staffed on a team that is not routing is not doing anything, and saying so
  in the same view is the point.
- `components/hr/team-member-list.tsx`: optional start date per addition, the
  period on each row, and "Who was here before?" fetching history on demand —
  a person who left a step in March still signed for it.
- The **employee** team picker was silently offering draft teams, which route
  nothing: an employee only found out at submission. It now lists every team
  (including retired, so an assigned one is never hidden into looking
  unassigned) and labels each with why it would not route.
- Proxies `app/api/hr/teams/{id}/{validate,activate,deactivate}/route.ts` proxy
  rather than reimplement: the browser must not be able to get a different
  answer about readiness than the activation action itself gives.

**Frontend verification.** `tsc --noEmit` clean; **63 files / 420 tests OK**
(rewritten `team-form` for the unified form, new `team-table` and
`team-lifecycle-actions`, updated `team-member-list` and `employee-form`);
`eslint` clean; `next build` compiles and registers the three new action routes.

**Context updated alongside.** `architecture.md` — Team lifecycle as one
authoritative field, effective-dated membership, nested creation, and the
validate/activate contract.

**Superseded by the standalone-workflow removal.** The chain picker and the
workflow list screen it fed are gone: a team owns its chain one-to-one and the
chain is written inside the team write, so there is no list to page. A team's
lifecycle is `Team.status` alone.

## Completed — Departments and one approver per section (2026-10-01)

Follow-on to Team Management above. A team's `department` was free text and a
section could name several members; both made eligibility and accountability
unknowable. The authority is `context/specs/20-hr-to-employee-data-integration.md`;
not yet committed.

**The idea.** An approver is one named person, and eligibility is a fact about
where they work. A free-text department cannot answer "is this person allowed to
approve for this team", and a section with a roster cannot answer "who decided".
So Department becomes a first-class record and each section holds exactly one
approver.

**Backend — Department as a real entity.**
- New `users.Department` (active/retired, audited) with lifecycle API; employees
  and teams reference it by PK. `Department.retire` refuses while anything still
  points at it, so a department is not deleted out from under a team.
- `users/0007_department.py`, `0008_employee_department_reference.py`;
  `audit/0013_department_target_type.py`.
- Employee and team writes validate against active departments and expose
  `department_name` on read, so the UI never has to resolve an id itself.

**Backend — one approver per section.**
- `Section.approver` is the single authoritative holder;
  `SectionMember`/`all_objects` keep the effective-dated history.
  `add_section_member` sets `Section.approver`, closes the outgoing period, and
  refuses a future `effective_from`.
- `TeamSectionInputSerializer.approver` is one primary key (`required=False`,
  `allow_null=True`), not a `members` roster. `new_workflow.sections` therefore
  names one approver per step; inline chain creation stays exclusive with an
  existing `workflow`.
- `GET /api/v1/teams/eligible-approvers/` answers *who may hold this step*:
  `?department=<id>&role=<id>` → `{department, candidates}`; institution-wide
  roles bypass the department match, and anyone already holding a **different**
  role in that department is excluded (conflict minus holding).
- `ApproverRoleWriteSerializer` takes only `label`; `code` is derived and
  immutable, and behavioural fields stay editable.
- `workflows/0020`–`0023`: department reference, single approver, optional
  draft workflow, institution-wide final approval.

**Frontend — the two questions, kept apart.**
- New `lib/departments.ts` and department proxies; `team-form` is two pages —
  page one is what the team *is* (name, department, window), page two is who
  decides (one named person per step). A team can still be saved as a draft with
  no chain; activation requires a department, workflow, roles, and staffed
  sections.
- Each step's picker fetches its own eligible people, because eligibility is
  per role; changing a step's role clears the choice rather than sending an id
  that would be refused.
- `team-member-list` is a single-approver picker per step (appoint = handover,
  remove, history on demand). The current holder is offered even if the
  eligibility list has moved on, so a held step never reads as unstaffed.
- `employee-form` and `approver-role-form` updated for department selects and
  name-only role creation.

**Verification.** Backend `workflows` **497 OK**, full suite **1125 OK**.
Scratch-DB seed check (`luanar_seedcheck`, since dropped): migrations applied
through `0023`; `seed_dev_users` 9 users; `seed_approvals_dev` refuses without an
active financial year (`CommandError`, documented D5), succeeds after creating
one, and is idempotent on re-run. Frontend `tsc --noEmit` and
`typecheck:test` clean, `eslint` clean, **63 files / 425 tests OK**, `next build`
compiles.

## Completed — HR-managed credentials (2026-10-01)

Follow-on to the employee directory. The Unit 2 assumption was that a
directory-created employee gets an **unusable password** and waits for an
external identity provider; the product now issues its own passwords, and they
had to be created by the right hand. The authority is
`context/specs/27-hr-managed-credentials.md`; not yet committed.

**The idea.** A superuser creates `hr` accounts in the Django admin; HR creates
every other account from the employee directory and sets that person's initial
password, and can reset it later. Nobody changes their own password, and the
directory cannot hand out `approver` or `hr` — approver standing still comes
from a workflow appointment.

**Backend (`users`).**
- `EmployeeSerializer` gains a write-only `password`: required and min-8 on
  create, optional on `PATCH` (non-blank resets, blank/absent keeps). Create now
  calls `user.set_password` instead of `set_unusable_password`.
- The role rule is enforced in `validate`: create always yields `employee`
  (`approver`/`hr` refused); update refuses any change of role, while an
  unchanged value is accepted so an existing HR/approver profile can still be
  saved. The password never enters the audit snapshot.
- `users/admin.py` `save_model` syncs `username` to `email`, so an
  admin-created HR account logs in through the email-based login.

**Frontend.**
- `lib/employees.ts`: `EmployeeInput.password?: string`.
- `employee-form` gains a Password field (`required` + `minLength={8}` on
  create; "Leave blank to keep the current password" on edit); the Role control
  is now read-only and `role` is no longer sent in the payload.

**Verification.** Backend full suite **1134 tests OK** (was 1125). Frontend
`eslint` and `typecheck:test` clean, **63 files / 426 tests OK** (was 425),
`next build` compiles.

## Operational (2026-10-01, dev database seed data removed — bare DB)

Developer asked for **all seed data removed**, obsolete accounts included. Ran
`manage.py flush --no-input` against the dev database `luanar_leave` (local
`DEBUG=True`). `flush` truncates tables via SQL, so the append-only guards and
`PROTECT` foreign keys that make an ORM delete impossible (see the 2026-09-28
note above) do not apply.

**Removed.** The obsolete `testdvc` account (role `employee`, no profile) and
its `RoleAssignment` to `dvc`; the orphaned `Legacy Chain` workflow and its
single `DVC` section; and the full `seed_dev_users` set — the 9 accounts
(`employee`, `supervisor`, `hod`, `dean`, `registrar`, `dvc`, `hr`,
`admin-supervisor`, `admin-hod`), 4 departments, 3 grade-entitlement bands, 4
leave types and 4 rules — plus the 6 backfilled approver roles. The DB was left
with **0 users, no superuser**.

**Preserved.** Schema and migration history (102 applied, none unapplied);
`flush` re-emits `post_migrate`, so content types (42) and permissions (168)
were rebuilt. `manage.py check` clean.

**To rebuild dev data.** `uv run manage.py seed_dev_users` creates the nine
accounts (and their empty profiles). It creates **no** business
configuration — no departments, approver roles, teams, chains, entitlements or
leave types; those are HR data and are created from the app. A superuser must
be created separately (`createsuperuser`), using the email address as the
username because login resolves email through that column.


---

## Completed — Email delivery made real (2026-09-30)

Email notifications were "established" — outbox model, five subject families,
composers, tests — but **no mail had ever left the machine**. Three independent
gaps, all confirmed by reading the code:

1. **Transport never configured.** `config/settings/base.py` hard-coded
   `django.core.mail.backends.console.EmailBackend`; there were no SMTP settings,
   no `DEFAULT_FROM_EMAIL`, and no env reading. `.env.example` had no email block.
2. **Send was inline.** Each composer called `send_mail` itself, inside whatever
   request emitted the event — so mail was bound to a web request and to whatever
   relay answered it.
3. **Two notification paths were dead code.** `leave/cancellations/events.py` was
   still the Unit-18 **no-op sink** (so no cancellation could ever notify, and
   `employee_notification_state` could never move off `not_required`), and
   `plans.tasks.run_plan_housekeeping` existed but **nothing scheduled it** (so
   block-confirmation reminders never fired).

### Delivered

- **Env-configured transport** (`config/settings/base.py`): `EMAIL_BACKEND`, host,
  port, user, password, `EMAIL_USE_TLS`/`EMAIL_USE_SSL`, `EMAIL_TIMEOUT`,
  `DEFAULT_FROM_EMAIL`, `NOTIFICATIONS_SYNC_SEND`, `EMAIL_DEV_RECIPIENT_OVERRIDE`.
  Console stays the default, so development needs no credentials. Google SMTP
  (`smtp.gmail.com:587` + TLS + an app password) is documented in `.env.example`
  with placeholders only; **the user pastes the real credentials into
  `backend/.env`**.
- **`notifications/tasks.py`** — the single `send_mail` call site.
  `deliver_notification(outbox_id, recipients=None)` re-reads the row (idempotent:
  a non-`pending` row is a no-op), records `sent`/`failed` with the error, and
  never raises. `enqueue_delivery()` dispatches through `django_q.tasks.async_task`
  on `transaction.on_commit`; a broker outage is logged and the row stays `pending`.
  SMTP without `DEFAULT_FROM_EMAIL` fails loudly on the row (Gmail rejects an
  unauthorised `From:`), instead of filling the outbox with unexplained 550s.
  `EMAIL_DEV_RECIPIENT_OVERRIDE` is honoured **only** under `DEBUG` and refused
  (error log) otherwise.
- **Composers queue instead of send**: `send_decision_email` → `queue_decision_email`
  (recipient list for a finalised application travels with the task — the row
  records the owner, the mail goes to owner + finalising approver),
  `queue_delegation_email`, `queue_reassignment_email`, and `notifications/plans.py`
  routed through the same helper (its plan-assignment notification previously
  bypassed `on_commit` entirely).
- **Cancellation notifications**: the bus is real now
  (`register_consumer`/`emit_cancellation_event`, mirroring `workflows/events.py`),
  `notifications/cancellations.py` composes one email per event for the employee,
  and `NotificationOutbox` gains a `cancellation` FK with
  `one_outbox_row_per_cancellation_kind_role` (migration `notifications/0006`).
  This family keeps `employee_notification_state` too, so the composer marks it
  `pending` when it queues and the delivery task reconciles it to `sent`/`failed`.
- **Housekeeping scheduled**: `plans/migrations/0002_schedule_plan_housekeeping.py`
  creates the `django_q.Schedule` row (daily 06:00) for
  `plans.tasks.run_plan_housekeeping`.
- **Read-only admin** (`notifications/admin.py`): the outbox is inspectable
  (state, recipient, error, filters, search) and cannot be edited by hand, matching
  its append-only rule.
- **Docs**: `DEVELOPER-GUIDE.md` (the "change the wording"/"make mail go out"
  recipes now name the real modules — they pointed at `subscribers.py`,
  `templates.py`, `dispatcher.py`, which do not exist), `README.md` (new "Email
  Notifications" section + worker requirement), `context/architecture.md` (§8 now
  describes the outbox → on-commit → worker path), and
  `context/specs/22-email-notifications-spec.md` §5 records the delta to D6.

### Verification

Backend **1151 tests OK** (was 1137 before this pass: 14 transport-level tests in
`notifications/tasks_tests.py`, 11 cancellation tests in
`notifications/tests_cancellations.py`, plus the queue-contract rewrites in
`tests_delegations.py`/`tests_reassignments.py` and the end-to-end journeys).
`makemigrations --check` clean; `migrate` applies `notifications/0006` +
`plans/0002`.

### Still open (operational, not code)

- **No live SMTP verification yet** — it needs the user's Gmail credentials in
  `backend/.env`. Until then, `EMAIL_DEV_RECIPIENT_OVERRIDE=<inbox>` +
  `NOTIFICATIONS_SYNC_SEND=True` is the fastest single-process check.
- **A worker must run for queued mail and for cron jobs**: `uv run manage.py
  qcluster`. `Q_CLUSTER["sync"]` affects `async_task` only, never a schedule row.

## Completed — Real users, real inboxes (2026-10-01)

The email pipeline worked, but it could reach nobody who mattered. `HR creates
account` ended in `set_unusable_password()` and stayed there: the only ways to
give a real person a password were a superuser typing it into Django admin or the
`seed_dev_users` password `testpass123`. An HR-created employee could not
authenticate, so every notification the system sends them was undeliverable —
which is the whole point of a queued outbox.

### The set-password flow

- **Model** — `users.PasswordSetToken`: the secret is `secrets.token_urlsafe(32)`
  and only its SHA-256 is stored; `expires_at` (72h, `PASSWORD_SET_TOKEN_
  LIFETIME_HOURS`), `used_at` for a real consumption, `invalidated_at` for a
  superseded one. Keeping those two apart is what makes "used" and "replaced"
  distinguishable in the audit trail, and `is_usable()` is the single definition of
  "still good" that both request and confirm go through.
- **Service** — `users/services.py`: `request_password_set(email, actor=None)` and
  `confirm_password_set(token, password)`, plus `token_is_usable` for the page's
  pre-flight. Passwords go through Django's configured validators against the
  account, so the similarity check works; a weak password fails *without*
  consuming the link, so the person can try again.
- **One live link per account.** Issuing a link stamps `invalidated_at` on the
  outstanding ones, so a link that leaked into an old inbox dies the moment HR
  resends.
- **No enumeration.** `request_password_set` returns `None` for an unknown,
  deactivated or address-less account, and the endpoint answers with the same 202
  body in every case. The refusal is logged, never returned.
- **Endpoints** — `POST /api/v1/auth/password-set/request/` (throttled
  `password_set_request`, 5/hour, because each accepted request mails a real
  person), `GET .../validate/`, `POST .../confirm/` (throttled
  `password_set_confirm`, 20/hour). No auto-login on confirm: the caller already
  knows the password, so a session there would only add a fixation surface.
- **Mail** — the outbox gained a `user` subject family
  (`notifications/migrations/0007`), and `notifications/accounts.py` queues it
  through the same single send site as everything else, so it retries, records
  `sent`/`failed` and honours the development recipient override. This family
  deliberately has **no** unique constraint, unlike every other subject family:
  re-emitting an event must not send twice, but reissuing a link must. The
  single-use token is what guarantees one link cannot be used twice.
- **HTTPS guard** — `FRONTEND_URL` is new backend configuration, and a password
  link over plain HTTP is refused outside `DEBUG` rather than sent.
- **Audit** — `PASSWORD_SET_REQUESTED` / `PASSWORD_SET` actions and a
  `USER_ACCOUNT` target type, a deliberate extension of Unit 24's pinned
  vocabulary (`audit/migrations/0014`).

### HR's side

- Creating an employee queues the first link automatically. Gated on
  `not user.has_usable_password()`, so attaching an employee record to somebody
  who already has a password never mails them a reset link.
- `POST /api/v1/employees/{id}/password-set-link/` resends — the ordinary case of
  lost or filtered mail. Refused with a 400 for an account with no address or a
  deactivated one, and HR-only like the rest of the viewset.

### Frontend

`frontend/lib/password-set.ts` and three same-origin proxy routes (the Django URL
never reaches the browser), `app/(auth)/set-password/page.tsx` and
`app/(auth)/forgot-password/page.tsx`, and a link from the login page. The token
is read once into a ref and scrubbed from the URL on mount, so it cannot leak into
history or a referrer, and a pre-flight validates it before anyone is asked to
type a password.

### Retiring the demo accounts

`uv run manage.py retire_demo_users` deactivates the seven `@test.luanar` accounts
and strips their passwords, writing one `DEACTIVATED` audit entry each
(actor-less — a maintenance command, not a person). It is idempotent and
reversible with `--undo`.

Deleting them was the obvious answer and is not available: ~2 dozen foreign keys
point at `users.User` with `PROTECT` (audit, decisions, delegations/reassignments,
`RoleAssignment`, `SectionMember`, balance transactions), which
`test_deleting_the_account_instead_is_refused` pins. Deactivation achieves what is
actually wanted — no authentication, and no approver routing
(`workflows/services.py:344` gates on `is_active`) — with every row left in place.
`seed_dev_users` stays, because it also seeds leave types, entitlements, rules and
the financial year, and its `update_or_create` never touches `is_active`, so it
cannot resurrect the accounts.

### Defect found and fixed along the way

**Form-encoded employee creation produced a deactivated account.** DRF's
`BooleanField` sets `default_empty_html = False`, which is right for a real form
(an unchecked checkbox is absent and means False) and wrong for an optional API
field: any client posting multipart or form-encoded — `curl -F`, an HTML form, and
DRF's own test client by default — omits `is_active` entirely and DRF supplied
`False`. `EmployeeSerializer.create` then built the user with `is_active=False`,
and `users/tests.py::test_a_hr_created_employee_is_inactive_so_holds_no_approver_
roles` had come to *assert* that accident. Fixed with `OptionalBooleanField`
(absent means "leave it alone") and an `initial_data` check in `update()` so a
PATCH that never mentioned activation cannot flip an account back on. The old test
was rewritten: a new account now holds no approver roles because it has no role
assignment, not because it was switched off.

### Verification

Backend **1198 tests OK** (was 1151: 47 in `users/tests_password_set.py`, plus the
`is_active` regression pair). `makemigrations --check` clean; `migrate` applies
`users/0007`, `notifications/0007`, `audit/0014`. Frontend **574 tests OK** (was
560), `tsc --noEmit` and `eslint` clean.

### Still open

- **No self-service password change for a signed-in user.** This unit's confirm
  endpoint requires a live token, so a person who is already signed in cannot
  change their own password anywhere in the app. Not a gap in the flow above —
  there is no session holding a stale password, because there is no forced
  change — but a gap in the product, and worth its own unit. HR's **Send password
  link** works on an account that already has a password and covers it meanwhile.
  See `context/specs/26-unit-hr-user-onboarding.md` §16.
- **The seeded demo accounts are still active** — `retire_demo_users` is built
  and tested but has not been run against the development database, deliberately
  left for the user to trigger.

### Still open (operational, not code)

- **Live SMTP still unverified** — two separate checks, and one passing does not
  imply the other. `uv run manage.py sendtestemail <inbox>` (Django built-in)
  proves the transport — credentials, TLS, `From:` — but sends directly and
  bypasses the outbox. The pipeline still needs a real employee record (or
  `EMAIL_DEV_RECIPIENT_OVERRIDE`) and an outbox row observed going
  `pending → sent`. Credentials and `FRONTEND_URL` go in `backend/.env`.
- **A worker is still required** for queued mail and cron: `uv run manage.py
  qcluster`, or `NOTIFICATIONS_SYNC_SEND=True` for a single-process dev server.

## Completed — Change password for a signed-in user (2026-10-01)

The gap the set-password unit left open: an already signed-in person had no way to
change their own password. The confirm endpoint needs a live token, and
`/set-password` only accepts one, so the only routes were HR's **Send password
link** (which works, and is what covered it in the meantime) or a superuser again.

### The part that was not just a form

A password change is only worth anything if it ends the sessions it is meant to
end. This app issues a 24-hour `refresh` token, never rotates it, never
blacklists it, and signing out only clears cookies — the server revokes nothing
anywhere. So the tempting implementation, an authenticated endpoint that calls
`set_password`, would have changed the password and left every other device
signed in for up to a day. For the one case a person reaches for this in anger
("I think this is stolen") that is close to useless.

SimpleJWT already had the mechanism, unused: `CHECK_REVOKE_TOKEN` writes a
fingerprint of the password hash into every token and rejects tokens that no
longer match. Enabling it covers the access path, exactly, with no new column
and no clock comparison.

**The refresh path needed closing, and that was the actual work.**
`TokenRefreshView` hands the raw token to `TokenRefreshSerializer`, which mints
a new access token without consulting the user record at all. A refresh token
captured before the change would keep working *and* mint access tokens that pass
the check above — so the check the feature was built on would have had a hole
straight through it. `users/authentication.py` holds one
`assert_token_matches_password`, called from both places, deliberately: two copies
of a revocation rule is two chances to leave one of them out.

Worth recording: the first attempt used a `password_changed_at` watermark and an
`iat` comparison, which a test caught immediately. `iat` is second-granular, so
anyone who changed their password and signed in again within the same second
would have been refused their own new password. The hash fingerprint has no such
window, and needs no column. The invented field was dropped.

### The endpoint

`POST /api/v1/auth/password-change/` — the one password endpoint that is not
token-based. No token means no proof, so the **current password is re-checked**:
without it, a borrowed access token could rotate the account's password and lock
the real owner out of their own leave history permanently. That check also
forces two rules the form could not:

* the new password must differ from the current one, which
  `AUTH_PASSWORD_VALIDATORS` does not cover (Django's
  `UserAttributeSimilarityValidator` compares username, name and email, never the
  password being replaced);
* throttled **per user**, not per IP, at 10/hour. The thing being guessed is one
  person's password, and a shared office address would otherwise let one
  person's attempts lock every colleague out of changing theirs.

Also: `validate_password` runs *before* `set_password`, so the validators see the
old hash; outstanding `PasswordSetToken`s are invalidated, so a set-password link
that leaked cannot outlive a deliberate change; and the caller's own token dies
too, which is why the frontend clears its cookies and returns to sign-in.

### The account surface

`/dashboard/account` — a **My Account** nav item below the role-specific items
rather than inside the HR group, since it is the one destination that does not
depend on what the person can do. This is the app's first account page, so it is
a page and not a header dialog: somewhere to put the rest of it later without
renavigating. `tests/dashboard-shell.test.tsx` previously asserted that no
"Account" or "Settings" item existed; that assertion's intent inverted, so it was
replaced with positive ones rather than dodged by picking a different label.

The form reports a wrong current password on the current field and a validator
message on the new one, and says up front that this signs every session out
rather than after the fact. On success it navigates to `/login?changed=1`, which
explains the sign-out — otherwise the change reads as a random logout.

### Two defects found

**An expired delegation window broke an end-to-end test.** `DelegationJourneyTests`
hard-coded a delegation for 2026-09-21 → 2026-09-30, and delegations only cover
an approver while in effect, so the test began failing the day the window passed
— as `not_current_stage`, which points at the approval chain and not at an
expired delegation. The window is now relative to today. Pre-existing and
unrelated to this unit; it surfaced in the full run.

**`readMessage` in the new client helper could have lost the error text.** The
first draft read the field to blame and the message through two separate lookups,
and a mismatch arrives under `confirm_password` but belongs beside the *new*
password — so the message lookup found nothing and the user would have seen a
generic failure. Both are now read as a pair.

### Verification

Backend **1233 tests OK** (was 1198: 35 in `users/tests_password_change.py`).
The suite's heaviest test is `SessionEvictionTests`, which mints a token, changes
the password, and requires rejection through **both** the access and the refresh
path — that pair is the property worth having tests for. `makemigrations
--check` clean; one migration, `audit/0015`.

Frontend **603 tests OK** (was 574), across three new files: the form
(11), the client helper (10), the proxy (6). `tsc` and lint clean.

### Still open

- **Logout still revokes nothing server-side.** A refresh token survives "sign
  out" for up to 24 h. A password change is now the way to actually end
  sessions, which is a strange thing for a *logout* button to be better at.
  Fixing it properly means `token_blacklist` plus rotation, which changes
  behaviour for every client — deliberately not done here.
- **The demo accounts are still active**; `retire_demo_users` is built and tested
  but has not been run against the development database.

---

## Live SMTP and real-employee run (2026-10-01)

The transport and the two-recipient fan-out are now verified against a real
relay, and the run turned up three defects worth recording.

### `croniter` was missing, which silently stopped all delivery

`qcluster` died on boot with `ImportError: Please install croniter to enable cron
expressions`. The effect was worse than a crash: the `django_q.Schedule` row that
runs plan housekeeping is a cron expression, so without `croniter` the worker
never started, and every queued notification sat `pending` with nothing to retry
it. A `password_changed` row added during the smoke test was the evidence — it
never moved off `pending` until the dependency was added. Now declared in
`backend/pyproject.toml`; `uv sync` restores it.

### The set-password page reported live links as dead

Both real links were verifiably fine — the database said `LIVE`, and
`GET /api/v1/auth/password-set/validate/` returned `{"valid": true}` for the exact
token — yet the page showed "This link is no longer valid".

The cause was in `frontend/app/(auth)/set-password/page.tsx`. The page scrubs
`?token=` from the address bar so the secret cannot leak into browser history or
a `Referer` header, and it re-derived the token from `useSearchParams()` on every
effect run. `history.replaceState` does not merely change the address bar: the
Next.js router then reports **no token** on the next read, so the second read was
`""` and the page declared a good link dead. The one-line fix reads
`rawToken || tokenRef.current`, so the token captured at mount wins over the
post-scrub empty read and the ref stays the single source of truth for both
validate and confirm.

It survived a full green suite because the tests mocked `useSearchParams` to a
**constant**, so the token never disappeared. The regression test added in
`tests/password-set-pages.test.tsx` now returns the token once and empty
thereafter, mirroring the browser, and asserts both that the form stays usable and
that confirm still sends the original token. Reverting the one-line fix makes it
fail, so it is a real guard. Frontend is now **604 tests** (was 603).

### A missing fingerprint claim was a way around password revocation

`CHECK_REVOKE_TOKEN` covers the *access* path, and SimpleJWT's built-in check
treats an absent fingerprint claim as a mismatch. `users/authentication.py` — the
shared check the custom refresh view calls — explicitly **allowed** a claim-less
token, on the reasoning that rejecting one would sign everyone out on deploy. That
made the two paths disagree in the one direction that matters: refresh accepted a
claim-less token and minted a *fresh* access token stamped with the current
fingerprint, which then passed the access check. A token captured before a
password change survived the change by that route, which is the single thing the
setting exists to prevent. The permissive branch is gone, so both paths reach the
same verdict; `MissingFingerprintTests` pins all three shapes (refresh rejects,
access rejects, and a claim-less token cannot outlive a change). Verified by
temporarily restoring the branch: refresh returned **200**. Backend is now
**1236 tests** (was 1233).

The old justification did not hold anyway — the app is stateless JWT, so there
are no server-side sessions to migrate, and this is pre-production.

### What the run proved, and one trap it could not

Asante Kolowiko applied for 2026-10-08 → 2026-10-15 (6 working days, FY
2026-27), and all four stages approved in order, the last by the DVC. Audit
records `password_set` twice, then `submitted`, four `approved`, and
`document_generated`. The `application_finalised` outbox row went `sent` with an
empty error.

The finalised row lists **only the owner**, and that is by design rather than a
bug: `notifications/services.py` keys one row on
`(application, kind, cycle, role_label)` recording the owner, and passes the full
recipient list into the queued task, which sends one message addressed to both.
Re-deriving the list for that exact event returns
`['asantekolowiko@gmail.com', 'echotask.dev@gmail.com']`.

But the SMTP account *is* the second address, so the final approver's copy was a
message from himself to himself: the relay accepted it, the row said `sent`, and
the mail landed in **Sent** rather than the Inbox. It is now in
`DEVELOPER-GUIDE.md` as a standing rule — the sender must differ from the
recipients, and a correct `sent` row is not evidence that a second recipient got
anything, because only the owner is recorded on the row.

---

## Completed — Vercel design mechanics (2026-10-01)

Applied the design mechanics extracted in
`context/vercel-design-system-analysis.md`, keeping the LUANAR identity.

### What changed

**Geometry (WS1).** The radius ladder `6/8/12/16/20/24` was replaced by a flat
scale: `4px` (`xs`/`sm`, plus the calendar cells), `6px` (everything from `md`
up, and `control-radius`), and `9999px` for genuine circles. `lg` through `4xl`
are kept as aliases so the ~256 call sites that name them keep resolving.
Verified in the compiled CSS that `rounded-md`, `rounded-lg` and `rounded-xl`
all emit 6px. `--radius-calendar` drops to 4px so a calendar cell is a square,
not a pill.

**Depth and stacking (WS2).** The slate-tinted shadows were replaced by the
border-first spec: `card`/`subtle` carry only a soft drop, `hover` adds a ring
plus lift, `dropdown` and `modal` carry the measured overlay values. The shadcn
`2xs`–`2xl` names alias onto these, with `sm`/`md` mapped down. Added named
z-index tokens so an overlay can never land under a dialog: `z-header` 75,
`z-popover` 100, `z-modal` 1000, `z-toast` 1100. The eight ad-hoc `z-50` call
sites in the overlay primitives now use those names.

**Focus (WS3).** One `focus-ring` utility, keyboard-only, applied through
`@utility` so it composes with variants: an opaque white inner ring then LUANAR
blue at 4px. A `ring-offset` was deliberately dropped because the offset colour
breaks on transparent parents. Invalid fields get the same two layers in red.
Six separate `ring-2 ring-offset-2` variants were removed.

**Motion, spacing, type (WS4).** `--duration-base` is 200ms, matching the
spec's stated feedback timing, and the interactive primitives were moved off
`duration-fast`. Added `--space-band` 40px, `--space-field` 48px and
`--space-bleed` 64px for large screens. `text-xs` is 12px, not shadcn's 13px,
which brings the 166 existing call sites to the documented caption size.
`leading-tight` is 1.2 per the spec's display rows.

**Primitives and touch (WS5).** Cards are 6px with `p-6`, and an interactive card
lifts 2px on hover (with a `motion-reduce` opt-out). Badges and the five
hand-rolled status pills are 4px. Fixed the `draft` badge tone, which
referenced `bg-surface-secondary` -- a token that has never existed, so draft
badges had no background at all. Added a 44px touch-target floor below `md`,
scoped so it does not apply inside `.overflow-x-auto`: those tables are
desktop-density layouts read sideways on a phone, and growing their actions
would triple the row height.

**Breakpoints (WS6).** `sm` 640 → 600px, `md` 768 → 960px. `lg` is unchanged at
1024px because 27 call sites depend on it and the third-column layouts are
genuinely desktop-only. The 960px choice matches the wide data tables: a tablet
in landscape is still a phone-sized reading experience.

**Mobile drawer (WS7).** `useIsMobile` (a `matchMedia` subscription that returns
`false` until mounted, so the server renders the desktop shell and there is no
hydration flash), plus a hamburger in the header opening a Radix `Dialog`
drawer. The rail and the drawer render the same `NavLinks` list, so a route
cannot exist in one and not the other. `sidebarOpen` and `drawerOpen` are
separate states. The drawer closes on Escape, the backdrop, its own close button,
and a route change -- the last handled by adjusting state during render rather
than in an effect, which is both lint-clean and avoids a second render pass.

### Verification

Frontend 610 tests OK (78 files), typecheck clean, lint clean, production build
clean. Six new drawer tests cover open, shared destinations, labelling, Escape,
the close button, and route-change dismissal. The `matchMedia` mock in
`tests/setup.ts` gained a `setNarrow` control so a test can cross the
breakpoint; it still reports `false` for every non-`max-width` query, which keeps
the desktop baseline the rest of the suite is written against.

Three findings worth keeping. The dev server accepted an invalid
`has-focus-visible` pseudo-class without complaint, and only the production build
surfaced it as a CSS parse warning; the utility is now plain `:focus-visible`.
A stale `.next` cache held both the old and new radius values at once, so
verifying token changes means clearing `.next` first, or reading which chunk a
page actually served. And the four heaviest form suites (`plan-form`,
`employee-form`, `delegation-form`, `cover-request-form`) exceed the 5s per-test
default whenever the machine is loaded: they pass in isolation and fail as
timeouts under contention, and they failed *worse* on the pre-change baseline
during the same contention (9 failures vs 8). The suite's own output flags the
cause — "create it once per worker with `pool: 'vmThreads'`... or
`isolate: false`" — and the fix is the config change it suggests, not a code
change here. Do not read a timeout in those four files as a regression without
re-running them on a quiet machine.

### Deliberate deviations

- LUANAR blue `#0097F0` replaces `#0070f3` in the focus ring. LUANAR identity wins.
- Card shadow drops the spec's `0 0 0 1px` ring, because the card already draws a
  real 1px border and both would render a 2px edge.
- No hero gradient. `ui-context.md` prohibits gradients on ordinary UI surfaces,
  and this app has no marketing page to justify one.
- Geist Sans is kept for headings, though the spec pairs headings with Geist Mono.
- `9999px` is limited to genuine circles. The spec reserves it for pill
  CTAs; here a pill reads as a control, and status is a label.

---

## Leave application moves into an overlay on the applications list

Applying for leave no longer navigates. `/dashboard/leave/drafts` stays where it
is and the whole three-step journey — details, review, confirmation — runs inside
a centred modal above it, so the user's list is never torn down mid-application.
This is the pilot for the same pattern on Leave Day Plans and Cover Requests,
which still render as full pages.

Four decisions set the shape:

- **Leave only.** Plans and cover are left alone until the pattern is proven.
- **A wider centred modal**, not a drawer. It reuses `DialogContent` at
  `max-w-2xl` with a scrollable body, matching the app's existing dialogs.
- **All three steps in one overlay.** The review and confirmation steps are
  stages, not pages, so the flow never leaves the list.
- **The open application lives in the URL**, as `?compose=1`,
  `?edit=<id>`, or `?edit=<id>&stage=review|done`.

### URL state, and why the old routes redirect

Lifting the open application into the query string is what makes a refresh
resume the same draft instead of starting a new one, lets the browser Back
button step out of the overlay, and keeps the application deep-linkable. The
existing entry points are preserved as thin redirects so nothing that links
there breaks:

| Old route | Redirects to |
|---|---|
| `/dashboard/leave/new` | `/dashboard/leave/drafts?compose=1` |
| `/dashboard/leave/[id]/edit` | `/dashboard/leave/drafts?edit=<id>` |
| `/dashboard/leave/[id]/submitted` | `/dashboard/leave/drafts?edit=<id>&stage=done` |

`/dashboard/leave/[id]/review` keeps its page, since `ReviewSummaryClient` is
still the shared review component and a direct link should render standalone.
Notification emails contain no dashboard URLs, so nothing external depended on
these paths.

The sidebar's "New Application" item, both `New Application` buttons in the
list, and each card's Edit and Review actions all push the query string rather
than a path. `ApplicationCard` takes an optional `onEdit`; when it is absent the
original `<Link>`s render, so the standalone page and the list share one
component.

### Shared extraction

The overlay and the standalone pages render the same components rather than
forking them, so the two cannot drift:

- `LeaveReviewPanel` — the review step, used by both. `onEdit` and
  `showBackLink` let the overlay swap the back links for buttons that change its
  own stage instead of navigating.
- `LeaveSubmissionResult` — the confirmation. `onDone` replaces the link row
  with a single action, and `onNotSubmitted` keeps the standalone page's
  redirect-to-review behaviour while the overlay only shows a message, since a
  redirect would tear the dialog down.
- `useSubmitLeaveApplication` — the submit transition, extracted because the
  422-issues and 409-already-submitted branches are easy to get subtly wrong and
  were previously duplicated in intent.

`LeaveApplicationForm` gained `onContinueToReview`, `onDraftCreated`, a
`forwardRef` handle exposing `flush()`, and `hideActions`. Its own Review button
still calls `router.push` when no `onContinueToReview` is given, so the
standalone pages are unchanged.

### Two bugs found on the way

**Autosave lost the last keystrokes.** `useAutosaveDraft`'s effect cleanup only
cleared the pending timer, so any change inside the 800ms debounce window was
discarded on unmount. A full-page form mostly hid this; the overlay unmounts the
form on close, which makes it routine. The hook now tracks pending state and
exposes `flush()`, which the overlay calls before closing and on Escape. A test
pins the old behaviour as unmount-without-flush so the reason it exists stays
visible.

**Select menus rendered behind the dialog.** Radix portals to `<body>`, so
`SelectContent` is a sibling of the dialog content, not a child. With one
`z-modal` value for both backdrop and content, the leave-type dropdown painted
*under* the modal. `globals.css` now splits `z-modal-overlay` / `z-modal` and
adds `z-portal-above` for any primitive that opens from inside a dialog. A
regression test asserts the select content carries that class.

The document-removal confirm was also `window.confirm`, which browsers suppress
in some contexts and which cannot be styled; it is now the app's `AlertDialog`,
its first consumer.

### Verification

Frontend 628 tests OK (79 files), typecheck clean, lint clean, production build
clean. New coverage: 9 overlay tests (stage transitions, deep links into review
and done, URL rewrite on draft creation, close reporting, the z-index guard), 5
list tests for the new overlay entry points, 4 autosave tests for `flush`, and
the uploader's confirm rewritten against `AlertDialog`.

One note for the next round: `useSearchParams` in `ApplicationsList` requires the
`<Suspense>` boundary the drafts page now provides, or the production build
fails during prerender. The same applies to any host whose route is
prerendered — but only to those. The cover overlay, added later, reads search
params on routes the build marks dynamic, so it needs no boundary. Check the
build output for `ƒ` before adding one.

## Cover request moved into an overlay

**Why.** `CoverPanel` rendered `CoverRequestForm` inline, permanently expanded
above the delegation table, so the list the user came for was pushed below the
fold on both of the panel's hosts. It was the only form in the app already
rendered next to its own list, which made it the cheapest real test of whether
the leave overlay pattern generalises.

**What changed.** Two new client components. `CoverRequestSection` owns the
`?cover=new` open state and renders the trigger; `CoverRequestOverlay` is the
dialog and holds the in-place confirmation. `CoverRequestForm` gained optional
`onSubmitted` / `onCancel` props and otherwise did not change: with no
`onSubmitted` it still calls `router.refresh()`, so the inline rendering path
and its five existing tests were untouched.

`CoverPanel` stays a server component and simply renders the new section in
place of the form card, so `/dashboard/cover` and the Approvals Cover tab needed
no changes. The section derives its query from `useSearchParams` rather than
hardcoding a path, so opening the request from the approvals tab keeps
`?view=cover` instead of clobbering it.

**Verification.** Frontend 639 tests OK (80 files), typecheck clean, lint clean,
production build clean. Ten new overlay tests, plus the shared `next/navigation`
test mock gained a `useSearchParams` default (closed), which is what the three
`approvals-workspace` cover tests were missing.

**Notes for the next round.** Unlike the leave flow, this needs no
`useSubmitLeaveApplication`-style hook and no imperative flush handle: a cover
request is a single POST with no draft and no review step, so the pattern
degrades cleanly to one stage. Two things worth carrying forward. First, the
confirmation state lives in the component that only mounts while open, so
closing discards it — putting it in the always-mounted parent resurrected the
previous request's confirmation on reopen. Second, `DateRangePicker` needed no
clipping fix after all: `PopoverContent` wraps a `PopoverPortal`, so the
calendar renders in `<body>` and `overflow-y-auto` on the dialog cannot clip it.
The `z-portal-above` work already covered the stacking.

No `Suspense` boundary was needed here, unlike `/dashboard/leave/drafts`: every
cover host resolves the user through `cookies()`, so the build marks
`/dashboard/cover` and `/dashboard/approvals` dynamic and there is no static
shell to defer the client component out of. If either route ever becomes
prerendered, the section needs wrapping.

Still open from the same review: the leave overlay's stage changes are local
state, so the URL is not rewritten on form→review or review→done, and
`LeaveSubmissionResult` still defaults to a redirect when it is handed no
`onNotSubmitted` callback.

## Small HR admin forms moved into overlays

**Scope.** Leave types, public holidays, and financial years — the three admin
forms that are two or three fields each. Employee, team, and the leave-document
template editor were deliberately left as pages: at 288, 497, and 422 lines they
would be a scrolling form inside a scrolling dialog, which is worse than the
page they replace. Entitlements (4 controls) and leave rules (7) sit on the
border and want their own look.

**The shared pieces.** `useOverlayParam` turned out to be the part actually
worth generalising, not the dialog. Every overlay host needs the same five
things: read the key, treat `new` as create and anything else as a row id, push
on open, and on close step back through history with a replace fallback for a
direct visit to the deep link. `AdminFormOverlay` is then only dialog chrome
plus the not-found escape hatch. Three thin sections — `LeaveTypesSection`,
`HolidaysSection`, `FinancialYearsSection` — render their own form.

**No per-record fetch.** The three tables already carry everything each form
needs (`name`/`code`, `name`/`date`, `start_date`/`end_date`/`is_active`), so
edit mode resolves the row from the list already on screen. That removes the
`getLeaveType(id)` call, the `notFound()` path, the loading state, and any
need for a `Suspense` boundary — the build marks both list routes `ƒ` dynamic
anyway because they resolve the user through `cookies()`.

**Row affordances.** The row name stays a real `Link` to the old `[id]/edit`
route, which is now a redirect shim, so middle-click and copy-link keep working
and it lands on the same overlay. Only the pencil becomes a button, and only
when the table receives `onEdit`; `EditActionLink` gained a sibling
`EditIconButton` rather than a changed signature, because five other tables
depend on it. The icon button's label names the record — eight rows of an
unnamed "Edit" button are indistinguishable to a screen reader.

**Shims keep the role guard.** All six routes (`new` and `[id]/edit` for each
area) still resolve the user and check `role !== "hr"` before redirecting, so a
non-HR user following a stale link lands on `/dashboard` rather than bouncing
through a list page that would refuse them anyway.

**The `?year` filter.** The calendar page is the one host with a filtered list,
and it produced two states that were reachable but unresolvable. A deep link to
a holiday the filter excludes found no row, and a holiday created while filtered
could be invisible afterwards, reading as a failed save. Neither is papered over
by clearing the filter — an admin who narrowed the view would lose it without
being asked. Instead the overlay explains the case and offers "Show all years".
The filter form is passed into `HolidaysSection` as a slot so it stays between
the header and the table it narrows.

**Financial year activation.** Activating a period deactivates the current one,
which is easy to toggle by accident in a two-field dialog. The dialog
description now states the consequence, and only when the edited record is
currently active, so the warning is not noise on an inactive period.

**Verification.** Frontend 671 tests OK (82 files), typecheck clean, lint clean,
production build clean. Twelve hook tests and twenty section tests are new. The
six form tests and three table tests that already covered these components pass
untouched, which is the evidence that the new `onSuccess` / `onEdit` props
genuinely default to the old behaviour rather than quietly replacing it.

**Two things worth carrying forward.** JSDOM's `window.history.length` only
grows within a test file and `replaceState` cannot truncate it, so any test
touching the `back`-versus-`replace` branch has to override the property
directly. And the `getByLabelText` on an element that should be absent throws
rather than returning null — `queryBy` is required to assert absence.

## Leave overlay follow-ups: stage in the URL, and no stray redirect

Two loose ends from the leave overlay work, both found on re-reading the code
rather than by a failing test.

**Stage moves never reached the URL.** The overlay's form → review → done
transitions were local state, so `?edit=<id>&stage=review` described the stage
only on entry. Stepping back to the form, or submitting to the confirmation,
left the address bar describing a stage the dialog was no longer showing. The
overlay now reports transitions through `onStageChange(stage, applicationId)` and
the host rewrites the URL. The overlay's outer wrapper already keys on
`initialStage`, so the rewrite remounts the inner component and the URL becomes
the single source of truth rather than competing with local state.

**The rewrite has to be a `replace`, and that is load-bearing.** Opening the
overlay pushes one history entry and `close()` steps back exactly once. A push
per stage would make the first close press look broken — the dialog would still
be open, one stage back — so the host replaces. There is a test that opens,
visits review and done, closes, and asserts one `back()` and no `push()` at all.

**The reported id matters for the create flow.** `?compose=1` carries no
application id, because the draft does not exist yet. The report therefore
passes the id along, and the host prefers it over anything already in the URL;
otherwise a create flow could never name its own draft.

**A default redirect that fired inside a dialog.** `LeaveSubmissionResult`
redirected to the review screen when the application was not submitted, and the
dialog case inherited it: a submit that came back not-submitted would navigate
the page out from under the confirmation the user was reading. The default is
now a no-op, which leaves the in-dialog message in place, and only the
standalone page opts into the redirect. Inverting the default rather than
passing a no-op callback from the overlay means the safe behaviour is what you
get by forgetting to think about it.

**Memoising `target`.** The new callback depended on an object literal that was
rebuilt each render, so `useCallback` never memoised and eslint flagged it.
Wrapping the derivation in `useMemo` and depending on the id instead of the
object fixed the warning properly rather than silencing it.

**Verification.** Frontend 681 tests OK (83 files), typecheck clean, lint clean,
production build clean. Ten new tests: three on the overlay's stage reporting,
one on the no-op default, six on the host's URL contract.

## HR registry overlays: entitlements, leave rules, approver roles

Wave 1 of the admin forms that were still whole pages. Entitlements, leave rules
and approver roles all moved to the same overlay host as the leave types,
holidays and financial years, and the six routes they used to own now redirect.

### The shared pieces the three waves needed

**`AdminFormOverlay` gained a `size`.** The first wave inherited whatever width
`DialogContent` defaults to, which was right for a two-field form and wrong for
the entitlement form's date range. `sm` stays at the default so a converted form
is a visual no-op, `md` and `lg` widen the dialog and cap its height with
`overflow-y-auto`, because a form that scrolls inside a dialog has to say so
visually or the submit button reads as missing. The height cap is applied
unconditionally so switching targets cannot change the dialog's height.

**`AdminFormOverlay` gained a `targetKey`.** The overlay keyed its inner wrapper
on the dialog title, so two records with the same title — "Edit rule" twice on
one page — reused the mounted form, and because the forms seed with
`defaultValue` the second record opened showing the first one's values. Entitles
are the sharp case: two bands can read alike in the table and differ by days.
The caller passes the record id and the wrapper remounts on it. Two tests pin
this, one of which uses an identical title on both renders, since that is
precisely the case a title-based key cannot distinguish.

**`RowActionsMenu`, built but not adopted.** `row-action-menu.tsx` would have been
the popover-shaped version of this, but a row's actions are a menu, so it is a
Radix `DropdownMenu` with an accessible label naming the record, an optional
heading, and a separator before the first destructive action. It is not on any
table yet: adopting it changes every table's interaction at once, which is a
separate piece of work from having the component.

**A new `@radix-ui/react-dropdown-menu` dependency** for the above. This is the
only new package.

### What each page keeps

The filter controls stay on the server page and pass through as a slot, because
they are GET forms the page owns while the header, table and overlay belong
together in the client section. The clear-filters escape hatch is a `href` for
the same reason a callback cannot cross the boundary: `LeaveRulesSection` takes
`clearFiltersHref` and pushes it.

Entitlements' `?grade` is a lookup panel, not a list filter — it feeds the
durations the other columns show — so it is untouched. Leave rules filter on
`?effective` and `?leave_type` and both survive opening an overlay. Roles are not
filtered.

The institution-wide holder block on the roles page stays on the page. It is a
relationship rather than a field of a role, and it has to stay visible next to
the table that assigns it.

### Two bugs the new tests found

**The financial-year warning was on the wrong rows.** The dialog warned when
editing the period that was *already* active. That row's checkbox is already
ticked, so there is nothing to deactivate and the warning was noise; the two
cases that silently retire a live period — creating a period, or activating an
inactive one — said nothing. The condition is now `isCreate || !is_active`, and
the two cases get different sentences, because "activating this period" is wrong
for a record that does not exist yet.

**`leaveRuleStatus` dragged `next/headers` into the browser bundle.** The rule
table is a client component and imported the helper from `lib/leave-rules.ts`,
which imports `api-client`, which reads cookies. This is invisible to `tsc`,
lint and Vitest — all three were clean — and only the production build caught
it, so it is worth naming as a class: any client component importing a value
(not a type) from a server data module is a build break. The helper moved to
`leave-rules-client.ts`, which is browser-safe, with a re-export left behind for
the server callers and tests. This is the same split `historyScopeLabel` already
uses in `approver-roles-client`.

### And one the tests did not catch

**A holiday created under an active `?year` filter vanishes silently.** The save
succeeds, the row is created, and it is absent from the table, because the filter
is applied server-side and the new date falls outside it. That reads as a failed
save. The section now keeps the created id and derives visibility from the list
the server sends back — not from the date the admin typed, so it stays correct if
the filter ever widens — and shows the explanation plus "Show all years" only
when the row really is missing. A holiday created inside the filtered year says
nothing.

### Verification

Frontend 713 tests OK (85 files), typecheck clean, lint clean, production build
clean. Thirty-two new tests: twenty-one covering the three sections end to end
through the URL, eight on the overlay's sizing and remount key plus the row
menu, and three on the two behaviours above. Two existing tests asserted the
financial-year warning was correct and were rewritten, because they were the
reason it was wrong.

## Delegations, teams and employees move into overlays

Three more lists lose their create page: a new delegation request, a new team and
a new employee are now dialogs on the list, matching the registry work. Each
list keeps its own filter, and each `new` route survives as a guarded redirect so
old links still land somewhere.

| List | Param | Size | Filter preserved |
| --- | --- | --- | --- |
| Delegations | `?delegation=new` | `md` | `?state` tabs |
| Teams | `?team=new` | `lg` (scrolls) | active / retired |
| Employees | `?employee=new` | `md` | `?search` |

Each form grew an optional `onSuccess`/`onCancel` pair. Given them it reports
the save instead of navigating; left out, it navigates exactly as before, which
is what the standalone pages still need — so `teams/[id]/edit` and the employee
profile page are untouched.

### What stayed a page, and why

Delegations have no edit form at all: approving, rejecting and cancelling are
done on the record's own page. Teams and employees keep their own pages for the
same reason — what those pages show is exactly what a dialog would have to leave
out. A team's roster is managed on the team's page, and an employee profile is a
record of one person with their grade history and document trail, not a short
form. A dialog that dropped those fields would be a worse version of the thing
it replaced.

### Three different "saved, but it is not in this table" answers

A create that succeeds can still leave no new row on screen, because each list
can hide a row for a different reason. All three sections keep the created id
and check it against the list the server sends back after the refresh — never
against the submitted values, so the message cannot disagree with the table.

- **Delegations** are created `requested`, so on the `?state=active` tab the row
  is absent. Offers "Show all states".
- **Teams** get no warning at all, and that is deliberate rather than an
  omission: a new team is a draft, and the list read excludes only *inactive*
  teams, so a draft is in the table under both filters. The warning would be
  code that can never fire.
- **Employees** have two causes and the copy names both, because they call for
  different actions. With a `?search` active it says so and offers "Clear
  search"; with no search it says the list shows the first *n* of *total* and
  offers nothing, since clearing an innocent search would be a red herring. The
  header always states which slice is on screen, so the table is never ambiguous
  about how much of the staff is hidden.

### Employee pickers were silently truncated

Four forms picked an approver, a delegate or a reviewer from
`listEmployees()`, which reads one page — twenty people. Past the twentieth
employee the picker was empty with no explanation, and the reviewer could not be
found at all. Delegation create, delegation review and reassignment create now
use `listAllEmployees()`, which pages through to the end. The cost is paid up
front: the delegations list fetches the whole staff on every load. That is the
deliberate trade for a picker that is never quietly short.

### The `next/headers` trap again, and this time it was load-bearing

Wrapping `TeamTable` in a client section pulled it into the browser bundle, and
it imported `teamStatusLabel`/`teamStatusBadgeClass` from `lib/teams.ts`, which
imports `api-client`, which reads cookies. `tsc`, lint and Vitest were all
clean; only the production build failed. The helpers moved to
`teams-client.ts`, re-exported from `teams.ts` so the server callers did not
change.

I checked this one rather than assuming: reverting the import and rebuilding
reproduced the `next/headers` failure, and restoring it built clean. It is the
same split as `historyScopeLabel` in `approver-roles-client` and
`leaveRuleStatus` in `leave-rules-client`.

### One wrong assumption, caught by the tests

The teams test fixture used `key: "hod"` on an `ApproverRole`. The real field is
`code`, and the chain seeds a new step with `roles[0].code` — so the fixture
left the role select on no value, the submit never got past "every step needs a
role", and six tests failed for a reason that had nothing to do with the
overlay. Worth recording because it is the kind of gap that reads as a product
bug: the create form looked broken when only the test data was wrong.

### Verification

Frontend 740 tests OK (88 files), typecheck clean, lint clean, production build
clean. Twenty-seven new tests across three suites — eight each for delegations
and teams, nine for employees — plus two on `DelegationForm`'s callback mode,
covering: filters surviving the overlay, cancel stepping back rather than
leaving, refresh-without-navigation on success, each of the three
visibility-missing cases, list errors replacing the table while leaving the
create trigger reachable, and a failed option read still opening the dialog.

One harness note, since it cost real time: the mocked `next/navigation` router
has to drop the overlay param on `back()`. Without that the dialog never
unmounts, and Radix leaves the page behind it `aria-hidden` — so the post-save
alert renders but cannot be found by role. That is a harness artefact, not a
product failure, and the fix belongs in the mock.
## Verification repair (2026-10-02)

The tracker had been claiming a green suite for four commits. It was not.
`8d472b3` shipped **4 failing tests** and nobody noticed, because every
verification claim in this file predates it. Full suite on a fresh test
database: **1155 tests, 4 failures.** Root cause and repair below.

**Why they failed.** `8d472b3` removed the hard-coded fixture-registry
fallback from `leave/cancellations/providers.py::_deducts_annual_balance`,
leaving "no snapshot + no HR-configured rule → does not deduct". That was the
correct change — whether a leave type deducts annual leave is business data HR
owns, not a placeholder registry. Four tests in
`leave/tests/test_cancellations.py` still built an approved
`LeaveApplication` directly with `leave_type_id=1` and **no
`rules_snapshot`**, relying on the removed fallback to mean "annual leave,
deducts". They resolved to a restoration of `0` days instead of `5`, which is
the invariant-12.4 breach they were written to guard.

**The fix is the snapshot, not the fallback.** `CancellationBase` gained
`snapshot_for(start, leave_type_id)`, which builds `rules_snapshot` with the
**production** `build_rules_snapshot()` off the stub's own leave-type rules, so
the fixture cannot drift from what `submit_application` writes. `make_approved`
takes a `leave_type_id` and the snapshot is built for the type the row claims.

**A fifth test had been passing for the wrong reason.** With the snapshot in
place, `test_non_deducting_leave_type_returns_zero_restoration` started failing
— it flipped `leave_type_id` to compassionate *after* creation, relying on the
same removed fallback, and was only green because the fixture registry said id 4
does not deduct. It now asks for `make_approved(leave_type_id=4)`, so the
snapshot agrees with its own row. Worth recording: fixing a stale test can
unmask another that was never testing what it claimed.

**Doc drift that let it through.** `architecture.md` §12.3 and §12.11 still
said a section "accepts several members and the first to act claims it" — true
before `8d472b3`, false after it, since `Section.approver` is one FK. Corrected:
a step resolves to one named person, so a step whose approver is the applicant
has nobody left to act and is refused, not skipped. Two backend docstrings
(`workflows/services.py::replace_workflow_sections`,
`leave/tests/stubs.py::_active_user_id_for_role`) stated the same superseded
rule and were corrected with it.

**`--keepdb` is not safe here.** A reused test database reported **79 failures**
against a suite that is green on a fresh one: leftover rows are visible to the
next run, and suites that create configuration by id (approver roles, sections,
leave types) then fail on state they did not create. The README no longer
recommends it and now explains the delete-once step.

**Also corrected in the README.** It documented `seed_approvals_dev`, which
does not exist — it names `seed_dev_users` only, which creates no business
configuration — and it omitted the two facts that make a bootstrap superuser
usable: the email-as-username rule, and that `createsuperuser` leaves `role` at
`employee`, which redirects every `/dashboard/hr-admin/*` page.

**Verification.** Fresh test database: **1158 tests OK** (1155 + 3 new).
`check` clean, `makemigrations --check` clean. `leave/0017` applies and reverses
on the dev database. Frontend unchanged by this pass (66 files / 448 tests OK,
`tsc` and `eslint` clean).

## Unit 30 — Approver Applicants Skip Forward; Final Approvers Go to HR (implemented 2026-10-03)

Spec `context/specs/30-approver-applicant-routing-spec.md`. Requested: an approver
must be able to apply for leave. Their own stage, and every stage below it, is
skipped rather than routed to them or refused outright; if they hold the last
stage the application is handed to HR. Within one workflow, one employee sits on
one stage and one role on one stage.

**This reverses invariant 12.3 and migration `0017_drop_skipped_stage_status`,**
which dropped the `skipped` status on the reasoning that a section whose approver
*is* the applicant should refuse the submission. That reasoning was wrong about
one thing: refusing is not the same as deciding, and an applicant who holds the
final step would otherwise be stuck between a refusal and an unfinalisable
application. The user chose this explicitly over keeping the refusal, so 12.3 and
`tests_self_approval.py` were rewritten rather than worked around.

**Most of the rest already held** and was verified rather than rebuilt: approvers
could already submit, `policies.get_decision_authority` already blocks
self-approval independently of stage assignment, `user_may_act` already authorises
only the current stage, and `DatabaseWorkflowProvider` already reads the
application's own team. **No submission notification was added** — there is none in
this system to add to; only decision emails are registered.

Two constraints, `section_workflow_approver_unique` and
`section_workflow_role_unique` (migration `0024`). `Section.approver` stays
nullable so unstaffed draft steps remain legal, and the dev database had no
duplicates to clear. The admin needed **no** new rule: Django's cross-form
`validate_unique` reports the repeat on the `approver_role` field from the model
constraint itself. An earlier attempt to re-check it in `SectionInlineFormSet.clean`
was dead code and was removed — the test now pins what the constraint actually
produces instead of what the extra check would have produced.

`SKIPPED` status plus `ApplicationStage.skip_reason` (migration
`0025_application_stage_skipping`). Two distinct reasons, because they answer
different questions for a reader of the history: the applicant's own stage reads
*"Applicant cannot approve their own application."* and a stage below it reads
*"Applicant is a higher-stage approver."*

The applicant's stage is found by **resolving** the section the way
`resolve_section_approvers` does — the configured approver, or the sole
institution-wide holder — not by reading `Section.approver`. Reading the column
would have missed every institution-wide step, which is where the final
vice-chancellor step normally lives, and so would have missed the HR handoff
entirely.

The HR destination is **one more `ApplicationStage`**, not a flag: `section_ref =
NULL`, `role = "hr"`, `history_scope = "all"`, every active HR user other than the
applicant in `eligible_approvers`. Authority, history and the decision path are
then the code that already existed, because `get_decision_authority` resolves
through `user_may_act` to that snapshot. Excluding the applicant is what stops the
handover becoming a back door to self-approval; if that leaves nobody, submission is
refused rather than parked on a stage nobody may act on.

Two bugs surfaced only because the stub provider had to be kept faithful to the real
one, and both were real:

- `leave/services/workflow_gate.py` carried a **second copy** of the
  "no active approver" rule, and refused every skip. `assign_workflow` had its own
  copy. Both now exempt skipped stages, and the duplication is the reason the rule
  is worth stating once.
- `assign_workflow` set `current_stage` to `stages[0]` and
  `_next_activatable_stage` took `remaining[0]`. Both now go by status, so a chain
  that opens with skipped stages points at the stage somebody can act on.

Frontend: `skipped` added to `StageState` and `StageStatus`; both
`STATE_MARKER` records and `META_LINE` carry it; `skip_reason` is on both stage
payloads and rendered under the stage. `team-form.tsx` now refuses a repeated role
or approver before submit, naming the role or person, because the backend enforces
the same rule as a constraint and a database error naming a constraint tells HR
nothing. `tests/team-form.test.tsx` had been asserting the duplicate as *correct* —
that assertion was the bug, and it was replaced with the two refusal cases.

Verified: `workflows` 513 tests OK; `workflows` + `leave` 923 OK; frontend 66
files / 451 tests OK; `tsc --noEmit` and `tsconfig.test.json` clean; `eslint` clean;
`makemigrations --check` clean. Unit 28's commit (`e993ed5`) also records that the
verification gate was itself repaired before this unit, so these counts are from a
gate that had been failing silently for four commits.

## Unit 29 — One Department, Several Teams; One Chain Per Team (implemented 2026-10-02)

Spec `context/specs/29-multiple-teams-per-department-spec.md`. Requested: a
department must hold one or more teams, and each team uses its own workflow.

**Most of it already held.** Verified against the code rather than assumed:
`Team.department` is an FK with `related_name="teams"` (database-enforced
one-to-many), `Team.workflow` is a `OneToOneField` so a chain cannot be shared,
`TeamSerializer.workflow` is `read_only` with the inline `new_workflow` as the only
writer, and `DatabaseWorkflowProvider` resolves `team.workflow` — routing already
followed the team.

**The defect was one function.** `_mismatched_department_team` made a second
*active, in-force* team in the same department an activation-blocking
`department_conflict`. That check was the only thing stopping the configuration,
and it contradicted four docstrings that all say a department holds "one or more
teams" — including `Department`'s own rule that "one employee holds one role
across **every team** in the department", which presupposes more than one.

Its own docstring argued two active teams are "nearly always accidental". That is
a product judgment, and the product has now made a different one. The message it
produced was also self-defeating: *"If sharing it is intended, deactivate that
team first"* — so a department could hold several team records but never more than
one *working* team, which is not what "one or more teams" means.

This is Unit 28 §A pointing the other way: there the code under-delivered on the
docs, here the docs were right and the code refused.

Removed: `_mismatched_department_team`, the `department_conflict` issue, and the
dead `resolve_applicable_workflow` / `_employee_key` pair that resolved a chain by
free-text `(category, department)` scope — the model team routing replaced, whose
docstring admitted "retained for reference only, no longer calls this" and which
was reachable only from its own two tests. Also corrected the `providers.py` and
`assign_workflow` docstrings that still described a section as "a set of people".

`department_missing` deliberately **stays** (D2). A different rule: a team with no
department cannot be staffed at all, so removing the conflict check must not
remove that.

**Three tests added, because the configuration they cover used to be
unreachable.** Two teams in one department can both be activated; each employee is
materialised with their own team's step and the two chains share no section; and
one person cannot be appointed a *second* role on the department's other team —
though re-appointing the *same* role is allowed, since the rule is one role per
department, not one appointment per department. That third rule already worked
(`ensure_role_consistency` filters `workflow__team__department_id`) but was never
exercised while a department could hold only one active team.

No frontend change: `teams-client.ts` renders `TeamReadiness.issues[].message`
generically and never names `department_conflict`, so removing an issue code
cannot strand the UI.

**Verification.** Fresh test database: **1158 OK** (net −1 removed conflict test,
+3 new, −2 dead-routing tests). `workflows` + `leave`: 910 OK. `check` clean,
`makemigrations --check` clean — no schema change. Frontend unchanged: 66 files /
448 tests OK.

## Unit 28 — Hardening and Integrity Review (spec written 2026-10-02)

Spec `context/specs/28-hardening-and-integrity-review-spec.md`. **Not started.**
Chosen over the other two candidates because the verification gate was broken for
four consecutive commits and every verification claim in this file predated the
commit that broke it — evidence the per-commit discipline has a systematic hole,
not a one-off. Two features on top of an untrusted gate is how you get eight.

The pass targets one defect class, because it is the class that survives review:
**code that claims behaviour it does not have.** All three instances found on
2026-10-02 were that class, and all three were deletions rather than missing
behaviour — `row_version`, `leave/services/snapshots.py`, and the
fixture-registry fallback four tests were still leaning on.

Two contract questions answered during scoping, recorded so they are not
re-opened: the **edit/resubmit path is sound** (`LeaveApplicationSerializer`
marks every server-calculated field read-only), and **`WorkflowViewSet` is
correctly read-only** — it is the `README` that is wrong, documenting a `POST` and
a `PATCH` that return 405. The README's API table is also missing roughly eight
routed endpoints Unit 26 added (`teams`, `approvals`, `approver-roles`,
`campuses`, `role-assignments`, `section-members`, `departments`, and the
`leave-document-template` actions), so the whole table needs verifying endpoint by
endpoint against `config/urls.py`.

D3 in the spec is the one that addresses how this got here: findings are recorded
whether or not they are fixed, so a deferred item stays visible. The four defects
Unit 24 deferred as "out of scope (D10)" were named in prose and never revisited.

## Completed — UI/UX Premium Polish Pass (2026-10-08)

**What shipped (refinement `01-ui-ux-premium-polish.md`).** §3.5 — toasts + optimistic UI
(tier 1 cross-cutting). Form overlays (approved scope): **A1** HR admin users
(`AdminUsersSection` + `?user=new|id`, page+shims), **A2** plans workspace
(`?plan=new`, shim), **A3** HR reassignments queue (`?reassign=id` overlay with
on-demand employee fetch, `notFound` for stale ids, row actions via button when
overlay owns it), **B1** leave review moved to shim `?edit=<id>&stage=review` and
tests retargeted to `LeaveReviewPanel` (ReviewSummaryClient removed). Primitives
shared: `AdminFormOverlay`, `useOverlayParam` (back closes, edit from row). Keydebug
script removed from `app/layout.tsx`. §3.6–§3.10 remain.

**Verification.** Frontend: 882 tests passed (101 files), lint clean,
`tsc --noEmit` and `tsc --noEmit -p tsconfig.test.json` clean, `npm run build`
clean. Servers smoke-checked: shim routes emit Next redirect (meta refresh) and
overlay pages render under auth (parity with prior behavior; auth-guarded
index/shims keep original guards). No backend changes.

## Completed — Chain Stepper Component & Rollout (2026-10-09)

**What shipped (refinement `02-chain-stepper-rollout.md`, supersedes §3.1 of the
UI/UX polish unit).** One data-driven `components/ui/Stepper.tsx` implementing the
§2.1 contract exactly (`StepStatus`, `Step`, `StepperProps`) with six visually
distinct statuses, `orientation="auto"` (one DOM tree: vertical below `md`,
horizontal at `md`+, connectors switched by breakpoint), `size="sm"|"md"`,
`showAvatars`, and a per-step expandable `detail` accordion (button with
`aria-expanded`/`aria-label="<label> details"`). Accessibility: a single
`aria-current="step"`, `data-state` per node, the pulse is
`animate-pulse motion-reduce:animate-none`. All colour comes from existing tokens
— the §2.2 red literals are mapped onto `status-rejected`; no new colours.
`lib/chain-steps.ts` is the only domain-aware layer and now emits `Step[]` via
`chainFromTracking`, `chainFromWorkflow`, `chainFromPlanStages` and the new
`stepsFromCancellation`.

**Status mapping.** approval/tracking: approved→`completed`,
awaiting/pending→`current`, upcoming/waiting→`pending`, self-approval
skip→`skipped`, vacant approver→`blocked` ("No approver assigned"),
rejected→`error` ("Rejected"), returned/correction_requested→`error`
("Correction required"). Cancellation reuses the approval-chain logic over its
shorter snapshot. Acting assignments surface as an "Acting" badge plus the
contextual sublabel rather than the old inline label.

**Rollout.** §3.1 tracking (`TrackingView`), approver review (`approval-detail`)
and the two plans pages (`plan-detail`, `plan-approval-detail`, which already
consumed the old component); §3.4 cancellation (`cancellation-card` vertical and
`cancellation-detail-panel` vertical, replacing `CancellationStageStepper`). The
old `components/approvals/ChainStepper.tsx` and
`components/cancellations/cancellation-stage-stepper.tsx` were deleted, along
with the now-orphaned `STAGE_STATE_META` label map. §3.2 document version-history
dialog, §3.3 "Changes since your decision" card, §3.5 onboarding and §3.6
org-unit checklist target surfaces that are **not built** yet, so they are
recorded as not-applicable rather than invented; §3.7 stays badges. Display-layer
replacement only — no API/backend changes.

**Deliberate display delta.** The old current-step caption "Awaiting decision ·
assigned {time}" is replaced by the spec's context (role/designation) with the
assignment time preserved as `Assigned {time}` in the `sublabel`; the redundant
"Not yet reached" caption is dropped (position conveys it). Comments/rejection
reasons, timestamps and actor names all remain reachable, so nothing is lost —
the comment now lives in the step's accordion.

**Verification.** Frontend: 887 tests passed (101 files), `eslint` clean,
`tsc --noEmit` clean. `tests/stepper.test.tsx` (renamed from
`tests/chain-stepper.test.tsx`) covers all six statuses, both orientations,
`size="sm"`, `showAvatars={false}`, reduced-motion, the detail accordion, and all
four adapters; `tracking-view`, `approval-detail`, `cancellation-detail-panel`
and `plan-approvals-workspace` were retargeted to the new markup.
## Unit 31 — Annual leave is owned by the entitlement form (implemented 2026-10-05)

Spec `context/specs/31-entitlement-linked-leave-type-availability-spec.md`, branch
`feature/updated-hr-track`. The defect this fixes is one of sequence, not of data:
Unit 31's own D1 said HR picks a leave type while configuring an entitlement and that
**no `LeaveType` row is ever created**. So HR configured a band of annual-leave days
and then had to go to a *different* form to create "Annual Leave" before any employee
could select it. The two halves of the original request were both implemented and still
did not connect, because the join depended on a manual step in between.

**Annual leave is now provisioned by saving an entitlement.** `provision_annual_leave`
is idempotent, shared by the API and the Django admin, and creates the `LeaveType` plus
a balance-deducting `LeaveRule` capped at the band's days, auditing each row it creates.
`GradeEntitlementSerializer.leave_type` is now **read-only** and `EntitlementInput` no
longer carries it, so a client cannot ask for a different type and get one. The admin
form disables the field and `save_model` provisions inside the save's transaction, so a
half-provisioned band is never committed.

**Leave Types refuses annual leave on both write paths.** The API refuses to create any
type that would claim the annual identity and refuses to edit the canonical type on
**any** field — including `is_active`, which looks like an ordinary flag and retires
annual leave into an empty dropdown for every employee. `LeaveTypeAdminForm` applies
the same two guards. Other leave types stay fully editable, and the annual *rule* stays
editable under Leave Rules, which is where the day cap and balance behaviour belong.

**One thing deliberately not blocked.** `has_add_permission` was first made to return
`False` for the whole admin, on the reading that Leave Types should not create anything.
That was over-reach: maternity, paternity and compassionate leave still have to come
from somewhere, and removing every add left HR no way to create them at all. Reverted to
a form guard that refuses only the annual identity.

Canonical annual identity is matched through `find_annual_leave_type`, honouring code
`annual`, code `annual-leave`, and a case-insensitive `Annual Leave` name — a database
written before the canonical code existed holds annual leave under whichever one it was
given, and the previous commits on this branch had also drifted between `annual` and
`annual-leave`, so the guard had to accept both rather than pick one.

**Frontend.** The entitlement form drops its leave-type dropdown and its
`listLeaveTypes` fetch entirely and now says the band grants Annual Leave, linking to
Leave Rules. `leave-type-form` renders annual leave as a read-only panel pointing at
Entitlements. `leave-type-table` shows "Managed in Entitlements" and an "Edit days"
link on the annual row while other rows keep their edit action. `isAnnualLeaveType` in
`lib/leave-rules.ts` mirrors the backend's two-code rule.

The **empty-state copy and the entitlement table's fallback label** both said annual
leave is something HR adds, which is now wrong; the fallback reads "Annual leave"
rather than "Annual (untyped)".

**Tests.** One backend test, `test_hr_can_patch_leave_type`, patched *annual* leave and
asserted 200 — it was asserting the exact behaviour being removed, so it was rewritten
against maternity and the annual cases were added alongside it. A new
`LeaveTypeAdminFormTests` class covers the admin guards in both directions.
`tests/entitlement-form.test.tsx` is new and pins that no `leave_type` is sent.
`test_admin_save_provisions_annual_leave` had to build its own HR user: the admin test
class has no `hr_user` fixture.

Verified: backend full suite **1192 tests OK** (was 1192, net 0 — 21 added, 4 obsolete
annual-patch expectations replaced); `leave` alone 174 OK; frontend **67 files / 462
tests OK** (was 66/451); `tsc --noEmit` and `tsc -p tsconfig.test.json` clean;
`eslint` clean on every touched file; `manage.py check` and `makemigrations --check`
clean — no schema change.

## Phase 1 — Department removed; Team is the unit (2026-10-06)

**Database wiped and rebuilt from migrations.** Dropped and recreated `luanar_leave`,
then `manage.py migrate` from zero. That rebuild is not cosmetic: the previous `flush`
had removed the rows migration `0011` seeds, so the dev database no longer had the six
canonical approver roles and could not have built a chain. Migrating from zero also
proved the migration graph end to end. Final state: one superuser, zero employees,
campuses, teams, workflows, sections and holdings, the six shipped roles.

**Two real defects found and fixed while verifying.**

*Migration graph inversion.* `users.0009` depends on `workflows.0026`, so nothing
ordered `workflows.0014` after `users.0005` — and `0014` reads
`application__employee__employee_profile__team`. On any fresh database the test runner
died in `select_related` before a single test ran. Fixed by declaring
`("users", "0005_employeeprofile_team")` in `0014`'s dependencies; `users.0005` already
depends on `workflows.0010`, an ancestor of `0013`, so the edge cannot cycle.

*`workflow__team_id` is not a valid lookup.* Three call sites inherited it from a
mechanical rename. `Team.workflow` is a `OneToOneField`, so the reverse accessor is
`workflow__team__pk`. This was a 500 on any team create with a section approver and on
the eligible-approvers action — `services.ensure_role_consistency` and two lines in
`views.eligible_approvers`.

**One design decision the removal forced.** Team membership is now the eligibility rule,
so `create_team` could no longer succeed: it writes the team, then judges the named
approvers against membership they cannot have yet. Creating a team now places the people
it names on it (`_place_new_team_member`, `place_on_team=True`, create-only). Someone
already on a *different* team is refused and told to be moved first, rather than being
quietly moved — that would leave their old team staffed by people who can no longer be
eligible. Re-pointing a step on an *existing* team deliberately does not place anybody:
that is a separate edit to the employee record.

**A consequence worth recording.** `ensure_role_consistency` (one role per team) is now
unreachable. A team owns exactly one workflow, so `ensure_single_stage_per_workflow`
always fires first and subsumes it. Kept as a defensive guard rather than deleted, but
`test_one_person_holds_one_role_on_a_team` now asserts the rule that actually protects a
team. Related: because `EmployeeProfile.team` is a single FK, one employee can only ever
be appointed within one team — "the same office approves for two teams" now needs one
holder per team.

**Login defect.** `User` is `AbstractUser` with no `USERNAME_FIELD` override, so
`LoginView` authenticates `username=<email>`. The rebuilt superadmin had
`username="admin"` and could never log in. Aligned to the product convention
(`username == email`, as every fixture and the admin add-user form already do).

**Tests.** 32 test functions deleted, 20 added, net −12 (1192 → 1180). Deleted only the
Department CRUD suite, the `department_missing` readiness case, and tests whose entire
premise was a per-department rule; every routing, skip-forward, visibility, delegation,
eligibility, snapshot and history rule was re-expressed in team vocabulary, not weakened.
A team with no department is no longer a distinct readiness issue — `no_approver` already
covers it. `workflows/testing.py` exposes `campus_for`/`team_for` and
`make_approver(..., team=)`; `make_team` takes `campus=` instead of `department=`.

**Verified.** Backend full suite **1180 tests OK** from a freshly created test database
(after deliberately dropping `test_luanar_leave`, because two earlier subagent runs had
been reporting green against a stale database). `makemigrations --check` reports no
changes. Frontend **66 files / 448 tests OK**, `tsc --noEmit` and `eslint` clean.
Department pages, BFF routes, client, table, form and their test are deleted; the
eligible-approvers call is `?team=`; the approvals and document-template payloads use
`team`. Live smoke test against a running server: admin logs in, `/api/v1/departments/`
404s, and campus → employee → team-with-chain → validate → activate all succeed through
the API from the empty database, with both approvers landing on the team automatically.
Smoke-test rows were then removed, returning the database to bare.

**Left for later phases.** Team category, multi-workflow teams and a deliberate
cross-team approver model are Phase 2+ — an employee currently cannot hold a role on
more than one team.

---

## Phase 2 — Team category, multi-workflow teams, and the three levels of approver (backend)

**What the schema change says.** `Team.category` (`academic` / `administration`, model
default `administration`) decides whether a team is campus-based or institution-wide.
The pair is validated at service and serializer level and *not* by a database check
constraint — a backfill that sets `category` from an existing `campus` would be rejected
by the very constraint that is meant to describe the rule. `Workflow.team`
(`related_name="workflows"`, `SET_NULL`) makes workflow ownership a forward relation;
`Team.workflow` stays the one-to-one routing pointer, with its reverse renamed
`team` → `routed_by` so the two never collide. A team therefore owns many chains and
routes exactly one of them.

**Two new holding tables.** `TeamRoleAssignment(team, role, user)` and
`CampusRoleAssignment(campus, role, user)`, both unique on the (scope, role) pair and
both `clean()`-refusing institution-wide roles, retired roles, and inactive campuses.
Writing a second holder for the same role and scope is the *replacement*, not an error —
the screen is pick-a-role, pick-a-person, and asking HR to delete before they may change
their mind is a step that only exists to satisfy the database. Both appointments and both
replacements are audited as `TEAM`/`CAMPUS` target events.

**Resolution order** (`workflows.providers.resolve_section_approvers`): the section's own
appointee → team-wide holder → campus-wide holder → institution-wide holder *only* when
the routing team is an administration team (and a `team=None` lookup may reach it, since
institution-wide roles have no team). A campus-wide holding on an academic team no longer
silently serves an administration team, which is the whole reason the gate exists.
`section_resolution` is the same answer as display data and never raises, so a screen can
show "who would act here" without the lookup failing first.

**Lifecycle rules that changed with it.** `ensure_team_eligibility` now refuses an
institution-wide role on a non-administration team; `validate_team` exempts team- and
campus-wide holders from the `approver_outside_team` rule; `team_for_section` follows
`workflow.team` (ownership) rather than assuming routing implies ownership; and a team is
never allowed to adopt a workflow it does not own — the serializer refuses `workflow` on
create outright and on update unless the team already owns it.

**The chain endpoint is writable again.** It was read-only because a chain was written
with its team; now that a team may own several, each is configured on its own here.
`WorkflowWriteSerializer` takes `name`, `team` (create only) and `sections`, and
*refuses* `effective_from` and `is_active` by name — when a chain begins applying is
decided when the team that routes through it is activated, and switching a chain off is
retiring that team. `GET /workflows/?team=` is the team's own listing.
`TeamSerializer.category` carries **no** DRF default, because a field default is filled
in before `validate` runs and would make "a campus was sent but no category" look like
"an administration team was sent"; instead the category is inferred to `academic` when a
campus is present and no category was given, which is what the campus has always meant.

**Migration `0027`.** Adds both fields and both tables, then backfills: every routed
workflow adopts the team that points at it (otherwise every live chain would look
ownerless on the new team screens), and teams with a campus are marked academic. The
backfill is `RunPython` with a `noop` reverse, because there is nothing to undo that a
drop of the column would not do better.

**Fixture change.** `make_team` now sets `workflow.team` and derives `category` from the
presence of `campus`, so a fixture cannot build the one state a real write refuses.

**Tests.** Full backend suite **1182 tests OK** (`workflows` alone: 523). Rewritten:
`WorkflowEndpointTests` (create requires a team; HR creates and edits a workflow; a
chain cannot be adopted by another team; `?team=` filter; DELETE still refused) and
`WorkflowActivationEndpointTests` (scheduling and switching off a chain are named field
errors rather than 405s; a deactivated role is refused at write; two teams may own
chains over the same scope). `test_a_team_may_not_point_at_an_existing_chain` and
`test_a_workflow_sent_on_create_is_ignored` now assert a refusal rather than a silently
ignored field.

**Left for later phases.** The frontend screens for campuses, the multi-step team
wizard, the workflow and wide-approver configuration pages, and the guided navigation
are the next phase; the API surface they need is in place.

## Phase 2 — Team category, multi-workflow teams, and the three levels of approver (frontend)

**What the screens now say.** The API surface from the backend phase is wired end to
end: a team is created as *academic* (campus required) or *administration* (campus
cleared, not merely left blank); a team owns several chains and routes exactly one of
them; a role can be held at institution, team, or campus scope; and the fallback order
of those three is shown as data, not implied.

**Data layer.** `lib/teams.ts` gained `TeamCategory` with labels/codes, `Team.category`,
`Team.workflows` (ownership list alongside the routing pointer), `TeamSection.resolution`
and `SECTION_RESOLUTION_LABELS`; `lib/workflows.ts` was re-read for this work — it now
talks to Django directly through `apiClientUrl` like the rest of the read layer, and
carries `WorkflowState`, `listWorkflows({team, routing})`, and the section input shape.
Writes go through BFF proxy routes (`app/api/hr/**`) as the rest of HR does:
`lib/workflows-client.ts` (create/update), `lib/approver-roles-client.ts` (team- and
campus-wide assignment create/remove), `lib/teams-client.ts` gained `routeTeamThrough`.
`lib/approver-roles.ts` reads the two new assignment collections.

**Screens.** New under `dashboard/hr-admin`: **Campuses** (list, create, read, edit;
teams at a campus and its campus-wide holdings), **Approvers** (all three scopes
grouped by role, with `?scope=/&team=/&campus=` filters), and, under **Teams/[id]**,
tabs for overview / approval steps / approvers / members plus **Workflows** (the team's
owned chains, which one routes, and a confirm-then-route action). The team wizard
(`components/hr/team-form.tsx`) now asks the category first — the campus select is the
visible half of the rule and is disabled until the team is academic — and a new
`WideHoldingPanel` is the single place a wide holding is added or removed, with the
scope picker offered only when the role allows more than one scope.

**Navigation.** The HR section of the dashboard shell gained **Campuses** and
**Approvers** between Teams and Roles, so the guided path (campus → team → chain →
approvers) is reachable without knowing URLs.

**Roles page narrowed.** It no longer lists institution-wide holders or writes
assignments — that screen was a second writer for rows the Approvers page now owns. It
links there instead, and keeps only the role catalogue (including retired roles, which a
chain may still name).

**Verification.** Frontend `npx tsc --noEmit` clean, `npx eslint .` clean, and the full
Vitest suite **65 files / 444 tests OK**. Rewritten/added tests: `campus-form.test.tsx`
for both `CampusForm` and `CampusQuickAdd` (the old collapsible API is gone),
`team-form.test.tsx` updated for the category rule — the exact create-payload key list
now includes `category`, the campus select is asserted disabled until Academic is
chosen, an academic team with no campus is refused before any write, and an
administration team sends `campus: null`. Dead code removed: `RoleAssignmentForm` and
its test (superseded by `WideHoldingPanel`), plus the holders block on the roles page.

**Left for later phases.** Employee-side surfaces still predate the category model (an
employee's team is a single FK, so "the same office approves for two teams" needs one
holder per team — already noted in Phase 1); the approvals screens read the backend's
resolver and need no change for the new fallback order, but have not been re-smoked
against a team that relies on a campus-wide holder.

## Defect Fix (2026-10-06) — `next/headers` reached the browser through client components

**What broke.** Opening `/dashboard/hr-admin/entitlements/new` in `next dev` (Turbopack)
failed with: *"You're importing a module that depends on `next/headers`. This API is only
available in Server Components…"*, traced as `api-client.ts ← leave-rules.ts ←
entitlement-form.tsx`. The entitlements trace itself was a stale `.next` graph — that
form stopped importing leave-rules when the leave-type picker was removed — but the
class of bug was real and live in two places.

**The rule that was being broken.** `lib/api-client.ts` reads cookies from
`next/headers` and is server-only by construction. Several lib modules import it
(`teams`, `leave-rules`, `workflows`, `approver-roles`, `employees`, `entitlements`,
…), so a *value* import from any of them, from a `"use client"` component, puts
`next/headers` into the browser bundle. Type-only imports are erased and are fine.
Two client components were doing it:

* `components/hr/team-form.tsx` imported `TEAM_CATEGORY_LABELS` from `lib/teams.ts`
  (introduced with the category radio group).
* `components/hr/leave-type-form.tsx` imported `isAnnualLeaveType` from
  `lib/leave-rules.ts` (pre-existing; the earlier `ea9fbec` fix created
  `leave-types-client.ts` for the fetches but left the pure predicate behind).

**The fix.** Pure vocabulary moved to client-safe siblings, re-exported from the
server modules so server callers keep one import path:

* `lib/team-category.ts` — `TeamCategory`, labels/codes, `teamCategoryLabel`,
  `teamCategoryBadgeClass`.
* `lib/leave-rules-pure.ts` — leave-type/rule interfaces, `ANNUAL_LEAVE_CODES`,
  `isAnnualLeaveType`, `leaveRuleStatus`.

Client components import from the pure modules; `team-table`, `campus-table`,
`leave-rule-table` and `leave-type-table` do too, so the rule is one line long —
a helper never comes out of a module that reads Django.

**Guard rail.** `tests/server-only-imports.test.ts` walks `lib/`, seeds the
server-only closure with anything importing `next/headers` or `api-client`, grows it
by value-imports, and fails if any `"use client"` file value-imports from that
closure. `tsc` cannot see this mistake (the import type-checks); the browser is where
it explodes, so it is pinned here instead.

**Verified.** `.next` cleared (the stale entitlements graph was the reported error).
`tsc --noEmit` clean, `eslint .` clean, full Vitest suite **67 files / 459 tests OK**,
and `next build` compiles successfully with `/dashboard/hr-admin/entitlements/new`,
the campuses pages and the approvers page all in the route table.

## Operational (2026-10-06, all seed data removed — bare database)

**What was removed.** The dev database `luanar_leave` was dropped and recreated,
then `manage.py migrate` run from zero. Final state, verified through the ORM:
**0 users**, 0 employees, 0 campuses, 0 teams, 0 workflows, 0 sections, 0
team/campus/institution holdings, 0 leave types, 0 grade entitlements — and the
**six approver roles** migrations ship (`supervisor`, `hod`, `dean`, `registrar`,
`campus_registrar`, `dvc`), which are product data from `workflows.0011`, not
seed data. The two leftover users, one team, one workflow and one section from
the Phase 1 smoke test are gone with the drop.

**What was deleted from the codebase earlier, now reflected in the docs.**
`users.management.commands.seed_dev_users` and its `management/__init__.py` were
already removed from the tree (they seeded seven `@test.luanar` accounts with
`testpass123` plus employee profiles and default entitlements). The root
`README.md` still told a second developer to run that command and tabulated the
seeded emails. The setup step is gone, and the "Development Users" section is
replaced by **First account**: there is no seed command and no fixture users; a
fresh database has the schema plus the six migration-shipped roles and nothing
else, and the bootstrap administrator is created with `createsuperuser` (email
as username, then `role = "hr"` once — the instructions that follow are
unchanged).

**Deliberately kept.** Test code may still create users with `testpass123` and
`@test.luanar` addresses — that is what the suite logs in as, and it runs
against the separate test database, not the dev one. `workflows.0011`'s six
canonical roles stay: without them no chain can be built on a bare database.
`leave.providers.fixture_data` / `FixtureRulesProvider` stay as the placeholder
rules provider still exercised by `leave/tests/test_cancellations.py`; the
configured provider is `DatabaseRulesProvider`.

**Verified.** Post-drop ORM counts as above; `README.md` contains no
`seed_dev_users`, `testpass123` or `@test.luanar` reference.

## Operational (2026-10-06, approver roles removed from the clean install)

**Directive.** After the bare-database pass, the developer asked to remove the
six migration-shipped approver roles as well — a clean install must start with
zero business records of any kind, including the role vocabulary.

**Migration 0028.** `workflows/0028_remove_seeded_approver_roles.py` deletes
the seed codes 0011 created (`supervisor`, `hod`, `dean`, `registrar`,
`campus_registrar`, `dvc`) **only when nothing references them**. On a fresh
`migrate` the database ends at zero roles; if any section or holding still
points at a seed code the rows are live configuration and are left alone, so
this cannot delete a real approval right. Reverse is a no-op (0011 re-seeds if
the database is rewound). `makemigrations --check` clean.

**Test suite made self-contained.** Roles are HR data, not migration seed, so
tests create what they use:

* `workflows/testing.py` `ROLE_SPECS` now carries the description text the edit
  tests quote (mirrors 0011's seed copy).
* `ConfigurationAPIBase`, `TeamConfigurationBase`, `SectionSequenceTests`,
  `WorkflowEndpointTests`, `WorkflowSerializerAtomicityTests`, and
  `AuditWiringTests` call `ensure_roles(...)` in `setUp` for the codes their
  payloads name.
* `leave/tests/legacy.py` `CleanDatabaseBootstrapTests` now asserts
  `ApproverRole` is empty on a fresh test database (was: six shipped roles).
* `RoleListingTests.test_adding_roles_does_not_add_queries` seeds its own
  baseline roles before the query-count assertion.

**Docs.** README "First account" no longer claims six roles ship; it states a
fresh database has the schema and nothing else, and that the superuser creates
HR through `/dashboard/admin/users`. Architecture already said HR defines role
codes — unchanged.

**Verified.** Dev DB dropped, recreated, migrated from zero: every model count
0. Backend suite **1182 OK** (includes the three previously failing audit /
bootstrap tests). Frontend production paths contain no mock business data —
pages read API results and show create/empty affordances; document-template
`sample` labels are system vocabulary for the template editor, not DB records.

**Deliberately kept (classification).**

| Item | Class | Why |
| --- | --- | --- |
| `workflows.0011` + `0028` | historical migration pair | 0011 cannot be rewritten; 0028 neutralises it on bare DBs |
| `workflows/testing.py` `ROLE_SPECS` / `ensure_roles` | test-only | fixtures create roles per test; never written to the dev DB |
| `leave.providers.fixture_data` / `FixtureRulesProvider` | test-only placeholder | default `LEAVE_RULES_PROVIDER` is `DatabaseRulesProvider` |
| `provision_annual_leave` / `get_or_create_annual_leave_type` | HR-triggered product write | runs when HR saves a grade entitlement, not on startup |
| `documents.services.get_template` | essential system config | singleton leave-document template materialised on first render |
| `FIELD_CATALOG` sample labels | essential system config | template-field vocabulary for the HR preview; not DB rows |
| Superuser + `POST /api/v1/admin-users/` | essential system access | bootstrap admin outside the product; creates HR only |
| Test passwords `testpass123` / `@test.luanar` | isolated test data | test DB only; not committed as seed scripts |

## Completed — Team Member Management and Workflow Member Eligibility (2026-10-07)

Specification authority: the feature request behind Unit 32 — like the team
management and workflow-sections work, this landed from a product request rather
than a numbered spec file, and the invariants live in `context/architecture.md`
§12.14–12.15. Not yet committed. Feature: a dedicated Team Members screen per team (search, filtering,
pagination, empty states, add/remove members, removal safeguards) plus normal
workflow members as a first-class, team-scoped assignment with a backend-computed
eligibility pool that can only ever offer people the write will accept.

**Backend — model + migration (`workflows/0029_workflowmember.py`).**
- `WorkflowMember` (workflow FK `CASCADE`, `user` FK `PROTECT`, denormalised
  `team` FK `CASCADE`, `added_by` FK `PROTECT` null, `created_at`) with DB-level
  unique constraints on **both** `(workflow, user)` and `(team, user)`. The
  second is the one-chained-member-per-employee backstop: even two concurrent
  assigns cannot put a person on two of a team's chains.
- Team source of truth stays `EmployeeProfile.team` (`related_name="members"`),
  so `WorkflowMember` is distinct from `Section.approver` / `SectionMember`.

**Backend — services (`workflows/services.py`).**
- `add_team_member` / `remove_team_member` with `select_for_update` on the
  profile row (locked without `select_related`, which the profile's nullable FKs
  would break on `FOR UPDATE`) and a full `_team_member_blockers` refusal set:
  active section approver, open approver period, `WorkflowMember` on any of the
  team's chains, `TeamRoleAssignment` on this team — each named in the 409.
- `workflow_member_pool` (available / current / assigned_elsewhere),
  `assign_workflow_member`, `remove_workflow_member`, and `sync_workflow_members`
  (whole-list replace on the workflow write; `None` = leave alone, `[]` = clear).
- `team_member_summaries` for the roster rows (workflow footprint + approver
  stance + team role). Audit: team add/remove → `TargetType.EMPLOYEE` /
  `UPDATED` via `changed_fields`; workflow member assign → `WORKFLOW/CREATED`,
  remove → `WORKFLOW/DEACTIVATED`, sync → `WORKFLOW/UPDATED`.

**Backend — API.**
- `GET/POST /api/v1/teams/{id}/members/`; `DELETE .../members/{user_id}/`;
  `GET /api/v1/teams/{id}/workflow-member-pool/?workflow=<id>`;
  `GET/POST /api/v1/workflows/{id}/members/`; `DELETE .../members/{user_id}/`;
  `members: [user_id]` accepted on the workflow write serializer.
- Both `TeamViewSet` and `WorkflowViewSet` gained `"delete"` in
  `http_method_names` solely to serve the member-removal actions; no destroy
  mixins were added (teams are retired, workflows never deleted by these views).

**Tests — `backend/workflows/tests_workflow_members.py` (35 new, all green).**
- `TeamMemberManagementTests` — add places an employee, remove clears them, and
  each refusal path (approver period, section approver, workflow member, team
  role holder) is a 409 naming the blocker.
- `WorkflowMemberEligibilityTests` — pool semantics for create (unassigned) and
  edit (current included as selected, siblings read-only under
  `assigned_elsewhere`). Uses a bare `team_for()` team because `make_team`'s
  seeded approver would pollute the pool with a fourth member.
- `WorkflowMemberAPITests` — endpoint write path and HR-only access (403 for a
  non-HR token).
- `WorkflowMemberConcurrencyTests` — `TransactionTestCase` proving the
  `(team, user)` unique constraint surfaces as an `IntegrityError` under race.
- `TeamMemberSummaryTests` — roster footprint shaping.

**Frontend.**
- BFF routes: `teams/[id]/members` (GET/POST), `teams/[id]/members/[userId]`
  (DELETE), `teams/[id]/workflow-member-pool` (GET), and
  `workflows/[id]/members/[userId]` (DELETE).
- `lib/team-members.ts` (client-safe types) + `lib/team-members-client.ts`
  (BFF calls); `Workflow`/`WorkflowInput` gain `members` / `members?: number[]`.
- `components/hr/team-members-panel.tsx` replaces the old roster in the team
  page's Employees tab: server-loaded roster, search, filter (all / staff a
  step / hold a team role / on a workflow / inactive), pagination, empty states,
  add-from-unassigned picker, and remove with the backend's refusal message
  shown inline.
- `components/hr/workflow-form.tsx` gains a "Normal workflow members" section
  wired to the eligibility pool: invites load from `available`, current members
  pre-check via `workflow.members`, assigned-elsewhere rows render read-only with
  the sibling chain's name, and submit sends `members` as the whole chosen list.

**Verified.** Backend `workflows` suite **558 OK**, whole backend suite
**1217 OK**, `makemigrations --check` clean. Frontend **468 tests OK** (+6
panel, +3 form-members), `tsc --noEmit` clean, `eslint .` clean, production
build succeeds.

**Notes / tricky classes.**
- `select_for_update().select_related(...)` blew up on nullable FKs
  (`NOT NULL` side lock only) — the lock now targets just the profile row and
  names are read separately.
- Frontend `setState` in an effect is refused by the repo's lint rule, so the
  panel loads via `.then` in the effect rather than a synchronous `reload()`.

## Completed — Second-Workflow Exclusion and Chain-Scoped Approver Picker (2026-10-07)

Follow-on to the workflow-member feature above (same feature request, Unit 32 +
the second-workflow rule the user added). Not yet committed. A team's **second**
chain must be built from people who are not already serving one of its other
chains, and step approvers are now picked on the workflow form itself, shaped by
the same exclusion.

**Backend — model + migration (`workflows/0030_...`).**
- `WorkflowMember.is_wide_approver` boolean; `workflow_member_team_user_unique`
  is now a **conditional** `UniqueConstraint` on `(team, user)` where
  `is_wide_approver = False`, so a wide approver may sit on several of the
  team's chains at once and a concurrent write still cannot route around the
  one-chain rule. `(workflow, user)` stays unconditional.
- Migration 0030 removes the old constraint, adds the column, `RunPython`
  backfills `is_wide_approver=True` from live holdings (RoleAssignment
  institution-wide, TeamRoleAssignment on the team, CampusRoleAssignment at the
  team's campus), then re-adds the conditional constraint. Applied to dev.

**Backend — services (`workflows/services.py`).**
- `_wide_approver_ids_for_team(team)` — active users with an institution-wide
  RoleAssignment, a TeamRoleAssignment on the team, or a CampusRoleAssignment at
  the team's campus; team with no campus reads no campus rows.
- `ensure_not_assigned_elsewhere(section, user)` wired between
  `ensure_single_stage_per_workflow` and `ensure_role_consistency` in
  `ensure_membership_allowed`: refuses a non-wide person who is a normal member
  of another of the team's chains or staffs an active step of one, naming the
  sibling chain; the section's own workflow is excluded so resaving the same
  appointment passes.
- `assign_workflow_member` computes `is_wide_approver` at write time, calls new
  `_ensure_member_not_assigned_elsewhere(...)` for non-wide people (member
  elsewhere or step approver elsewhere refused), and creates the row flagged.
- `workflow_member_pool` now also counts active-section step approvers of other
  chains in `assigned_elsewhere` (workflow_name named), subtracts wide ids, and
  keeps wide approvers in `available`.

**Backend — API.**
- `GET /teams/<id>/eligible-approvers/?workflow=<id>` — drop anyone assigned to a
  **different** chain of the team (WorkflowMember or active step approver);
  `?workflow=new` drops anyone on **any** of the team's chains (chain not
  created yet); the absent parameter keeps its legacy no-exclusion behaviour for
  the team form. Wide ids are subtracted.
- `WorkflowMemberSerializer` exposes read-only `is_wide_approver`.

**Backend — tests (9 new, all green).**
- `tests_workflow_members.py`: step approver elsewhere excluded+named from a
  sibling pool; step approver elsewhere refused as member; member elsewhere
  refused as step approver; resaving one's own chain approver is not a conflict;
  team-wide approver joins both chains, stays eligible, not flagged elsewhere;
  institution-wide approver exempt.
- `tests_teams.py` `EligibleApproverEndpointTests`: `?workflow=<id>` drops people
  on the other chain yet keeps the chain's own holder; `workflow=new` drops
  people on any chain while the no-param call keeps legacy behaviour; a
  team-wide approver on another chain stays offered.

**Frontend.**
- `lib/teams-client.ts listEligibleApprovers(team, role?, workflow?)`; BFF route
  `app/api/hr/teams/eligible-approvers` accepts `workflow` in FILTERS.
- `lib/workflows.ts` `WorkflowSection` gains `approver: number | null` and
  `approver_name: string | null`.
- `workflow-form.tsx` gains a **per-step approver picker**: candidates load per
  `(team, role)` scope via `listEligibleApprovers(team, roleId, workflow ?? "new")`
  (memoised key `${team.id}:${roleId}`); editing pre-fills the step's current
  approver; changing a step's role clears that step's approver; submit sends
  `approver` per section. Footer now explains the one-chain-per-employee rule.
- `team-member-list.tsx` (approval steps screen) scopes its picker to the team's
  routing workflow (`team.workflow`); its test expectations updated.
- **UI naming pass (same day):** the team page tab that holds the roster is
  renamed from "Employees" to **"Members"** and its heading now says "Team
  members" with a line that add/remove happens here and that membership alone
  never places anyone on a workflow. The workflow form's normal-members note
  now links to that Members tab and states the pool is drawn only from the
  team's members. No new page — both surfaces live on the existing Team
  Details and Workflow Configuration pages.

**Verified.** Backend whole suite **1226 OK**, `makemigrations --check` clean.
Frontend **470 tests OK** (+2 picker), `tsc --noEmit` clean, `eslint .` clean.

**Notes / tricky classes.**
- Two sources of "assigned to a chain" must agree everywhere: `Section.approver`
  on active sections and `WorkflowMember` rows. `workflow_member_pool`,
  `eligible-approvers`, `ensure_not_assigned_elsewhere`, and
  `_ensure_member_not_assigned_elsewhere` all compute the same union minus wide
  ids.
- Frontend lint refuses `setState` synchronously inside an effect, so the
  candidate effect returns early for an empty key pair instead of resetting
  state there; new keys replace the whole `candidates` record in `.then`.
- `roleIdByCode` is built in its own `useMemo` because it feeds another memo's
  dependency array.

## Completed — Creating a Team Lands on Its Members, Then Workflow Configuration (2026-10-07)

User directive: "after creating a team the process should not go direct to
approval steps but the process should go to adding team members first then it
can go to configuring workflow." This matches the §9 required sequence (Team
Details → Members → Add Team Member → Workflow Configuration). Not yet
committed.

**Frontend (`components/hr/team-form.tsx`).** Creating a team is now
**details-only**:
- The create wizard's page two (approval-steps/chain) is gone for a new team —
  exactly one page asks what the team *is*, and the submit button reads
  **"Create team"** instead of "Continue to approval steps". The team is
  written as a **chainless draft** (no `new_workflow` in the payload), reusing
  the draft-save branch the backend already supported.
- After save the form redirects to the **new team's Members tab**
  (`/dashboard/hr-admin/teams/<id>?tab=members`), not the teams list, so
  employees are added before anyone is appointed. The approval chain is
  configured afterwards from Overview → New workflow.
- A hint under the create button states the Members-tab-first flow.
- Editing is unchanged: the edit form keeps the two-page shape (details, then
  the per-step chain that rewrites the team's routing workflow).
- Dead create-only copy removed from page two (steps can no longer be reached
  without a team), and the page-two render is now gated on `!team`.
- `team-form.test.tsx`: create-path tests rewritten for the details-only flow
  (payload has no `new_workflow`; exact key list excludes it; push expects
  `/dashboard/hr-admin/teams/4?tab=members`); the no-longer-possible
  create-wizard tests (step-description, draft-save-from-create) removed; two
  chain tests that were exercising the create form now exercise the edit form,
  which is where chain work happens.

**Verified.** Frontend **468 tests OK** (net −2 create-wizard tests),
`tsc --noEmit` clean, `eslint .` clean. Backend untouched.

## Completed — Team Member Picker Is Category-Scoped and Never a Wide Approver (2026-10-07)

User directive: the team-member picker must only show employees whose category
matches the team (academic team → academic employees, administration team →
administration employees), and the only people available to add are normal
employees — wide approvers are excluded. When asked "what about a wide approver
who is not yet listed?", the user chose **"Exclude wide approvers (no list, no
add)"**: a wide approver is never offered in the add-member list, and the
backend refuses adding one as a normal member. Not yet committed.

**Backend — read (`users/views.py` `EmployeeViewSet.get_queryset`).** The
employees endpoint now scopes its team=none answer for the roster picker:
- `?category=<academic|administration>` keeps only employees of the team's kind.
  An unknown value is ignored, not fatal.
- `?not_wide_for_team=<id>` excludes `wide_approver_ids_for_team(team)` — the
  institution-wide holders, this team's `TeamRoleAssignment` holders, and the
  `CampusRoleAssignment` holders at the team's campus (when the team has one). A
  missing team or a non-numeric id ignores the filter. The fallback is to offer
  nothing the write will refuse.

**Backend — write (`workflows/services.py` `add_team_member`).** The same two
rules on the write path, so a stale or hand-typed request is refused rather than
kept in sync by the UI alone:
- category mismatch → `WorkflowMemberError` naming both kinds ("…is an
  Academic employee, but "X" is an Administration team…");
- wide approver for the team (any of the three holdings) → refused with "… is a
  wide approver for this team, so they serve its steps from the Approvers tab
  rather than as a normal member."
- `_wide_approver_ids_for_team` was made **public** (`wide_approver_ids_for_team`)
  so `users.views` can reuse the one canonical helper; call sites updated
  (services.py, views.py-approved paths unchanged in behaviour).

**Frontend.** `lib/employees.listUnassignedEmployees(category?, teamId?)` sends
`category` + `not_wide_for_team`; the team page passes `team.category`/`team.id`.
`TeamMembersPanel` copy now says the picker is scoped ("Only employees without a
team who match this team's category are offered here, and never a wide
approver") and the empty option reads "No employees to add to this team" instead
of "No employees without a team".

**Tests.** Backend `users/tests.py` (`EmployeeRosterFilterTests`: category
keeps/excludes by kind, unknown category ignored, institution-/team-/campus-wide
holders excluded per team and only per team, garbage/nonexistent id ignored) and
`workflows/tests_workflow_members.py` (`TeamMemberManagementTests`: category
mismatch refused, academic-on-academic accepted, institution-wide and campus-wide
approvers refused, roster untouched after every refusal). Frontend
`tests/employees-lib.test.ts` (new — query params + paging) and
`tests/team-members-panel.test.tsx` (now asserts the scoped picker copy).

**Verified.** Backend **1238 tests OK** (11 new), `makemigrations --check`
clean. Frontend **472 tests OK** (70 files), `tsc --noEmit` clean, `eslint .`
clean.

---

## Completed — User-id vs Record-id Mixup Fixed in HR Pickers (2026-10-07)

**Reported:** "when i try to add a member to a team i experience this error: user:
admin@luanar.mw has no employee record, so there is nothing to place on a team.
Complete their employee record first." and "i'm unable to add a team wide
holder/approver".

**Root cause (two defects, one shared contract).** An `Employee` row from
`EmployeeSerializer` carries its **record pk** as `id` and the linked **account**
as `user_id`; every write that places a person into a `User`-keyed field
(`/teams/<id>/members/` `user`, delegation `approver`/`delegate`,
reassignment `to_approver`, and the holder picker) resolves against `User`.

1. **Member add picker sent the record pk as a user pk.** `TeamMembersPanel`'s
   add `<option>` used `value={person.id}` and POSTed it as `user`. When a
   candidate's record pk coincided with another account's user pk (candidate
   record pk 2, `admin@luanar.mw` user pk 2, no employee record), the backend
   resolved to admin and refused with the reported "has no employee record"
   message. Live check: sending `user_id` for the same person resolves correctly.
2. **The Approvers-tab holder feed reused the roster's scoped candidates.**
   The team page built `employees = [...members, ...candidates]`, and after the
   category/wide-approver scoping work `candidates` excluded wide approvers and
   category-mismatched employees. A team-wide holder **need not be a team
   member** (`create_team_role_assignment` accepts any active employee with a
   record), so genuine holder candidates silently vanished from the picker —
   "unable to add a team wide holder". The feed is now the whole directory.

**Fixed.**
- `TeamMembersPanel` add picker options now carry `person.user_id`
  (`frontend/components/hr/team-members-panel.tsx`).
- Team Approvers tab feed `[...members, ...candidates]` → `listAllEmployees()`
  (`frontend/app/(dashboard)/dashboard/hr-admin/teams/[id]/page.tsx`); the
  category/wide filters remain scoped to the *members* picker only.
- Same `user_id` correction in the delegation create/review (approver/delegate)
  and reassignment (`to_approver`) pickers plus their candidate filters
  (`delegation-form.tsx`, `delegation-review.tsx`, `reassignment-form.tsx`).

**Tests.** All four tests' employee fixtures now use **distinct** `id`/`user_id`
(together they coincided and masked the bug); `team-members-panel.test.tsx`
adds the candidate with `user_id 99`/`id 30` and asserts `addTeamMember` is sent
`99`. **Frontend 472 tests OK (70 files), `tsc --noEmit` clean, `eslint` clean.**
Backend unchanged (the mismatch was client-side; the write refusals — "no
employee record", category, insufficient scope — are correct behaviour).

**Worth knowing.** Live DB still has three profile-less users
(`root@luanar.ac.mw` pk 1, `admin@luanar.mw` pk 2, `hr@luanar.ac.mw` pk 3). They
remain unoffered by every picker and refused by every write; appointing any of
them requires completing their employee records first — by design.

---

## Completed — Team-wide Holder Save Sent `team: 0` (2026-10-07)

**Reported:** "when i want to add the team wide approver by selecting approver
button inside a team, it shows this error: team: Invalid pk \"0\" - object does
not exist. but if i add team wide approver using approvers item in the sidebar i'm
able to add the approver without the problem."

**Root cause.** `WideHoldingPanel` only draws a scope picker when `scopeOptions`
is non-empty, and only then validates. The team page (and the campus page)
passed **neither** `scopeOptions` nor any fixed id — so no picker rendered,
`scopeId` fell back to `Number(null || 0) = 0`, the `needsScope` guard never
ran, and `POST /team-role-assignments/` received `team: 0` → the backend's
`Invalid pk "0"`. The sidebar Approvers page worked because it passes
`scopeOptions` (all teams / campuses), which turns both the picker and the guard
on.

**Fixed.**
- `WideHoldingPanel` takes an optional fixed `scopeId` (the team or campus whose
  page renders it): no picker is drawn — there is nothing to choose — and the id
  travels with the write. `needsScope` now means "no fixed scope **and** there
  are options to choose between".
- Team page passes `scopeId={team.id}`; campus page passes `scopeId={campus.id}`.
  The sidebar Approvers page is unchanged (`scopeOptions` = all teams/campuses).
- The guard was widened from `needsScope && !scopeId` to
  `scope !== "institution" && !scopeId`, so a scoped save with no id is refused
  with "Choose the team/campus this holding applies to." in *any* state — pk 0
  can no longer reach the backend from this panel.

**Tests.** 3 new in `tests/wide-holding-panel.test.tsx`: fixed team scope saves
with the page's team and draws no picker; fixed campus scope likewise; a scoped
panel with neither fixed id nor options names the missing scope instead of
sending pk 0.

**Verified.** Frontend **475 tests OK (70 files)**, `tsc --noEmit` clean, `eslint`
clean. Backend untouched. Still uncommitted, together with the earlier
user-id/record-id picker fix.

## Completed — Wide Approvers Are the Same Category as the Teams They Cover (2026-10-07)

**Requested:** "campus wide and team wide approvers under Academic should be
employees under Academic wide category" — i.e. a wide approver must belong to
the same half of the institution they hold a role for.

**Rule.** A **team-wide** holder must match the team's category (an academic
team takes an Academic holder, an administration team an Administration
holder). A **campus-wide** holder must be an Academic employee, because every
team at a campus is academic (the model refuses an administration team with a
campus — architecture §12.x), so a campus holding is always an academic-team
holding. Institution-wide holdings are unchanged: they already serve only
administration teams and carry no category restriction.

**Backend (the hard rule).** `create_team_role_assignment` refuses with
`RoleActionError("user", … " is an Academic employee, but "X" is an
Administration team.")` when `user.employee_profile.category != team.category`; `create_campus_role_assignment`
refuses non-Academic holders the same way. Raised *after* `_ensure_wide_role`,
so the profile-existence check still runs first. Both surface as a 400
`{"user": [...]}` through the existing `RoleActionError` → `Response` handling
in the team/campus role-assignment viewsets.

**Frontend (offer only what the write accepts).** `listAllEmployees(category?)`
gains the `?category=` filter (server-side, same pattern as the roster read);
`ScopeOption` carries `category`; `WideHoldingPanel` takes `requiredCategory`
and filters `candidates` by the fixed scope's category *or* the chosen scope
option's, using a controlled scope select.
- Team page: Approvers feed becomes `listAllEmployees(team.category)` and the
  panel gets `requiredCategory={team.category}`.
- Campus page: feed becomes `listAllEmployees("academic")` and the panel
  `requiredCategory="academic"`.
- Sidebar Approvers page: `teamOptions`/`campusOptions` carry each option's
  category (teams from `team.category`, campuses `"academic"`), institution
  panels keep the full directory. The team/campus panels filter per-option
  (the one place a client-side per-option filter is unavoidable: one shared
  select serves teams of both categories).

**Tests.** Backend: `tests_workflow_members.py::WideHolderCategoryTests` — 4 new
(academic holder refused on an administration team, matching-category holder
accepted, administration holder refused on a campus, academic holder accepted).
Frontend: 4 new in `wide-holding-panel.test.tsx` (fixed team category, fixed
campus academic, person list follows chosen team's category, campus academic
once a campus is chosen).

**Verified.** Backend workflows suite green (members module 50 tests, including
the 4 new). Frontend **479 tests OK (70 files)**, `tsc --noEmit` clean,
`eslint` clean. Still uncommitted with the batch above.

## Completed — Wide Approvers Choose Their Role From a Drop Down (2026-10-07)

**Requested:** "when assigning wide approvers, the role name should be selected
from the drop down" — i.e. assigning a wide approver names the role first, in a
select, instead of the Approvers page repeating the whole form once per role.

**Change.** `WideHoldingPanel` is now one form per scope (institution, team,
campus), not one form per role:
- Props became `{ scope, roles, scopeOptions?, scopeId?, requiredCategory?,
  employees, holdings }` — the single `role` prop is gone. The Role drop down
  offers the roles valid at that scope: the institution panel shows every
  active role, the team/campus panels only scoped roles
  (`activeRoles.filter(r => !r.is_institution_wide)`), which also stops a role
  that would be refused (an institution-wide role can't be held at a team or
  campus) from appearing in a team/campus picker.
- The person select is disabled until a role is chosen; candidates are the
  scope's category (fixed `requiredCategory` or the chosen `ScopeOption.category`)
  minus the people who already hold the chosen role at that scope. Empty
  candidates reads "Every active matching employee already holds {role} here."
- Holdings list shows `role_label · user_name` with a Remove per row; a save
  replaces that role's holder at the chosen scope, with a footnote on the
  Approvers page saying so.
- Approvers page: flattened `institutionByRole`/`teamByRole`/`campusByRole`
  into `institutionHoldings`/`teamHoldings`/`campusHoldings`, dropped
  `groupByRole`, and renders one grid of three panels with the scope filters.
  Team/campus pages each render a single panel with fixed `scopeId`.
- Form `id`s per scope (`role-${scope}`, `scope-${scope}`, `holder-${scope}`) so
  the three panels' selects never collide.

**Tests.** `wide-holding-panel.test.tsx` rewritten for the new API — 22 tests:
role drop-down contents, per-scope remove collections (institution/team/campus),
institution write with no scope picker, team picker requires the team,
campus write with chosen campus, fixed `scopeId` writes with no picker (the
pk-0-guard regression), missing-scope guard, no-role / no-person refusals,
holder-of-the-role excluded live, empty-candidates message, inactive excluded,
fixed team category / campus academic, person list follows chosen team's
category, campus academic once chosen, no-roles placeholder, server refusal
stays usable.

**Verified.** Full frontend suite **481 tests OK (70 files)**, `tsc --noEmit`
clean, `eslint` clean. Backend untouched. Uncommitted (see the batch below).

## Completed — A Person Holds Only One Wide Approver Role (2026-10-07)

**Requested:** "ensure that when a person is assigned a wide approver, that
person must not appear again in other wide approver sections" — i.e. once
somebody is a wide approver anywhere, they must not be offered (or appointed)
again anywhere else.

**Rule.** One wide approver per person, across all three scopes. Once Jane is
the Dean team-wide on one team, she is gone from every other wide-approver
picker — institution, any other team, any campus — and the writes refuse a
second holding, naming the existing one. The same role at the same scope stays
writable in place (that is the holding, not a second one), so re-pointing a
holder still works.

**Backend (the hard rule).** `_ensure_single_wide_holding` added to all three
creates:
- `create_role_assignment` — refuses a user who holds any team- or campus-wide
  holding, or a *different* institution-wide role (same-role re-save still hits
  the existing "already holds X role" path).
- `create_team_role_assignment` — refuses a user with any wide holding except
  the (team, role) pair this write is replacing.
- `create_campus_role_assignment` — same, excluding the (campus, role) pair.

Message: "A person may hold only one wide approver role, and {name} already
holds {role} institution-wide / as a team-wide approver on {team} / as a
campus-wide approver at {campus}. Remove that holding before assigning another
one." Surfaces as a 400 `{"user": [...]}` through the existing
`RoleActionError` → `Response` handling.

**Frontend (offer only what the write accepts).** `WideHoldingPanel` gains
`excludedUserIds?: number[]` and filters candidates by it (in addition to the
same-role-here and category rules); the empty-person message now reads "Every
active matching employee already holds a wide approver role here or elsewhere."
Each page feeds the union of every holder's user id:
- Approvers page: `[...institution, ...team, ...campus]` (read unfiltered, so a
  holder is excluded even when the scope chips filter a panel down).
- Team page: reads `listRoleAssignments()`, `listTeamRoleAssignments()`,
  `listCampusRoleAssignments()` and unions them (its own holdings are filtered
  out of the list, not the pool).
- Campus page: same, with `listCampusRoleAssignments()` read unfiltered.

**Tests.** Backend: `WideHolderSingleRoleTests` — 9 new (institution holder
refused team-wide; team-wide refused institution-wide; team-wide refused a
second role on the same team; institution holder refused a second institution
role; team-wide refused campus-wide; campus holder refused team-wide elsewhere;
re-saving the same (team, role) still says "already holds", not the single-role
message; replacement with a fresh person allowed; replacement with an
institution-wide person refused). Frontend: 2 new — a person who holds a wide
role elsewhere is not offered; the person list hides when every candidate is
already wide.

**Verified.** Backend non-migration workflows suite **555 tests OK** (546 +
9), `makemigrations --check` clean. Frontend **483 tests OK (70 files)**,
`tsc --noEmit` clean, `eslint` clean. Uncommitted with the role-dropdown batch.

## Defect Fix (2026-10-07) — workflow detail crashed reading `section.memberships`

**Reported:** "Cannot read properties of undefined (reading 'filter')" on
`teams/[id]/workflows/[workflowId]`, at `section.memberships.filter(...)`.

**Root cause.** `SectionSerializer.memberships` (`SectionMemberSerializer`,
`many=True`) declared no `source`, but the reverse relation on `SectionMember`
is named `members`, not `memberships`. DRF resolves a read-only field that
cannot be read from the instance as "skipped", so the API payload never
contained the key and the chain screen crashed on `undefined.filter`.

**Fix.** `Section.memberships` property added to the model, serving the full
period record from `SectionMember.all_objects` (open *and* closed rows, in
`effective_from` order) so the existing field serializes as designed — the
explained contract: closed periods are how "who held this step in March" stays
answerable. Unstaffed steps now emit `memberships: []`, never miss the key.

**Tests.** `WorkflowDetailMembershipSerializationTests` — 2 new: every section
of the workflow detail emits a `memberships` key (regression for the crash),
and a staffed step lists its effective holder. Backend non-migration workflows
suite now **557 tests OK**, `makemigrations --check` clean (property only, no
schema change).

## Defect Fix (2026-10-07) — workflow detail rendered the resolution object

**Reported:** "Objects are not valid as a React child (found: object with keys
{source, automatic, user, user_name, label})" on
`teams/[id]/workflows/[workflowId]`. Surfaced once the previous `memberships`
fix let the chain render further.

**Root cause.** `SectionSerializer.get_resolution` returns that object (the
backend's decided answer: where the approver comes from, the label, and the
person), but the frontend typed `WorkflowSection.resolution` as `string` and
passed it through `sectionResolutionLabel`, which treated it as an unknown
string code and fell back to returning the object itself as a React child.

**Fix.** Frontend only. `WorkflowSectionResolution` type added to
`lib/workflows.ts` matching the read contract (`source`, `automatic`, `user`,
`user_name`, `label`); `WorkflowSection.resolution` retyped to it; the chain
page renders `section.resolution.label` plus the resolved person's name when
there is one, instead of `sectionResolutionLabel(section.resolution)`. That
helper's vocabulary ("staffed" / "team_wide") never matched the workflow
endpoint's; it remains only for the unrelated `TeamSection` summary, which the
backend does not populate with a resolution.

**Verified.** Frontend `tsc --noEmit` clean, `eslint` clean, **483 tests OK
(70 files)**. No backend change.

## Defect Fix (2026-10-07) — every Edit Steps save refused (`PATCH /api/v1/workflows/1/` → 400)

**Reported:** `"PATCH /api/v1/workflows/1/ HTTP/1.1" 400 94` — the Edit Steps
screen could not save anything.

**Root cause.** The workflow edit form restates the team it is editing under
(`workflow-form.tsx` sends `team: team.id` on every PATCH, a deliberate part of
the frontend contract: "the field is sent so the refusal, when it comes, is the
one that names the rule rather than a missing field"). But
`WorkflowWriteSerializer.validate` refused **any** `team` on update — even the
workflow's own team — so every save returned
`{"team":["A workflow cannot be moved between teams. ..."]}` (exactly the
94-byte body).

**Fix.** Backend only. On update the serializer now accepts `team` when it names
the workflow's current owner (confirmation — discarded, never rewritten) and
still refuses any other team, or null, with the same "cannot be moved" message.
The refusal rule is unchanged; only the false positive is gone. Docstring
updated to state the accepted-confirmation behaviour.

**Tests.** `test_an_edit_may_restate_its_own_team` added (PATCH with the owning
team → 200, owner unchanged); the existing
`test_a_chain_cannot_be_moved_to_another_team` still passes (other team → 400).
Reproduced the reported request against the live workflow: **200** after fix
(previously 400). Backend `tests.py` + `tests_team_configuration` +
`tests_workflow_members` = **298 tests OK**. No frontend change.

## Completed (2026-10-07) — Institution-wide steps staff themselves in the Edit Steps picker

The Edit Steps form now mirrors the backend's appointment rule the moment an
institution-wide role is chosen, instead of showing "Not appointed yet" for a
step the save path has already decided.

**Why it matters.** `_appoint_institution_wide_holder` already appoints the
role's single holder at save, but only on administration teams. The gap was
pre-view: HR saw an empty Approver field, picked a person (or left it), and the
answer arrived later. The form now shows the answer on first draw, and matches
the write rule **exactly** so what the screen promises is what the save accepts:

* only an institution-wide role fills anything;
* only an administration team (an academic team may not use an institution-wide
  approver — `ensure_team_eligibility` refuses it at save, so auto-filling there
  would build a guaranteed 400);
* only when there is exactly one holder (multiple holders is the ambiguity the
  backend leaves unstaffed rather than guesses at).

**The approver is locked to that holder.** An institution-wide role has one true
approver — its single institution-wide holder — so once such a role is chosen
the Approver field is read-only: it shows the holder's name with a lock hint
("Locked to the institution-wide holder of this role.") and no other name can be
selected. The submitted section is exactly that holder. The lock applies on
first draw, in `changeRole`/`addStep`, and covers an *edited* chain too: a step
whose role is institution-wide and solely held is corrected in the form even if
a different person was appointed before the rule existed — the wide holder wins.
Without a single holder the field stays a normal picker, because then there is
no "approver's name" to show and HR may still staff the step (the backend
validates, and academic teams remain unstaffed).

**Implementation.** The form reads holdings through a new client-safe reader
`listRoleAssignments()` in `approver-roles-client.ts` (a
`/api/hr/role-assignments/` GET proxy was required — the server-only reader in
`approver-roles.ts` goes through `next/headers`, and value-importing it would
have put the server module into the client bundle, which the
`server-only-imports` guard refuses). The fill happens on first draw (when
holdings arrive) and in `changeRole`/`addStep` (event handlers) so a role picked
after load fills inline. The empty-lone-holder map is exactly one-holder-per-role
and carries the holder's name for the locked read-only display.

**Second request in the same pass: a role must not be reused across steps.**
Already enforced at every layer — the client `repeatedRole()` blocks the save,
`normalize_section_sequence` refuses server-side, and the
`section_workflow_role_unique` constraint holds at the database. The only
remaining gap was UX: the dropdown still *offered* an already-used role and only
errorred at save. The role `<option>` for a role already sitting on another step
is now `disabled` and labelled "— used in step N", so the chain cannot even be
described twice with one office. The save-time guard stays as the backstop.

**Tests.** `workflow-form-members.test.tsx`: 4 new tests — a single holder
locks the approver to their name (no picker shown) and submits exactly that id,
stays unstaffed with two holders, stays unstaffed on an academic team, and a
role used on step 1 is disabled on step 2. Frontend **488 tests / 70 files OK**;
`tsc --noEmit` and `eslint` clean. No schema change.

## Defect Fix (2026-10-07) — roles table said "No holder" for a role that has one

**Reported.** On the Approver Roles page, the Registrar row showed its usage
("Nama Dingo, who holds it institution-wide", "the 'netwoks workflow' workflow
(1 section and 1 member)") while the Institution-wide holders column read
"No holder — applications reaching this role have nobody to approve".

**Root cause.** `WorkflowRoleTable`'s holders column is fed a
`assignments: Record<roleId, RoleAssignment[]>` map, but the roles page passed
a hard-coded `assignments={{}}`. The column therefore always answered "No
holder", contradicting the backend usage lines and, for a live role held
institution-wide, loudly claiming applications would stall.

**Fix.** The roles page now loads the institution-wide assignments
(`listRoleAssignments()`) alongside the roles and passes them keyed by role id,
so the column shows the actual holder (with its Remove control) or a genuine
"No holder" warning only for an active role with nobody holding it. If that
fetch fails the page says so, and the column renders "Could not load the
holders" rather than repeating the hold-less lie. Later the table grew to show
team- and campus-wide holders too, at their own scope — see the 2026-10-08
entry below.

**Tests.** `approver-role-table.test.tsx`: new case — `assignments={undefined}`
shows "Could not load the holders" and not "nobody to approve". Existing
holder/no-holder/retired cases unchanged and green. Frontend eslint + `tsc`
clean.

## Completed (2026-10-08) — A role's scope lives where it is held, and the roles table says so

**What changed.** The "Institution-wide role" checkbox is gone from the role
editor (`/roles/<id>/edit`). A role's scope is decided by where it is held, on
the Approvers page: assigning a role its **first institution-wide holder** is
what makes it institution-wide — the same save promotes the role
(`create_role_assignment` sets `is_institution_wide=True` atomically with the
holding). PATCHing scope from the role endpoint is refused
(`update_approver_role` returns "A role's scope is decided on the Approvers
page..."), so there is exactly one way to make a wide role and it is the one HR
already looks in.

**Why the editor had to lose it.** The edit page was the *only* place the flag
could be set, and it sat beside fields that genuinely belong to the role — so a
Registrar-type decision looked editable next to "decides cancellations", and a
campus-held "Campus Registrar" could read as mis-configured. Moving it to the
Approvers page ties the scope to the holding that gives it meaning.

**Guards.** Promotion is refused while the role is still held team-wide or
campus-wide (`create_role_assignment` → "already held on a team or campus.
Remove those holders under Approvers first"). Promotion is one-way: removing an
institution holder does not silently demote the role, so a deliberately-wide
role stays wide until HR explicitly re-purposes it (it simply reads "No holder"
again, never a silent team role). The institution panel on the Approvers page
now offers only roles that are already institution-wide or not wide at any
scope, so a guaranteed-400 choice is off the menu.

**The roles table now reports the real scope.** The "Scope" column is derived
from the holdings, not a stale flag label: an institution-wide role reads
"Institution-wide", a role with a campus-wide holder reads "Campus-wide", one
with a team-wide holder reads "Team-wide", and only a role nobody holds wide
reads "Team role". The holders column lists every wide holder at every scope —
`user_name — team/campus name` for scoped holdings, with the same Remove
control the institution holder has — so "Champus Registrar held at a campus"
reads as exactly that instead of "Team role / Staffed through team
membership". The roles page now reads all three assignment lists and the team
and campus name maps to name the scopes.

**Tests.** Backend: `tests_teams.py` — granting a team role its first
institution holder promotes it (201, role flipped, promotion audited); a role
held on a team is refused at the institution scope (400, role stays team).
`tests_roles.py` — PATCHing scope is refused with the Approvers message, and an
unchanged scope sent alongside a real edit stays harmless. Frontend:
`approver-role-form.test.tsx` — no scope control on create or edit, and the
update payload never carries `is_institution_wide`; `approver-role-table.test.tsx`
— Team-wide and Campus-wide scope reads with their holder names, and scoped
Remove calls the right endpoint. Full suites: backend **1256 OK**, frontend
**490 OK**; eslint + `tsc --noEmit` clean.

## Completed (2026-10-08) — An institution-wide role is assigned to one approver, never a second

**What changed.** Once a role has an institution-wide holder, assigning that
role to a different person is refused, naming the current holder:
`create_role_assignment` raises `"<role>" is already held institution-wide by
<name>. A role has one institution-wide approver; remove that holder under
Approvers first, then assign another.` The Approvers institution panel also
stops offering a role that already has a holder — the rule is enforced on the
one real write path (the service the API calls), and the picker hides the
guaranteed-400 choice before HR can make it. Changing a holder is therefore
remove first, then assign.

**Where the rule stops.** Institution-wide only. A team or campus role keeps one
holder per team/campus and stays offered at other teams and campuses, so the
same role may still be held by different people at different places — that is
what the per-place rule (`(team, role)` / `(campus, role)` uniqueness) covers,
and it is unchanged. The panel's footer copy now says exactly this instead of
the old blanket "saving replaces that role's current holder at the chosen
scope", which stopped being true for the institution scope.

**A DB constraint was deliberately not added.** The write path is a single
service — the same place the promotion guard and the one-wide-role-per-person
rule already live — while a `unique(role)` constraint would (a) refuse migration
on any deployment already carrying two institution holders, and (b) rule out a
state the product still supports: several approvers of one role through section
members, and the legacy rows the resolver still reads as an ambiguity to leave
unstaffed rather than auto-decide. In production the service is the only code
that creates a holding.

**Auto-appointment became deterministic.** With at most one institution holder
creatable, a held role's step always staffs its single holder; a never-held role
still reads unstaffed. The old "two holders leave the step for HR to choose"
test is replaced by the refusal itself — the ambiguity it pinned can no longer
be created.

**Tests.** Backend `tests_teams.py`: the service refuses a second holder and the
chain still auto-appoints the first; API-level, the second grant is a 400
carrying "already held institution-wide by", with one holding left and the
refused person still not an approver. Frontend `wide-holding-panel.test.tsx`: the
institution role drop down omits a role that has a holder (and still lists that
holder with Remove), and all-held says "Remove a holder first" with no form; the
person-exclusion tests that used a held institution role moved to team scope,
where a held role is still offerable. Full suites: backend **1257 OK**,
frontend **492 OK**; eslint + `tsc --noEmit` clean; `makemigrations --check`
clean.

## Completed — System Admin Dashboard (2026-10-11)

Refinement unit `context/refinement/03-unit-system-admin-dashboard.md`. Not yet
committed.

**The surface.** The built-in Django admin is extended — not replaced — into a
developer/ops dashboard at `/system-admin/` (configurable via
`SYSTEM_ADMIN_URL_PREFIX`). `admin.site` is now `system_admin.sites.LuanarAdminSite`
via `AdminConfig.default_site` in `system_admin.apps.SystemAdminConfig`, which
replaces `django.contrib.admin` in `INSTALLED_APPS` but keeps the `admin` app
label, so every existing `@admin.register`, the `admin:` URL namespace, and the
login/logout flow are untouched. Project-level `backend/templates/admin/`
carries the three custom templates.

**Two tiers, by developer decision — spec A4's HR tier is dropped.** This
surface exists for *the developer* to observe system stats and performance;
HR is an end-user of the Next.js product (the HR dashboard), not a customer of
the ops console. So `get_dashboard_tier` returns only `superuser` / `plain`:
superusers get the stats grid, the system-health panel, and the recent
account-management actions panel on the index plus two health URLs; every other
staff account — including `hr` and anyone in a Django Group named `HR` — sees
stock, unmodified Django admin with none of those context keys. The tier is
enforced server-side before any superuser-only ORM query runs, and the health
views also re-check superuser on top of the site's `is_staff` gate.

**Stats (superuser only, each degrading to "Not yet available" independently).**
Leave applications by status + today/this-week; pending approvals system-wide
(`ApplicationStage.status = pending`); users total + active (30 days); documents
(active `SupportingDocument` count + summed `file_size`); background tasks
(queued `OrmQ`, failed/succeeded in 24h using django-q2 `Failure`/`Success` —
the spec's "recent errors" card takes this permitted simpler path rather than a
new log pipeline); database (`pg_database_size`, `pg_stat_activity` count).

**Health.** `gather_health_status()` runs three independent checks that never
raise: database `SELECT 1` latency (<200 ms = ok, else degraded),
task-runner freshness (last `Success.stopped` within 1h), and storage
reachability via a new `leave.services.storage.ping_storage()` that lists
buckets. SMTP is deliberately not probed automatically; the health page offers a
POST-only "send test email to my account" button instead.

**Account-management actions.** `grant_superuser`, `revoke_superuser`, and
`grant_staff_access` are attached to the user changelist. Each is gated three
ways: hidden from non-superusers (admin-action permissions), a server-side
`_require_superuser` on direct calls, and a confirmation step where the exact
target username must be typed. Exactly one account must be selected; self-revoke
is refused; every applied change writes an `AuditEntry` with one of three new
`AuditEntry.Action` codes (`system.superuser_granted`, `system.superuser_revoked`,
`system.staff_access_granted`, migration `audit/0020`).

**Tests.** `system_admin/tests.py` (35 tests): tier/HR-is-plain gates, stats
shape + single-stat degradation, recent-actions filtering, access matrix
(anonymous redirect, non-staff denied, plain staff stock admin, superuser
dashboard), all three health checks including the storage-on/down split, health
view access + test-email POST semantics, and the full action lifecycle
(confirmation required, mismatch refused, exactly-one enforced, self-revoke
refused, audit rows written, actions hidden from HR). Backend full suite
**1458 OK**; `manage.py check`, `makemigrations --check` clean.

## Completed — Broken-Merge Recovery, `workflows` → `org`/`approvals` Split, and Leave Feature Gaps (2026-10-14)

Recovery of merge commit `726ee04`, which had merged `feature/plans-teams` into
`development` with unresolved conflict markers committed (carried on by the
"commit remaining WIP" commit `9891935`). Resolution adopted `feature/plans-teams`
as canonical for every conflict and finished the incomplete refactor it began.

**The split.** Approval-chain models moved out of `workflows` into two new apps:
`org` (`Team`, `Workflow`, `Section`, `ApproverRole`, `Campus`, `SectionMember`,
and the role-assignment tables) and `approvals` (`ApplicationStage`,
`ApprovalDecision`, and related). `workflows` now holds only `Reassignment` and
`WorkflowMember`. String FKs were repointed and every production and test module
swept for stale imports.

**Non-destructive table move.** Production data lives in the old `workflows_*`
tables, so the split must not create, drop, or rename tables. Each moved model
keeps `Meta.db_table = "workflows_<model>"`, the same `db_table` is written into
the migration `CreateModel` options, and the five affected migrations are wrapped
in `SeparateDatabaseAndState(state_operations=[...], database_operations=[])`.
The result: model state follows the new app labels while the database is left
untouched, so `makemigrations --check` reports "No changes detected" and an
existing database is never altered. Field-level compatibility was verified
(the only diffs against history are FK app labels and dropped `help_text`).

**Leave feature gaps completed.** `ApprovalConflictError` in `workflows.services`
now refuses any `approve` that would leave the applicant's team over-subscribed,
using the same numbers as the calendar (`leave.conflicts.find_team_conflict`) and
mapped to `409 {reason: "team_conflict"}` by `ApprovalDecisionAPIView`.
`workflows.policies.user_can_view_team_calendar` scopes the team calendar to HR,
superusers, team members, section approvers/members, workflow members, and
team/campus/institution-wide role holders, returning 404 otherwise.
`GET /api/v1/leave/me/form-defaults/` returns the last live leave type (falling
back to the canonical annual type), the next working day (skipping weekends and
public holidays), and the resolved annual entitlement per annual-consuming type.
`/api/v1/setup/{status,templates,apply-defaults,rollover}/` and
`/api/v1/calendar/team/` are wired in `leave/urls.py`.

**Tests.** Backend full suite **1494 OK** (was 1484 with 19 failures + 6 errors
before this pass; `system_admin` 35/35, leave 476/476, workflows+approvals
419/419). `manage.py check` and `makemigrations --check` clean. Frontend
`instrumentation-client.ts` gained `export {}`, fixing
`TS2306: File is not a module` in `typecheck:test`; its 3 Vitest tests pass.

## Completed — Phase 2c Domain-Logic Split: `approvals` + `organisation` (2026-10-15)

Moved the approval-execution and organisation-administration code out of the
`workflows` monolith into their feature apps (§3.1). Every HTTP URL path, route
`reverse()` name, payload, and status code is unchanged; this is a pure
code-ownership move on top of the Phase 2b model moves.

**`approvals`** now owns: the delegation / reassignment / execution / decision
services (`approvals/services.py`), the approval + delegation + reassignment
serializers, the approval endpoints (former `workflows/approval_views.py`) and
the `DelegationViewSet` / `ReassignmentViewSet` (`approvals/views.py`), the
former `approval_payloads.py` (`approvals/payloads.py`), the delegation /
reassignment admins, and `approvals/urls.py` (registered in `config/urls.py`
before `workflows.urls`). `workflows/approval_views.py` /
`workflows/approval_payloads.py` were removed.

**`organisation`** now owns: the approver-role, role-assignment,
team-role-assignment, campus-role-assignment and campus services and their
serializers, the matching viewsets (`ApproverRole`, `RoleAssignment`,
`TeamRoleAssignment`, `CampusRoleAssignment`, `Campus`), the matching admins,
and `organisation/urls.py` (registered in `config/urls.py`).

**Boundary decisions (documented in `architecture.md` §3.1).** `TeamViewSet`
stays in `workflows/views.py` because `POST/PATCH /teams/` create/rewrite the
team's chain and share the URL with the team-admin actions; the pure team code
lives in `organisation` and is imported by `workflows` (`workflows →
organisation`). One read-only model exception: `organisation/services.py` reads
`workflows.models` (`Section`/`SectionMember`/`Workflow`) for approver-role usage
checks — a model reference only, never a service/view import.

**Verified.** `manage.py check` clean; `makemigrations --check` → "No changes
detected"; `workflows.tests_routing` 15 OK, `tests_approvals` 91 OK,
`tests_self_approval` 34 OK, `tests_roles`+`tests_teams`+
`tests_team_configuration`+`tests_workflow_members` 308 OK, `workflows.tests`
142 OK, `leave`+`notifications`+`plans`+`users`+`audit` 787 OK. Still pending
for the final sweep: the full `workflows` suite including `tests_migrations`,
and the frontend `npm test` / lint / build.

## In progress — Phase 2d Frontend Feature-Module Reorg (2026-10-15)

Pages move from the flat `/dashboard/**` tree onto one module root per module.
Old paths keep working via `next.config.ts` redirects. The legacy `/dashboard/**`
tree keeps `DashboardShell`; each module root renders a module-scoped
`ModuleShell` (its own nav + an "← All Apps" link back to `/`).

- **Shell split.** `(dashboard)/layout.tsx` is now only the auth guard; the
  original `DashboardShell` moved to a new `dashboard/layout.tsx` scoped to the
  legacy tree, so module pages no longer render two sidebars.
- **leave — DONE.** Pages moved to `/leave` (`drafts`, `new`, `[id]/edit`,
  `[id]/review`, `[id]/submitted`, `applications/[id]`); `apps-registry` leave
  route now `/leave`; ~50 link/redirect/test refs updated. `npm test` 960 OK,
  lint/typecheck/build clean.
- **approvals — DONE.** `/dashboard/approvals` → `/approvals`,
  `/dashboard/cover` → `/approvals/cover` (incl. `[id]`); approver-only
  redirects now go to `/`. Focused approvals suites 80 OK, lint/typecheck/build
  clean.
- **organisation — DONE.** `teams`, `campuses`, `roles`, `approvers` moved from
  `/dashboard/hr-admin/*` to `/organisation/*`; new `/organisation` index
  redirects to `/organisation/teams`; module nav wired to all four sections;
  registry route `/organisation`. Unauthorized-role guards now go to `/`.
- **hr-admin — DONE.** All remaining `/dashboard/hr-admin/**` (employees,
  leave-rules, leave-types, entitlements, calendar, leave-document-template,
  delegations, reassignments, plans, audit) moved to `/hr-admin/**`; registry
  route `/hr-admin`. Legacy redirect added after the organisation-specific ones.
- **documents — DONE.** Added a minimal `/documents` landing page (documents
  are attached to leave/approval records; no standalone library or list
  endpoint exists yet) and pointed the registry route at `/documents`.
- **Legacy tree** (`/dashboard`, `/dashboard/account`, `/dashboard/admin`,
  `/dashboard/plans`) is intentionally retained with `DashboardShell`; every
  old module path redirects to its module root. Full frontend suite green
  (960/960) and `npm run build` clean after all five modules.
- **Post-login landing — DONE.** `app/(auth)/login/page.tsx` now defaults the
  post-login redirect to the launcher `/` (was `/dashboard`); explicit
  `?redirect=` still wins. New `tests/login-page.test.tsx` (2) locks it in.
- **Backend verification — DONE.** Full `uv run manage.py test workflows`
  (incl. `tests_migrations`) = **620 tests OK**, exit 0 (~26 min).
- **Launcher endpoint defect — FIXED (2026-10-15).** The proxy (`apps/launcher/`)
  never matched the backend (`launcher/`), so the launcher grid was empty for
  every role. Registered `path("apps/launcher/", ...)`; added backend
  `launcher/tests.py` (8: per-role app sets + badge flow-through) and frontend
  `tests/launcher-proxy.test.ts` + `tests/app-launcher-grid.test.tsx` (grid
  renders cards, badge count, drops unknown keys, empty/failure states).
- **HR admin list key warning — FIXED (2026-10-15).**
  `hr-admin/employees` passed its search `<form>` (2+ siblings) to the client
  `EmployeesSection` via a JSX `filter` slot; across the RSC boundary React
  treated the form's children as an unkeyed list ("Each child in a list should
  have a unique key prop"). Same latent bug on `hr-admin/calendar` →
  `HolidaysSection`. Fix follows the pattern already documented in
  `TeamsSection`: the client sections render their own controls from plain data
  (`EmployeesSection` owns the `?search` form; `HolidaysSection` takes
  `availableYears` and owns the `?year` form). Pages still own the URLs.
  Updated `tests/hr-admin-form-overlays.test.tsx`; full suite 971 pass,
  lint/typecheck/build clean.
- **Module layouts RSC boundary error — FIXED (2026-10-15).**
  The five module layouts (`leave`, `approvals`, `organisation`, `documents`,
  `hr-admin`) were server components passing `navItems` (with lucide `icon`
  component references) to `ModuleShell`, a client component. React Server
  Components cannot serialize component objects across that boundary →
  "Only plain objects can be passed to Client Components from Server Components".
  Fix: added `"use client";` to each module layout so the icons stay in client
  scope. Verified end-to-end by logging in through the frontend and fetching
  `/hr-admin` (200, no error) plus every other module root.
- **Missing `/leave` index — FIXED (2026-10-15).**
  The restructure pointed the launcher registry and the leave sidebar at
  `/leave`, but no `app/(dashboard)/leave/page.tsx` existed (the canonical
  landing is `/leave/drafts`). Added `leave/page.tsx` redirecting to
  `/leave/drafts`, mirroring the `organisation/page.tsx` → `/organisation/teams`
  pattern. Verified `/leave` now returns 307 → `/leave/drafts` (200).
- **Launcher card hydration error — FIXED (2026-10-15).**
  `components/launcher/app-card.tsx` wrapped its `<div>` children in a `<p>`
  (invalid nesting → React hydration error); the outer element is now a `<div>`.
  `tests/app-launcher-grid.test.tsx` gained a guard that fails if React logs an
  invalid-nesting message (verified it catches the regression).
- **`components/ui/` purity — FIXED.** `components/ui/Stepper.tsx` imported
  `formatDateTime` from `@/lib/tracking/format` (a feature module). Moved the
  generic `formatDate`/`formatDateTime` to `lib/format.ts`, repointed all 17
  importers, and deleted `lib/tracking/format.ts`. `components/ui/` now imports
  only generic primitives.
- **Legacy shim — KEPT (decision).** `/dashboard` (+ account, admin/users,
  plans) and the 11 legacy→module redirects stay as-is; non-module pages have no
  module root of their own and old bookmarks keep working.
- **Remaining:** manual click-through (human step) for the §5 checklist; nothing
  else outstanding in Phase 2d.

## Completed — Separation of Duties: HR and the Team Manager (2026-10-17)

The API now enforces a strict handover. HR creates a team and names its manager,
and keeps the team's identity, wide-role holdings, and which chain routes; the
manager alone runs their own team's roster, chains, and step approvers. The
frontend now offers each role only the actions the server will accept.

### Backend enforcement
- New `workflows/permissions.py::IsTeamManagerOnly`: `has_permission` is active
  AND (superuser → allow) AND (HR → refuse) AND (has at least one managed team);
  `has_object_permission` resolves the team from the object via
  `.workflow` / `.team` / `.section`. HR → 403, a non-manager or a member with no
  managed team → 403, and a manager of *another* team passes the coarse check
  then 404s through the scoped queryset.
- `workflows/views.py` `get_permissions` maps the write actions to manager-only
  (WorkflowViewSet create/update/partial_update/members/remove_member;
  TeamViewSet members/member_candidates/workflow_members_pool + remove_member;
  SectionMemberViewSet create/destroy); reads stay `IsHROrTeamManager`.
- `workflows/services.py` gains `_require_team_manager`, used by
  `create_workflow` — its view has no object, so object-level checks never fire
  and a service guard is the only thing that can refuse HR. The other member
  services deliberately keep `_require_can_manage_team` so the HR-admin
  employee/team move flows (`users/serializers.py`) that call them with an HR
  actor still work: the permission layer is the enforcement boundary.
- **DRF gotcha:** `self.action` is the viewset *method name*, not the
  `url_path`, so the `get_permissions` mappings match `"members"`,
  `"member_candidates"`, `"workflow_members_pool"`.

### Backend tests
- New `workflows/tests_separation_of_duties.py`,
  `workflows/tests_team_management.py`, `workflows/tests_workflow_members.py`
  (35 + 61 OK) pin HR refusal and manager success end-to-end.
- Rewired the existing suites to act through a designated team manager
  (`dvc` role, `create_team_role_assignment(..., is_team_manager=True)`, a fresh
  manager per team to satisfy the one-wide-role-anywhere invariant) and to name
  the new manager-owned tests accordingly: `tests_teams.py` (103 OK),
  `tests_team_configuration.py` (95 OK), and the legacy
  `workflows/tests.py` (142 OK; `test_hr_can_create_a_workflow_for_a_team` →
  `test_manager_can_create_a_workflow_for_a_team`, likewise for editing steps).
- Full backend green: `workflows` 655 OK; `audit tests organisation` 73 OK;
  `users approvals leave` 632 OK; `notifications documents plans system_admin
  launcher config` 210 OK.

### Frontend
- New pure `lib/team-access.ts`: `visibleTeamTabs(isHr)` (HR → `overview` +
  `approvers`; manager → `overview` + `steps` + `members`), `canConfigureChains`
  (manager), `canRouteTeam` (HR).
- Page gating mirrors the API: the team detail tabs are filtered and its "New
  workflow" link is manager-only (the manager-only member-candidate feed is not
  fetched for HR); the workflows list hides "New workflow"/"Edit steps" from HR;
  the workflow detail hides "Edit steps" from HR; the new/edit workflow pages
  guard to managers and send HR back to the team's chain list / the workflow.
- `tests/team-access.test.ts` (6) and `tests/team-page-access.test.tsx` (4)
  pin the split. Full frontend suite 990 OK; tsc/eslint/`build` clean.
- Updated the stale `tests/module-layouts-client.test.ts` canary (≥5 → ≥4):
  the organisation module no longer passes icon components to `ModuleShell` —
  its `layout-client.tsx` maps icon *names* in the browser — so only four
  module layouts carry the RSC serialization hazard the guard watches.

### Follow-up — chainless team creation, manager-owned chains and routing
- HR no longer configures approval steps at all. `create_team` writes a team
  **without** a chain (a draft), optionally designating the manager in the same
  pass; `TeamSerializer` refuses `new_workflow`/`workflow` from HR with a 400
  keyed on that field, and `workflow` is read-only. The manager builds and edits
  chains through `POST /api/v1/workflows/` and `PATCH /api/v1/workflows/{id}/`
  (`WorkflowWriteSerializer`, `create_workflow`/`update_workflow`), and chooses
  which of the team's chains is in force through `POST /api/v1/teams/{id}/route/`
  (`route_team`; audit `TEAM` UPDATED, reason `Routed through "<name>".`). Routing
  a team at a chain it does not own, or as HR, is refused.
- Bug fix in `workflows/views.py`: `WorkflowViewSet.create/update` now also catch
  `TeamActionError`, so a chain write that fails a membership / one-stage-per-
  workflow rule surfaces as a 400 keyed on the field instead of an uncaught 500.
- Tests rewritten to the new contract: `workflows/tests.py`
  `WorkflowSerializerAtomicityTests` now drives `WorkflowWriteSerializer`;
  `audit/tests.py` creates the team as HR, designates a manager, and builds the
  chain as the manager; `tests/test_end_to_end.py` `hr_creates_team` now does the
  same handover. Added `TeamRoutingAPITests` (manager assignment on create,
  manager reassignment, manager route + audit, HR route→403, cross-team route→400).
  New helper `designate_manager` in the end-to-end spine uses a team-scoped
  `team_manager` role, since every shipped role in that journey is institution-wide
  and an institution-wide role cannot be a team's manager.
- Frontend cleanup: deleted the unused `components/hr-admin/team-form.tsx` and the
  dead `TeamWorkflowInput`/`TeamSectionInput` types plus `TeamInput.new_workflow?`
  in `lib/teams.ts`; `canRouteTeam` is manager-only (the earlier "(HR)" note was
  inverted). Backend `workflows audit tests` 728 OK;
  `tests_teams` 108 OK and `tests_team_configuration` 95 OK; frontend team/
  workflow tests green, `tsc`/`eslint` clean.

### Follow-up — a team manager can actually reach and run their team
- **Bug fixed:** a designated manager was an ordinary employee account, so
  `organisation.services.can_access_org` (HR/staff only) left the Organisation
  app out of the launcher entirely — the manager had no way to reach the roster
  and chains only they may write. It now also admits anyone who manages at least
  one team (`managed_team_ids_for`). The launcher module still holds no access
  rules of its own; each module answers `can_access_*`.
- **Auto-activation:** `create_team` now puts a team **active** when it is
  handed to a manager in the same request (audit `TEAM` ACTIVATED), instead of
  always landing a draft. A team with no manager stays a `DRAFT`, because nobody
  may configure it yet; `activate_team` still refuses a chainless draft, so the
  HR-only validation path is unchanged. The manager then builds and *routes* the
  chain, which is the manager's activation — `route` was already manager-only.
- Not a hazard: an unstaffed step does not silently strand applications —
  `DatabaseWorkflowProvider` refuses the submission naming the step, so routing a
  half-built chain surfaces as a loud, fixable error. The team detail "steps" tab
  copy was corrected to say so (it claimed an unstaffed step "blocks
  activation", which is no longer the gate).
- Tests: `launcher.tests.LauncherEndpointTests.test_a_designated_team_manager_reaches_their_team`
  pins the app set (an ordinary employee is still `{"leave", "documents"}`;
  a manager gains `organisation`, and `approvals` because a manager holds a real
  approver role). `TeamRoutingAPITests` gains the active-on-create and
  still-a-draft-without-a-manager pair. Backend
  `workflows organisation launcher users tests audit` 900 OK; frontend `tsc` /
  `eslint` clean and team/workflow suites green.

### Follow-up — a team member must share the *manager's* category
- The roster's eligibility rule is now measured against the **team manager's**
  own `EmployeeProfile.category`, not the `Team.category` field. Two call sites
  agreed on the rule: `organisation.services.add_team_member` (the write) and
  `TeamViewSet.member_candidates` (the picker), both now going through the new
  `organisation.services.team_manager_profile(team)`. A team not yet handed to
  a manager has no manager, so its own category stands in — reachable only in
  the service, since the `members`/`member-candidates` endpoints refuse HR.
- In practice the two categories already coincide: `create_team_role_assignment`
  refuses a holder whose category differs from the team's, and the manager is
  designated through that path. This makes the stated rule the one actually
  coded rather than an implicit consequence.
- Refusal message now names the governing category ("…takes only
  Administration employees") instead of restating the team's category twice.
- Frontend: `TeamMembersPanel` scope copy updated to "share your category as
  this team's manager". `tests/team-members-panel.test.tsx` assertion updated.
- Tests: 5 added to `workflows.tests_team_management.TeamManagementDelegationTests`
  (same-category added, other category refused naming the manager's category,
  picker offers only the manager's category, managerless fallback in the
  service); one wording assertion in `tests_workflow_members` updated.
  Verified: 904-test run had exactly one failure (that wording assertion),
  since fixed — `workflows.tests_workflow_members users` 217 OK, and the three
  modules that call `add_team_member` (`tests_separation_of_duties`,
  `tests_team_management`, `tests_workflow_members`) plus `tests_teams`,
  `tests_team_configuration` and `organisation` 305 OK.

### Bug — the roster picker was empty for every team manager
- **Symptom.** A manager opened their team's Members tab and the picker read
  "No employees to add to this team", with nobody offered. The backend was not
  the cause: `member-candidates` returned 8 candidates for the administration
  manager and 9 for the academic one against the real dev database.
- **Cause.** `teams/[id]/page.tsx` is a **Server Component**, and it filled the
  picker by calling `listTeamMemberCandidates` from `lib/team-members-client`,
  which is a *browser* helper: a bare relative `fetch("/api/hr/teams/<id>/member-candidates")`.
  From a Server Component that request carries no `Authorization` header — the
  `/api/hr/...` proxy answers 401 — and the call site's `.catch(() => [])`
  turned the failure into a silent empty list. Every other read on that page
  goes through `apiClientUrl`, which reads the token off the request cookies
  explicitly, which is why the team itself rendered while its candidates did not.
- **Fix.** Moved `listTeamMemberCandidates` into `lib/teams.ts` beside
  `getTeam`/`listTeamWorkflows`, reading `/api/v1/teams/<id>/member-candidates/`
  through `apiClientUrl`; removed it (and its now-unused type import) from
  `lib/team-members-client.ts`, which keeps only the browser *writes*. The
  page's fallback now `console.error`s instead of swallowing the reason, so the
  next failure of this kind is visible rather than silent.
- **Verified on the running app**, not just in tests: requesting
  `/organisation/teams/2?tab=members` as that manager now renders all 8
  candidates. Frontend: `tsc`/`eslint` clean, 68 team/roster/workflow tests pass,
  including two new ones in `tests/team-page-access.test.tsx` — the panel mock
  now records the `candidates` length, so "the read reaches the picker" is
  asserted, and HR is asserted not to read candidates at all.
