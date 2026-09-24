# Progress Tracker

Update this file after every meaningful implementation change.

## Current Phase

- Unit 20 — HR-to-Employee Data Integration (COMPLETE — backend + frontend)
- Unit 19 — Supporting Document Lifecycle (COMPLETE — backend + frontend)
- Unit 18 — Leave Cancellation (COMPLETE — backend + frontend)
- Unit 17 — Rejection, Correction, and Resubmission (COMPLETE — backend + frontend)
- Unit 16 — Approver Review and Decision (COMPLETE — backend + frontend)
- Unit 15 — Employee Application Tracking (COMPLETE)
- Unit 14 — Leave Validation and Submission (COMPLETE)
- Unit 13 — Leave Application and Drafts (COMPLETE), integrated onto `development`
- Unit 10 — HR Approved Leave Document Template (COMPLETE)
- Unit 9 — HR Emergency Reassignment (COMPLETE)

## Current Goal

- **Unit 20 — HR-to-Employee Data Integration** replaces the placeholder
  fixture rules provider with a real database-backed provider so the employee
  experience reflects the actual HR-track record: HR creates an employee →
  assigns grade/department/category → the system resolves entitlement and
  balance → the employee sees their correct profile, entitlement and balance
  on the dashboard.

  **Implementation complete (2026-09-24).** Backend: `DatabaseRulesProvider`
  (`leave/providers/database.py`) implements the full `RulesProvider` contract
  over `EmployeeProfile`, `GradeEntitlement`, effective-dated `LeaveRule`,
  `FinancialYear` and the ledger; `LEAVE_RULES_PROVIDER` now points at it.
  Structured `LeaveRule.eligibility_rules` (D7 vocabulary — gender /
  min_service / grade_range / employee_category) + `EmployeeProfile.gender`
  (`M`/`F`) carry what the eligibility validator enforces (free-text
  `eligibility` remains display-only). New authenticated-only (non-HR)
  endpoints `GET /api/v1/leave/my/overview/` and
  `GET /api/v1/leave/my/leave-types/` back the dashboard. Seed commands
  (`seed_dev_users`, `seed_approvals_dev`) share idempotent defaults via
  `leave/defaults.py` (entitlement bands A–C 21 / D–G 24 / H–U 30, built-in
  leave types with rules + eligibility, financial year covering today) and
  now run against the real provider. Frontend: `lib/leave-overview.ts` +
  `/api/leave/my/overview` + `/api/leave/leave-types` Next proxies,
  `lib/services/leaveTypes.ts` real fetch (replaces the Unit-4 mock), and the
  dashboard now shows the real employee record (grade, designation,
  department, category, gender, appointment date, financial year,
  entitlement/used/available) instead of hard-coded stat cards, with the
  "Awaiting My Approval" card fed by the real `approvals/capabilities` count.
  Verified: backend full suite 643 OK (serial + `--parallel auto`),
  `makemigrations --check` clean; frontend 277 tests OK, `tsc --noEmit`
  clean, `eslint` clean, `npm run build` clean.

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
- **Reconciliation.** The Unit 13 drafts list renders draft rows only (no
  submitted rows exist), so the in-app entry point to the tracker is the
  submission-confirmation link, not the drafts list.

## Completed

### HR track (Units 2–11) — merged via `feature/hr-track`

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
  - Backend: 265 → 299 tests (34 new) passing via `uv run manage.py test
    workflows` (131) then `--noinput`; `manage.py check` clean; migrations
    applied
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
## Completed (Unit 16 — Backend)

- **Approvals surface.** New `backend/workflows/` approval stack: `models.py`
  (`ApplicationStage` with optimistic `version` + DB check constraints, and
  append-only immutable `ApprovalDecision` records — ORM overrides raise
  `ImmutableDecisionError`, DB constraints block commentless rejects),
  `approval.py` (`decide()` transition table with optimistic concurrency →
  `StageChanged` on stale version, sequential-integrity `NotAllowed`, per-action
  comment rules, final approval closes the application), `policies.py`
  (`get_decision_authority`, `get_view_access` — `None` → 404 so existence is
  never leaked; `get_leave_history_scope` role matrix with fails-closed `None`
  guard; `get_leave_history`), `events.py`/`services.py`, and
  `fixture_provider.py` with locked route map: academic →
  Supervisor→HOD→Registrar→DVC, administration → HOD→Dean→Registrar→DVC,
  per-department overrides documented for tests/dev.
- **Approvals API** under `/api/v1/approvals/...`: `capabilities/`
  (`{is_approver, pending_count}`), list (`tab=pending|decided`, search by
  reference/name, pagination, oldest-first), detail (full review payload:
  application, employee-info whitelist, balance, leave history, documents,
  stage list, permissions, current stage), `decision/` (200 on land,
  400 bad action/blank comment, 403 not-current/already-decided/closed,
  409 stale version), `documents/{id}/download-url/` (signed URL, 503 when
  storage unavailable). `seed_approvals_dev` command idempotent with
  references 910001..910010.
- **Backend tests.** `workflows.tests_approvals`: **48 tests green, 0 failures/
  errors** — decision transitions, immutable records + DB constraints,
  optimistic concurrency, audit-event assertions, visibility matrices,
  API auth/paging/search/decisions, academic route, sign-off seed idempotency.
  Test-suite fixes landed: weekday-snapping cursor in the shared `submit()`
  helper (auto blocks never start on a weekend → `START_NOT_WORKING_DAY`
  elimination), per-class academic-route override (adds dean stage) in
  `VisibilityScopeTests` with `addCleanup` restore, registrar advance added
  before DVC scope checks, audit `.get()` scoped by `new_state="approved"`,
  and `update_profile` now mutates through the cached instance so the reverse
  relation stays coherent with the DB.

- **Frontend.** `lib/approvals/` (`types.ts` mirroring the serializer shapes,
  `format.ts` reusing Unit 15's `Africa/Blantyre` date helpers plus
  range/bytes/decision-label helpers, `service.ts` — status-aware `ApiError`
  for 400/403/404/409, `hooks.ts` `useApprovalsList`/`useApprovalDetail`,
  `capabilities-context.tsx` provider with `refresh()`), proxy routes
  `app/api/approvals/{capabilities,route,[id],decision,download-url}` built on
  the shared `proxyRequest`; `components/approvals/` — `ApprovalsList`
  (Pending/Decided tabs, 300ms-debounced search, pagination, per-tab empty
  states with role-appropriate copy, error/retry + skeleton), `ApprovalReview`
  (header + reference/resubmission badge + reuse of the Unit 15 `StatusBadge`,
  cards: application details, employee info, leave balance with requested-vs-
  available + over-balance note for annual leave, leave history, documents with
  download-url flow, approval-history timeline, `DecisionPanel` + accessible
  `DecisionDialog` handling approve/reject/return-for-correction, 400 inline
  comment errors, 403 read-only refetch, 409 stage-conflict reload,
  success toast + capabilities refresh); hand-rolled accessible primitives in
  `components/ui/` (`Dialog` with focus trap/Escape/aria-modal, `Tabs`, and
  `Textarea`) per project convention — no new packages. Nav: capability-driven
  `ApprovalsNavItem` (lucide `ClipboardCheck`, blue `pending_count` badge) in
  the dashboard shell, hidden until capabilities resolve; hardcoded approvals
  block removed. States/review page under `app/(dashboard)/approvals/`.
- **Frontend tests.** `tests/dashboard-shell.test.tsx` updated to
  capabilities-gated nav; new suites `approvals-service`, `approvals-format`,
  `approvals-list`, `approval-review` (19 new tests) + JSON fixtures in
  `lib/approvals/__fixtures__/`. **`npm test`: 35 files / 207 tests green;
  `tsc --noEmit`, `npm run lint`, `npm run build` all clean.**

## Completed (Unit 17 — Backend)

- **Resubmission surface.** New `backend/leave/services/resubmission.py` +
  `leave/views/resubmission.py` + `leave/urls.py` routes:
  `applications/<pk>/resubmission/` (GET context, PATCH save-changes),
  `applications/<pk>/documents/` (POST multipart), `applications/<pk>/documents/<document_id>/replace/` (POST), `applications/<pk>/documents/<document_id>/` (DELETE), `applications/<pk>/resubmit/` (POST `{row_version}`). Core rules implemented: PATCH save keeps `rejected`/`correction_required` status; resubmit → application `pending`, same current stage + approver (`ApplicationStage.version += 1`), same reference, `submission_cycle += 1`; immutable `ApplicationRevision` (`unique(application, revision_number)`, `changes` = snapshot diff vs previous, `None` for revision 1); `row_version` optimistic token bumped on every mutation; documents retire metadata-only (never physically deleted); vetoes: 409 `not_editable` while pending/approved, `not_resubmittable` unless `rejected`/`correction_required`, `version_conflict`, `workflow_inconsistent`, `approver_unavailable` for inactive approvers (Spec §9 message); 400 `validation_failed` with `{code, field, message, detail}[]`.
- **Edit context.** `resubmission/` GET returns the saved form payload +
  `permissions` (`editable`, `resubmittable`, `needs_resubmission`) +
  `documents: {active, retired, changes}` where retired rows carry
  `retire_reason`/`replaced_by_id`, plus `changes_preview` computed by the
  `leave/services/diff.py` snapshot engine (`dataclasses` + `json` only,
  no Django) — used by `test_diff.py` (11 tests). APIClient multipart tests use
  `SimpleUploadedFile` (a bare name/size shim never reaches `request.FILES`).
- **Review-fix pass.** Post-review corrections:
  `tracking/services.py` — `decision.stage.stage_order` (not bare `stage_order`) + `select_related("stage")`.
  `diff.py` — `_display_value` converts `start_date`/`end_date` to ISO strings; `_chain_ends_on_active` returns the active endpoint ID (or `None`) instead of bool; `_diff_documents` builds `replaced` before `added`, tracks endpoint IDs, and excludes only claimed endpoints from `added`.
  `resubmission.py` — `resubmit` acquires `_acquire_employee_lock(actor.id)` before `run_validation`; rebuilds `application.rules_snapshot` via `build_rules_snapshot(result.context)` and includes it in `save(update_fields=...)`; `upload_document` uses a unique `uuid` path segment while keeping `file.name` as `file_name`; `create_revision` sets `leave_type_id=application.leave_type_id` directly (raw provider ID, no FK lookup) so revisions survive even when no `LeaveType` row matches.
  `test_diff.py` — date expectations updated to ISO strings; `test_replacement_endpoint_is_not_reported_as_added` now expects both cert-v2.pdf and note.pdf in added; added `test_two_step_replacement_chain`.
  `edit-application.tsx` — `handleFieldChange` accepts `Partial<ResubmissionContent>` patch and merges via `setContext`; `handleSave` returns `row_version | null`; `handleResubmit` uses the returned version and stops if save fails; 409 specific codes (`approver_unavailable`, `workflow_inconsistent`) checked before generic `e.status === 409`; `showError` hides while `isLoading` is true; `setDirty(true)` removed from document handlers.
- **FOR UPDATE pitfalls (Postgres).** `select_for_update()` cannot be combined
  with `select_related` over nullable outer-join sides → `_lock_owned` locks
  only the base row then re-fetches relations; `resubmit()` uses `_lock_owned`.
- **Storage/Schema.** `SupportingDocument.file_url` widened to
  `URLField(max_length=2048)` (Supabase signed URLs exceed the default 200);
  migration `leave/0009_widen_supportingdocument_file_url` created and applied
  (also `0008_*`). `upload_document` and `_today()` (`timezone.localdate()`)
  are unit-tested via mocks in `test_resubmission.py`.
- **Approvals consumption (Unit 16 changes).** decided-tab excludes
  `assigned_approver == user AND current_stage.status == PENDING`; document
  download restricted to `SupportingDocument.Status.ACTIVE`;
  `approvals_serializers` fixed: `stage_order` read off `decision.stage`,
  `SupportingDocument` import, redundant `decisions` dict removed, decisions
  prefetched with `select_related("stage")`.
- **Tracking §8 extension.** `WorkflowTracking` contract gains
  `submission_cycle`, `resubmissions`, `decisions`; `_merge_real_data`
  overlays real revisions/decisions/`can_resubmit`; serializer renders the
  block; fixture scenarios stay additive.
- **Seed.** `seed_approvals_dev` extended with 5 Unit 17 scenarios
  (refs `LV-2026-27-910011..910015`, academic first-stage supervisor):
  rejected-then-edited, resubmitted-after-rejection, correction-then-edited,
  returned-then-resubmitted (annual, Feb 2027), rejected-with-replaced-document
  (compassionate, Mar 2027). Advance protocol supports `,edit` and `,resubmit`
  suffixes via `_advance`/`_edit_in_place`/`_resubmit_in_place`/
  `_replace_and_add_documents`. Idempotent (15 "Exists, kept" on re-run);
  stale dev app `LV-2026-27-000001` deleted from dev DB (overlap blocker).
- **Backend tests green.** `leave.tests.test_resubmission` 31 new tests,
  `leave.tests.test_diff` 11 new; full `leave` 295 and `workflows` 182 suites
  all pass. `application_resubmitted` is the resubmission audit/ApproverEvent
  action; `AuditEvent` is a generic-FK model (filter by `object_id`).

## Completed (Unit 17 — Frontend)

- **Types & service.** `lib/applications/resubmission-types.ts` (full
  `ResubmissionContext`, `ResubmissionFeedback`, `ChangesPreview`, validation
  shapes) and `lib/applications/resubmission-service.ts` (`ApiError`, `request`,
  `multipart` helpers; `getContext`, `saveChanges`, `addDocument`,
  `replaceDocument`, `removeDocument`, `resubmit`, `parseValidationBody`).
  `lib/tracking/types.ts` gained `submission_cycle`, `decisions: TrackingDecision[]`,
  `resubmissions: TrackingResubmissionEntry[]`. `lib/approvals/types.ts` gained
  `submission_cycle` + `is_resubmission` on `ApprovalListItem`, `ApprovalDecisionEntry`,
  `ApprovalChanges`, `ApprovalResubmission` blocks and `decisions[]` + `resubmission`
  on `ApprovalDetail`. `lib/leave-validation.ts` / `useLeaveValidation` accept
  optional `application_id` to exclude the current application from overlap checks.
- **Proxy route handlers** under `app/api/applications/[id]/resubmission/`
  (GET/PATCH), `.../documents/` (POST multipart), `.../[documentId]/replace/`
  (POST multipart), `.../[documentId]/` (DELETE), `.../resubmit/` (POST) — all
  built on the shared `proxyRequest` helper.
- **Edit page** at `app/(dashboard)/applications/[id]/edit` →
  `components/applications/resubmission/edit-application.tsx` ("use client"):
  fetches context via `getResubmissionContext`, redirects when `!can_edit`,
  renders `ApproverFeedbackCard`, `ResubmissionForm`, `ResubmissionDocuments`,
  `ValidationErrorsPanel`, `ResubmitConfirmDialog`, footer with Save/Resubmit/Cancel;
  `useUnsavedChangesGuard` for `beforeunload` + in-app navigation warning.
- **Resubmission components** (spec §9): `approver-feedback-card.tsx`
  (XCircle/CircleCross per action, reused by tracker banner + edit page),
  `resubmission-form.tsx` (controlled Unit 13 form, live working-days via
  `useLeaveValidation(application_id=...)`), `resubmission-documents.tsx`
  (react-dropzone add, Replace/Remove with `window.confirm`, retired history),
  `resubmit-confirm-dialog.tsx` (Dialog with `blockDismiss`, returns-to note,
  `ChangesSummary`, `approver_unavailable` banner), `validation-errors-panel.tsx`
  (aria-live alert list), `changes-summary.tsx` (before/after field rows +
  added/removed/replaced document lists — shared with approver card),
  `use-unsaved-changes-guard.ts`.
- **Approvals consumption** (spec §10): `ApprovalsListItem` gains `is_resubmission`;
  `ApprovalDetail` gains `decisions[]` (chronological) + `resubmission` block
  (`previous_decision`, `changes`, `history`). `approval-history-timeline.tsx`
  renders stage rows grouped by cycle (via `decisions[]`). `approvals-list.tsx`
  shows `ResubmissionBadge` from `is_resubmission`. `approval-review.tsx` top
  header already shows `ResubmissionBadge` on the reference.
- **Tracker fixtures** extended with `submission_cycle`, `decisions[]`, `resubmissions`
  for all 8 tracking fixtures, enabling cycle-grouped timeline rendering.
- **Backend diff improvement** (`leave/diff.py`): `leave_type` now surfaced as the
  type *name* (labelled) rather than the raw id, keeping comparison by id. Aligned
  `test_diff.py` (`test_leave_type_change_is_labelled_by_name`).
- **Verification:** `npm test` 207/207 green, `tsc --noEmit` clean, `npm run lint`
  clean, `npm run build` passes. Backend `uv run manage.py test` green.

## Completed (Unit 18 — Leave Cancellation)

- **Models** in `leave/models.py`: `CancellationRequest` (kind withdrawal /
  approved_leave, status pending/approved/rejected, reason 10–1000 after
  trim), per-request `CancellationApprovalStage` rows plus stage lifecycle
  (`waiting → pending → approved/rejected`, `not_reached`, `cancelled`),
  `EmployeeNotificationState` (pending/sent/failed/not_required) and the
  append-only `LeaveBalanceTransaction` ledger. **Backend package**
  `leave/cancellations/` (`services.py`, `serializers.py`, `views.py`,
  `fixture_balance.py`, `balance.py`, `events.py`, `permissions.py`).
- **Endpoints** (`backend/leave/urls.py:100-130`):
  `applications/{id}/cancellation-eligibility/` (GET — the four keys from
  `get_eligibility`: `cancellation_action`, `cancellation_blocked_reason`,
  `estimated_restoration_days` as a float, `restoration_financial_year`),
  `applications/{id}/cancel/` (POST `reason`/`confirm`/`expected_action` →
  `{kind, cancellation_request}`), `applications/{id}/cancellations/` (owner
  list, newest first), `approvals/cancellations/` (GET `?tab=pending|decided`,
  DRF pagination), `approvals/cancellations/{id}/` (detail + `balance_impact`),
  `.../decision/` (POST `decision`/`comment`/`stage_version`).
- **Rules.** Withdrawal: immediate `Cancelled`, no ledger rows, stages closed,
  audit + event after commit, notification `not_required`. Request: chain =
  Supervisor/HOD roles only, snapshot from the original workflow
  (`FIXTURE_WORKFLOWS` — default HOD only, academic Supervisor→HOD; no-profile
  users get HOD chain); one open request per application. Sequential stages;
  later-stage approver cannot act early (`not_current_approver` 403; read
  allowed for assigned approvers). Reject requires a comment and leaves the
  leave `Approved` with the balance untouched. Final approval restores exactly
  the original deduction to the debited FY, sets `carry_forward_eligible=false`,
  and is idempotent against replay/concurrent decisions. Start-date re-checked
  at final approval (`leave_already_started` 409; reject still allowed).
  Maternity/paternity/compassionate cancellations restore 0 days.
- **Guards.** `confirmation_required`/`reason_too_short`/`reason_too_long`/
  `comment_required` → 400; `not_current_approver` → 403; `application_not_found`
  → 404; `action_changed`/`stale_stage_version`/`request_not_pending`/
  `leave_already_started`/`not_cancellable_status`/`open_request_exists` → 409;
  `no_cancellation_approvers` → 422. Employee identity comes only from the token.
- **Balance integration** (`FixtureBalanceProvider.get_deduction` now uses
  `working_days or calculated_days or 0`): cancellation restoration is the
  inverse of the deduction and shows immediately in Unit 14 balance; ledger is
  append-only; withdrawn apps absent from Unit 16 queues and later decisions 409.
- **Frontend service layer** `lib/cancellation/` (`types.ts`, `service.ts`,
  `hooks.ts`, `format.ts`, `labels.ts`): fetchers for eligibility, submit,
  app-scoped list, approvals list/detail, decision submit; `ApiError` re-exported
  from `lib/approvals/service`; `useCancellationEligibility`, `useCancellations`,
  `useCancellationApprovalsList`, `useCancellationApprovalDetail`; `formatFinancialYear`,
  `startsInLabel`.
- **Proxy routes**: `app/api/applications/[id]/{cancellation-eligibility,cancel,cancellations}/`
  and `app/api/approvals/cancellations/{route,[requestId]/route,[requestId]/decision/route}`
  via the shared `proxyRequest` helper (relative-import depth per nesting level).
- **Components** `components/cancellation/`: `CancelApplicationButton`
  (Withdraw / Request per `cancellation_action`, muted blocked-reason),
  `CancelApplicationDialog` (Details→Confirm two steps, live 0/1000 counter,
  trim-then-validate, Back preserves text, double-submit guard, `action_changed`
  → message + parent refetch, server reason/confirmation/blocked codes mapped
  to field/inline errors), `CancellationStageStepper` (aria-label "Cancellation
  progress"), `CancellationCard` (self-hiding, status badge — slate "Cancelled",
  stepper, approved outcome with restored days + FY label / "No annual leave
  balance was affected.", rejected outcome with comment, notification chip,
  collapsible `Cancellation history (N)`), `CancellationRequestsTable`
  (Pending / Decided by me tabs, DRF pagination, "Starts in N days"/"Started",
  rows link to `/approvals/{appId}?cancellation={requestId}`),
  `CancellationDecisionPanel` (reason/balance-impact/stage tracker, Approve +
  Reject confirm dialogs, mandatory reject comment, "Leave has started; this
  request can only be rejected." disables Approve, 409 → toast
  "This request changed. Refreshing…" + refetch + parent refetch, 403 → read-only
  message).
- **Tracking integration**: `lib/tracking/types.ts` + fixtures gained
  `cancellation_action`, `cancellation_blocked_reason`,
  `has_open_cancellation_request`, `latest_cancellation`, `cancelled_at`,
  `estimated_restoration_days`, `restoration_financial_year`; `TrackingHeader`
  renders the cancel button and a "Cancellation requested" pill; `TrackingView`
  renders `CancellationCard` after the current-status card.
- **Approvals integration**: `approvals-hub.tsx` adds an Applications |
  Cancellation requests switch (Unit 16 queue unchanged); `approvals/[id]`
  reads `searchParams.cancellation` (a Promise) and `ApprovalReview` renders
  `CancellationDecisionPanel` at the top, refetching app detail + capabilities
  on decision.
- **Tests** (§3.11): backend `test_cancellation.py` (53 tests) covering the
  eligibility matrix, withdrawal, stage derivation, sequential approval, final
  approval + restoration idempotency, guards, authorization, and
  balance/regression; frontend new tests for the button/dialog (visibility
  matrix, 9/10/1000/1001 validation, two-step + Back, double-submit,
  `action_changed` + server-error mapping), the card (pending, approved with
  and without restoration, rejected-with-comment, history, notification chips),
  the approver panel (approve/reject flows, mandatory reject comment, started
  warning, 409 refetch, 403 read-only) and the approvals hub switch/list.
- **Verification:** frontend `npm test` 245/245 green, `tsc --noEmit` clean,
  `eslint` clean (one pre-existing warning in
  `edit-application.tsx:184` useCallback deps). Backend `uv run manage.py test`
  590/590 green (incl. tracking query-count 3→4), `manage.py check` clean.
  No new packages added.
- **Code-review pass (15 findings):** FKs on `LeaveBalanceTransaction`
  (`employee`/`leave_type`/`application`/`cancellation_request`) are now
  `PROTECT`, not `CASCADE` (models + migration 0010); shared `_iso` moved to
  `tracking/contracts.py`; `_approve_final` restores only an *actual* ledger
  deduction (`get_ledger_deduction`, never the display estimate) keeping
  `Σ deductions − Σ restorations` consistent; unused `permissions.py` classes
  removed; `_leave_started` uses the injectable `get_today`; unknown-404 detail
  test now exercises a real `<int:request_id>`. Frontend: dialog closes after a
  successful submit and clears the `action_changed` "refreshing" banner when
  fresh eligibility arrives; `CancellationCard` refetches off the tracking
  page's `lastRefreshed` signal; panel drives `canAct`/read-only decision from
  the backend's viewer-specific `can_act` + `my_decision` detail fields (no
  stage-list inference) and surfaces dialog errors without `commentError`;
  `TrackingCancellation.latest_cancellation` is typed as
  `TrackingCancellationRequest`; test helper uses the bound-query type.
  Skipped: serializer `max_length` on the decision comment would change the
  `comment_required` error shape (limit already enforced for approve + reject
  in `services.py`).

## Completed (Unit 20)

- **Backend — rules provider swap.** `DatabaseRulesProvider`
  (`leave/providers/database.py`) implements the full Unit 20 contract
  (`backend/docs/leave-rules-provider-contract.md`): `get_employee_for_user`,
  `get_leave_balance`, `get_financial_year_for`, `get_today`,
  `get_leave_type_rules` (effective-dated, with structured eligibility),
  `get_available_balance` and `get_public_holidays`. Durability notes:
  `max_duration_unit="calendar_days"`, `min_notice_unit="working_days"`
  (`LeaveRule` stores units silently), `LeaveType` has no active flag so
  `is_active=True` always, `EmployeeInfo.department_id=None` (department is
  free text), FY label `f"{start.year}-{end.year % 100:02d}"`, ledger net used
  = `Σ deductions − Σ restorations`. Provider wired via
  `config/settings/base.py` `LEAVE_RULES_PROVIDER`.
- **Models/schema.** `LeaveRule.eligibility_rules` JSONField (migration
  0011) holding the D7 vocabulary so the validator can materialize
  `EligibilityRule`s; `EmployeeProfile.gender` TextChoices `M`/`F` (users
  migration 0003); `LeaveRuleSerializer.validate_eligibility_rules` enforces
  the D7 shapes.
- **Endpoints.** `MyLeaveOverviewView` + `MyLeaveTypesView`
  (`leave/views/my_leave.py`, registered in `leave/urls.py`), both
  `IsAuthenticated` only — profile + balance + counts for the overview, and
  only leave types with an effective rule for the form.
- **Seeds via `leave/defaults.py`.** Shared idempotent
  `ensure_default_entitlements` / `ensure_default_leave_types_and_rules` /
  `ensure_default_financial_year` used by `seed_dev_users` and
  `seed_approvals_dev`. Business impact of the swap on seed tests: the
  approvals dev seed now runs real validation, so it ensures its own config
  (grades, entitlements, leave types+rules, financial year, employee gender
  for the maternity scenario) and drops the fixture-data lookup in
  `_leave_type_id`; `StubProviderMixin.use_stub` now also patches
  `workflows.approvals_serializers.get_provider` so approval review payloads
  stay deterministic under the injected stub.
- **Frontend.** `lib/leave-overview.ts` (typed overview + `formatIsoDate`),
  `/api/leave/my/overview` + `/api/leave/leave-types` Next proxy routes,
  `lib/services/leaveTypes.ts` real fetch mapping snake_case → camelCase
  (replaces the Unit-4 mock; consumers use only `id`+`name`), dashboard
  rewritten to render the real employee record and balances (removed the fake
  `"21"` available-balance and zero counts) with the approver card fed by the
  existing `approvals/capabilities` payload.
- **Tests.** `leave/tests/test_database_rules_provider.py` (contract suite
  incl. ledger, eligibility, FY, holidays, effective-dated rules),
  `leave/tests/test_my_leave_views.py`, `leave/tests/test_leave_rule_serializer.py`,
  `frontend/tests/leave-types-service.test.ts`,
  `frontend/tests/leave-overview.test.ts`. Full backend suite 643 OK (serial +
  `--parallel auto`); frontend 277 OK, tsc/eslint/build clean.

## Next Up

  Unit 21 — Workflow-to-Approver Integration: connect HR workflow
  configuration to real submitted applications (resolve the applicable
  workflow, route to the correct responsible approver, sequential progression,
  mandatory stages, department/faculty routing, delegated approvers and
  reassigned applications). Removes hard-coded development workflows; verify
  against the existing approvals API (Unit 16) and assignment policy. Depends
  on HR Units 6–9 and Employee/Approver Units 14–17.

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
- Document storage swaps to Supabase signed URLs — requires `SUPABASE_URL`,
  `SUPABASE_SERVICE_KEY`, `SUPABASE_BUCKET`

## Session Notes

- **Troubleshooting log introduced (2026-09-23):** added
  `context/troubleshooting-notes.md` — a standing log of errors, root causes,
  and fixes. Mandate recorded in `context/AGENTS.md`: every error/bug/debugging
  session must be appended there before moving on, in the shape of the existing
  entries (symptom / root cause / what to look for / fix). First entry:
  the `psycopg.errors.DeadlockDetected` failure caused by two `manage.py test`
  runs sharing the same test DB (`test_luanar_leave`), plus the general
  playbook for classifying `F` vs `E` and resetting the disposable test DB.
- **Unit 16 frontend complete (2026-09-22):** approver queue + review/decision
  UI landed. Key decisions: no Radix/21st.dev (nothing installed) — hand-rolled
  accessible `Dialog`/`Tabs`/`Textarea` primitives in `components/ui/` with
  focus trap, Escape (blocked while submitting), `aria-modal`, and pointer-
  outside dismiss; capability-driven nav via a React provider (render null
  while capabilities load — no nav flash), replacing the role-guess hardcode
  (`/dashboard/approvals` was a stale placeholder; real routes are `/approvals`
  per the spec's route-group placement). Review flow maps locked contracts:
  `stage_version` from `current_stage.version` (409 → reload banner), comment
  mandatory for reject/return (400 field errors inline), 403 → read-only
  refetch, append-only decisions so post-decision is a read-only summary with a
  "Return to approvals" link. Test gotchas: rows render in both the desktop
  table and mobile cards so queries use `getAllBy*`/`findAllBy*`; desktop +
  mobile sticky bars duplicate the action buttons (decision-dialog tests click
  the first match); the eslint `react-hooks/set-state-in-effect` rule rejects
  synchronous `setState` in effects, so hooks flip to `loading` via a
  microtask instead. `latestDecisionAction` was dropped in favour of passing
  the action through from the submit call. Full verification: frontend
  `npm test` 35 files/207 green, `tsc --noEmit` clean, lint clean, build clean;
  backend `manage.py check` clean (approvals suite unchanged since its 48/48
  green run).
- **Unit 19 spec drafted (2026-09-21):** `context/specs/19-supporting-document-lifecycle.md` — supporting documents get a full state-aware lifecycle. The four developer-approved decisions: (1) Unit 19 owns the document lifecycle (Unit 17's resubmission document flows reuse its service, not re-implement); (2) the file-storage abstraction + local-filesystem dev backend are built here — `LEAVE_STORAGE_BACKEND` dotted-path factory mirroring `get_provider()`, defaulting to `DevelopmentStorageBackend` (repo `storage/` root) so uploads/downloads work with no Supabase credentials; (3) draft-phase replace/remove keeps Unit 13 behavior (physically deletes old file+row), while post-submission replaces/removes retire and never delete (Unit 17 rule); (4) history = `SupportingDocument.status/retired_at/retired_by/retire_reason/replaced_by` + `document_uploaded`/`document_removed`/`document_replaced` AuditEvents, no new model. Download moves from stored signed URLs to one authenticated Django streaming endpoint (`content/?download=1`) opened via the Next proxy; `file_url` stays but now stores the content-URL. Depends on Units 16/17 status enum values — the edit/read-only gate is a membership check so it activates when those merge. Next; spec's §12 docs updates (architecture.md storage decision, README API table) are implementation-time.
- **Unit 19 shipped (2026-09-24):** backend + frontend complete and all green (see Current Goal). The spec's §12 doc updates are done: `architecture.md` §5.2 (storage decision), §12.8 (byte-access + no-permanent-deletion invariants), §13 decision table rows; root `README.md` API table now lists the config/list/upload/retrieve/delete/replace/history/content endpoints.
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
- **Unit 18 leave cancellation complete (2026-09-24):** backend package
  `leave/cancellations/` + endpoints (eligibility, cancel, request lists,
  approvals list/detail/decision), Supervisor/HOD-only chain from the workflow
  snapshot, sequential stages, mandatory reject comment, start-date re-check,
  audited, idempotent balance restoration to the debited FY with
  `carry_forward_eligible=false`; 53 cancellation tests, full backend suite 590.
  Frontend: `lib/cancellation/` service layer + 6 proxy routes, cancel
  button/dialog, cancellation card + stepper, approvals table, decision panel,
  tracking header/view integration, approvals hub switch + `?cancellation=`
  review panel. Verification: frontend 244/244, `tsc` and `eslint` clean;
  backend 590/590 green. Two component fixes during testing: the decision
  panel's read-only message was dead code after a 403 (now renders), and the
  dialog's `action_changed` path now calls the parent refetch as documented.
- **Unit 17 frontend complete (2026-09-23):** resubmission types/service,
  proxy handlers, edit page + orchestrator, resubmission components
  (feedback card, form, documents, confirm dialog, validation panel,
  changes summary, unsaved-changes guard), approvals types/consumption
  (decisions[], resubmission block, is_resubmission badge, cycle-grouped
  timeline), tracker fixtures extended, diff improvement (leave_type
  labelled by name). Verification: `npm test` 207/207, `tsc --noEmit`,
  `npm run lint`, `npm run build` all clean; backend `manage.py test`
  green. Route fix: tracker `OutcomePanel` "Edit & resubmit" link
  updated from `/dashboard/leave/{id}/edit` to `/applications/{id}/edit`.
  `useLeaveValidation` hook now passes `application_id` (optional) so
  overlap checks exclude the current application; test updated to
  expect `application_id: null`.- **Test infrastructure speedup (2026-09-24):** test runs were the bottleneck as
  the suite grew. Added `backend/config/settings/test.py` — MD5 password hasher
  (users are created in nearly every test), in-memory email backend, and a
  `TEST_DB_NAME` env override for the disposable test DB so parallel work
  sessions each run on their own DB (fixes the documented
  `DeadlockDetected` test-DB collision). Backend command is now
  `DJANGO_SETTINGS_MODULE=config.settings.test uv run manage.py test
  --keepdb --parallel auto` — full suite **591 tests in ~19 s** (was minutes
  of setup + PBKDF2 per user). Hoisted read-only fixtures in `workflows/tests.py`
  to `setUpTestData` for 5 high-count classes (WorkflowEndpoint/Admin/
  ActivationEndpoint, DelegationModelState/Service) — 56 tests still green;
  `ApprovalFixtureMixin` left on per-test `setUp` because it needs per-instance
  mock patchers and several tests mutate shared approver profiles. Frontend:
  `pool: "vmThreads"` (one jsdom per worker), `css: false`, and
  `// @vitest-environment node` on 6 pure-logic suites (approvals-format,
  tracking-format, tracking-service, entitlements, financial-years, leave-rules;
  approvals-service stays jsdom — it reads `window.location.origin`); added
  `npm run test:changed` (`vitest run --changed`). Frontend suite 97 s → 29 s,
  245/245 green; `tsc --noEmit`, lint, backend all clean.
