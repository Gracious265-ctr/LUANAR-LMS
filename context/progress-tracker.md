# Progress Tracker

Update this file after every meaningful implementation change.

## Current Phase

- Unit 10 — HR Approved Leave Document Template (COMPLETE)

## Current Goal

- Paused on HR work: Unit 10 is complete and no buildable HR unit remains.
  Units 9 and 11 are blocked on application rows owned by the Employee +
  Approver track. Resume when those application units land.

## Completed

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
  - Backend: 265 tests passing (review follow-up removed the unused backend
    preview endpoint + `render_preview`/`SAMPLE_VALUES`; catalog validation,
    endpoint auth/permissions/round-trip, `available_fields`, admin);
    `uv run manage.py test --noinput` OK (~571 s)
  - Frontend: `lib/leave-document-template.ts` (server-safe types + reads) and
    `lib/leave-document-template-client.ts` (client-safe
    `updateLeaveDocumentTemplate` → `/api/hr/leave-document-template` PATCH
    proxy), split like `workflows`; catalog comes from `available_fields`
  - `LeaveDocumentTemplateEditor` (controlled wording + field label/order/
    inclusion editor + signature area editor + save with backend errors and a
    saved notice) and `DocumentTemplatePreview` (live presentation preview using
    the catalog's sample values), one page under
    `/dashboard/hr-admin/leave-document-template`; "Document Template" sidebar
    item (`FileText`) + HR index card; HR index footer note updated
  - Frontend: 109 tests passing (15 new); `npm test`, `npm run lint`, and
    `npm run build` pass
  - Root `README.md` API table: `/api/v1/leave-document-template/` GET/PATCH rows
    added

- Unit 8: HR Delegation Management
  - Spec: `context/specs/08-hr-delegation-management-spec.md` (drafted, decisions
    approved: delegation is person-based (approver `User` → delegate `User`, not
    stage-based), delegate required at approval (HR confirms or substitutes the
    nomination), `active_delegation_for` is the Unit 21 routing boundary, the
    approver request *form* is a later-track unit, no notifications/audit here)
  - `Delegation` model in `workflows` (approver/delegate `User` FKs, `starts_on`,
    optional `ends_on` = open-ended, `request_reason`, `requested_by`, `status`
    requested/approved/rejected/cancelled, `decision_reason`, `decided_by`,
    `decided_at`, timestamps; CheckConstraint `ends_on >= starts_on`; a derived
    `state` tightening `approved` by the calendar — scheduled/active/ended);
    migration `0003_delegation`
  - `workflows/services.py`: `is_approver_user`, `resolve_delegate_user`,
    `open_request_exists`, `effective_end`, `find_conflicting_delegation`
    (reuses `leave.services.date_ranges_overlap`, open-ended = `date.max`),
    `active_delegation_for` (Unit 21 boundary), `require_decision_reason`, and
    `approve_delegation`/`reject_delegation`/`cancel_delegation` shared by
    serializer/actions/admin with `transaction.atomic()` and
    `DelegationActionError(field, message)`
  - `DelegationSerializer` (create: HR on behalf must pick an active
    approver-role user; self-service forces `approver` to the authenticated
    user; delegate must be active/approver-role/different; `ends_on >= starts_on`;
    one open request per approver) + `DelegationActionSerializer`;
    `DelegationViewSet` at `/api/v1/delegations/` (HR-only
    list/retrieve/approve/reject/cancel, create open to approvers via
    `IsApproverRoleOrHR`; `state=`/`approver=` list filters; `approve`/
    `reject`/`cancel` custom actions), SimpleRouter basename `delegation`
  - Django admin: `DelegationAdmin` as a view-only inspector (state column,
    status filter, raw_id/search on users), `has_delete_permission=False`
  - No delegation seeding (consistent with Units 6–7)
  - Backend: 241 tests passing (49 new: model states/constraint, services,
    endpoint auth/validation/actions, admin); `uv run manage.py test --noinput`
    (`Ran 241 tests` OK, ~502 s)
  - Frontend: `lib/delegations.ts` (server-safe reads) +
    `lib/delegations-client.ts` (client-safe `DELEGATION_STATE_CODES`/`LABELS`/
    `delegationStateBadgeClass` + `createDelegation`/`approveDelegation`/
    `rejectDelegation`/`cancelDelegation` → route-handler proxies), split like
    `workflows`; `/api/hr/delegations` POST + `/api/hr/delegations/[id]/approve`,
    `[id]/reject`, `[id]/cancel` POST proxies
  - `DelegationTable` (approver, delegate, period, state badge, review link,
    empty state), `DelegationForm` (approver select, optional delegate
    nomination, dates, reason), `DelegationReview` (detail + state badge;
    Approve/Reject for `requested`, Cancel for scheduled/active, mandatory
    reason + delegate select rendering backend errors)
  - Pages under `/dashboard/hr-admin/delegations` (index with `?state=` tabs +
    "New delegation request", `new`, `[id]` review); "Delegations" sidebar item
    (`UserCheck`) + HR index card; HR index footer note now lists only documents
    as a later unit
  - Frontend: 94 tests passing (21 new); `npm test`, `npm run lint`,
    and `npm run build` pass
  - Root `README.md` API table: `/api/v1/delegations/` list/create, `{id}/`,
    `{id}/approve/`, `{id}/reject/`, `{id}/cancel/` rows added

- Unit 7: HR Workflow Activation & Scheduling
  - Spec: `context/specs/07-hr-workflow-activation-scheduling-spec.md` (drafted,
    decisions approved: activation = setting `effective_from`; `is_active`
    meaningful once dated; approver availability = at least one active user per
    stage role; conflicts = scope overlap with any other applying workflow)
  - `Workflow` gains `effective_from` (null/blank = draft), `is_active`
    (default True), a derived `state` property
    (`draft`/`scheduled`/`active`/`inactive` via `timezone.localdate()`), and a
    `scope` tuple helper `(category or "", department or "")`; migration
    `0002_workflow_effective_from_workflow_is_active`
  - `workflows/services.py`: `scopes_overlap`, `missing_approver_roles`,
    `find_conflicting_workflow` (applying = `effective_from` set + `is_active`;
    excludes self), and `validate_workflow_for_activation` returning
    `ActivationIssue(field, message)` records (a small, documented deviation
    from the spec's `list[str]` so fields map to `effective_from` vs `detail`)
  - `WorkflowSerializer` adds `effective_from`/`is_active`/`state` and
    validates activation/scheduling using the shared service: missing-role
    errors surface as `{"detail": [...]}` (DRF normalizes dict values to
    lists), scope conflicts as `{"effective_from": [...]}`; deactivation and
    draft edits always allowed
  - Django admin: `effective_from` + `is_active` columns, `is_active` filter,
    `WorkflowAdminForm.clean()` guard reusing `validate_workflow_for_activation`
  - Backend: 192 tests passing (21 new: service combos, endpoint schedule/
    activate/conflict/deactivate, admin form guards); `uv run manage.py test --noinput`
  - Frontend: `Workflow`/`WorkflowInput` gain the new fields; `WorkflowState`
    type + `WORKFLOW_STATE_LABELS` + `workflowStateBadgeClass`
    (draft/active/scheduled/inactive colors) in the client-safe
    `lib/workflows-client.ts`, re-exported by `lib/workflows.ts`
  - `WorkflowTable` adds "Effective from" (dash for drafts) + a state badge;
    `WorkflowForm` adds an "Effective from" date input (blank = draft) and an
    "Active" checkbox surfaced once a date is set / editing a dated workflow;
    pages and proxies unchanged
  - Frontend: 73 tests passing (5 new); `npm run lint` and `npm run build` pass
  - Spec: `context/specs/06-hr-workflow-builder-spec.md` (drafted, decisions
    approved: role-based stages (not named people) with person resolution
    deferred to Unit 21; nothing seeded — start empty; scope is category +
    department, both blank means any)
  - `workflows` app models: `Workflow` (unique name; optional `employee_category`
    from `EmployeeProfile.Category`; optional `department`; ordering by name)
    and `WorkflowStage` (FK `workflow` related_name="stages"; `order`;
    `approver_role` from `supervisor`/`hod`/`dean`/`registrar`/`dvc`/`hr`,
    sourced from `User.Role`; CheckConstraint `order >= 1`; UniqueConstraint
    `(workflow, order)`); migration `0001_initial`
  - `workflows/services.py`: `StageSequenceError` + `normalize_stage_sequence`
    (validates non-empty, valid role, positive+unique orders, no duplicate
    roles; renumbers to 1..N) shared by serializer and admin guard
  - `WorkflowSerializer` (nested writable stages; required trimmed unique name;
    PATCH replaces the stage list wholesale inside `transaction.atomic`) and
    `WorkflowStageSerializer`; `WorkflowViewSet` at `/api/v1/workflows/`
    (list/create/retrieve/patch, no delete, HR-only via `IsHRRole`,
    `prefetch_related("stages")`)
  - Django admin registration (`WorkflowStageForm`, `WorkflowStageInlineFormSet`
    rejecting duplicate roles, `WorkflowStageInline` `extra=1`/`min_num=1`
    `validate_min=True`), `has_delete_permission=False`, list `stage_summary`
    reads the prefetched stages
  - Backend: 171 tests passing (27 new: model constraints, service, endpoints,
    admin guards); `uv run manage.py test --noinput`
  - Frontend: `lib/workflows.ts` (server-safe reads + re-exports) split from
    `lib/workflows-client.ts` (client-safe constants/labels + create/update →
    route-handler proxies) so forms never pull `next/headers` into the client
    bundle; `/api/hr/workflows` POST + `/api/hr/workflows/[id]` PATCH proxies
  - `WorkflowTable` (name, scope, sequence `role → role → …`, edit link, empty
    state) + `WorkflowForm` (name, category select with "Any category",
    department, ordered stage builder with add/remove/move-up/move-down,
    approver-role select per stage)
  - Pages under `/dashboard/hr-admin/workflows` (list, new, `[id]/edit`),
    "Workflows" sidebar item (lucide `Workflow`) + HR index card; HR index
    footer note now only lists delegation and documents as later units
  - Frontend: 68 tests passing (13 new); `npm run lint` and `npm run build` pass

- Unit 5: HR Financial Year and Calendar Configuration (COMPLETE)
  - Spec: `context/specs/05-hr-financial-year-calendar-spec.md` (drafted, decisions
    approved: explicit `is_active` flag with exactly one active period; nothing
    seeded; single "Calendar" page under `/dashboard/hr-admin/calendar`)
  - `FinancialYear` (start/end dates, `is_active`; CheckConstraint
    `end_date >= start_date`; ordering `-start_date`) and `PublicHoliday`
    (`name`, `date` unique; ordering `date`) models; migration
    `0003_financialyear_publicholiday`
  - `leave/services.py`: `date_ranges_overlap`, `find_overlapping_financial_year`,
    `financial_year_for_date`, `active_financial_year`, `public_holidays_between`
  - `FinancialYearSerializer` (required dates, end >= start, non-overlap
    excluding self, atomically deactivates other active periods when
    `is_active=True`) and `PublicHolidaySerializer` (non-blank name, unique
    date excluding self)
  - `FinancialYearViewSet` + `PublicHolidayViewSet` at `/api/v1/financial-years/`
    and `/api/v1/public-holidays/` (list/create/retrieve/patch, no delete,
    HR-only via `IsHRRole`; holiday `year=YYYY` filter)
  - Django admin registration with form guards (`FinancialYearAdminForm`,
    `PublicHolidayAdminForm`), `has_delete_permission=False`, and
    `FinancialYearAdmin.save_model` deactivates the previous active period
  - Backend: 144 tests passing (45 new: FY resolution, endpoints, holidays,
    admin guards); suite needs `--noinput` and ~284 s — run via the bash tool
    with a timeout ≥ 420000, not the default VSCode one
  - Frontend: `lib/financial-years.ts` (server-safe reads + `financialYearStatus`
    active|upcoming|past) and `lib/financial-years-client.ts` (client-safe
    create/update helpers), `/api/hr/financial-years` + `/api/hr/public-holidays`
    POST/PATCH proxies, `FinancialYearTable`/`FinancialYearForm` +
    `PublicHolidayTable`/`PublicHolidayForm`
  - Pages under `/dashboard/hr-admin/calendar` (two-section index with holiday
    `?year=` filter, financial years + public holidays), `financial-years/new`,
    `financial-years/[id]/edit`, `holidays/new`, `holidays/[id]/edit`
  - "Calendar" sidebar item (`CalendarDays`) + HR index card
  - Frontend: 55 tests passing (16 new); `npm run lint` and `npm run build` pass
  - End-to-end smoke tested through the Next.js proxy (create/patch FY + holiday,
    overlap 400, duplicate holiday 400, exactly-one-active, unauth 401, page
    renders + prefill, non-HR 307, unknown-id 404); smoke data cleaned up

- Unit 4: HR Leave Type and Rule Management
  - Spec: `context/specs/04-hr-leave-type-rule-spec.md` (approved)
  - `LeaveType` (name unique, code unique/blank) and `LeaveRule` (FK to leave
    type, `max_duration_days >= 1`, `min_notice_days >= 0`,
    `requires_supporting_document`, `consumes_annual_entitlement`,
    `effective_from`) models; save-time name/code normalization and
    `code = slugify(name)` when blank; DB check constraints; migration
    `0002_leavetype_leaverule`
  - `leave/services.py`: `normalize_leave_code` + `resolve_leave_rule(...)`
    (newest effective rule on/before `as_of` wins; accepts an instance or PK)
  - `LeaveTypeViewSet` + `LeaveRuleViewSet` (list/create/retrieve/patch, no
    delete) at `/api/v1/leave-types/` and `/api/v1/leave-rules/`, HR-only via
    `IsHRRole`; rule list filters `leave_type=` and `effective=current|upcoming`
  - `LeaveTypeSerializer` derives the code from the name when blank and rejects
    duplicate name / duplicate effective code; `LeaveRuleSerializer` exposes
    read-only `leave_type_code`/`leave_type_name` and validates bounds
  - Django admin registration for both models (filters/search/autocomplete;
    no hard delete)
  - `_seed_default_leave_types` seeds annual → 30 (consumes entitlement),
    maternity → 90, paternity → 10, compassionate → 5 idempotently (get_or_create
    keyed on leave_type + effective_from)
  - Backend: 99 tests passing (26 users + 73 leave: rule resolution,
    leave-type/leave-rule endpoint auth/permissions/validation, seed idempotency)
  - Frontend: `lib/leave-rules.ts` (types + `listLeaveTypes`/`getLeaveType`/
    `listLeaveRules`/`getLeaveRule`/`leaveRuleStatus`) plus client-safe
    `lib/leave-rules-client.ts` (create/update helpers → route-handler proxies)
    — split so the forms never pull `next/headers` into the client bundle
  - `/api/hr/leave-types` and `/api/hr/leave-rules` POST/PATCH proxies,
    `LeaveTypeTable`/`LeaveTypeForm` + `LeaveRuleTable`/`LeaveRuleForm`
  - Pages under `/dashboard/hr-admin/leave-types` (list, new, edit) and
    `/dashboard/hr-admin/leave-rules` (list with All/Current/Upcoming tabs +
    leave-type filter, new, edit)
  - "Leave Rules" + "Leave Types" sidebar items and HR index cards
  - Frontend: 39 tests passing (18 new); `npm run lint` and `npm run build` pass
  - End-to-end smoke tested through the Next.js proxy (create/patch leave type
    and rule, prefill on edit, non-HR 307); smoke data cleaned up

- Unit 3: HR Grade and Annual Entitlement Configuration
  - Spec: `context/specs/03-hr-grade-entitlement-spec.md` (approved)
  - `GradeEntitlement` model in `leave` app (grade range, days, `effective_from`;
    DB check constraints for `days >= 1` and `grade_start <= grade_end`; save-time
    normalization), initial migration
  - `leave/services.py`: `resolve_grade_entitlement(grade, as_of=None)` plus
    `normalize_grade`/`grade_in_range`/`ranges_overlap` helpers — effective-dated
    resolution, newest rule wins on/after its `effective_from`
  - `leave/serializers.py` validates start <= end, days >= 1, required
    `effective_from`, and rejects a range overlapping **any** existing rule
    regardless of effective date (excluding self on update)
  - `GradeEntitlementViewSet` (list/create/retrieve/patch, no delete) with a
    `resolve` action (`?grade=` required, optional `as_of`), HR-only via
    `IsHRRole`, routed at `/api/v1/entitlements/`
  - Django admin registration for `GradeEntitlement`, with a `save_model`
    overlap guard using the same `leave/services.py` rule
  - `seed_dev_users` seeds the 3 default bands idempotently (A–C→21, D–G→24,
    H–U→30), effective today
  - Backend: 60 tests passing (26 users + 34 leave: service resolution, HR
    endpoint auth/permissions/validation, admin form overlap guard, seed
    idempotency)
  - Frontend: `lib/entitlements.ts` types/helpers, `/api/hr/entitlements`
    POST/PATCH proxies, `EntitlementTable` + `EntitlementForm`, pages under
    `/dashboard/hr-admin/entitlements` (list with resolve widget, new, edit),
    "Entitlements" sidebar item + HR index card (20 frontend tests total)
  - EmployeeForm upgrade: grade input is a native combobox (`<datalist>`) —
    grades expanded from currently effective entitlement ranges are offered as
    dropdown suggestions while manual entry stays available (20 tests)
  - Frontend `npm run lint` and `npm run build` pass
  - This machine: `ALTER USER luanar CREATEDB` applied so `uv run manage.py test`
    runs directly

- Unit 2: HR Employee Directory
  - Spec: `context/specs/02-hr-employee-directory-spec.md` (drafted, approved)
  - `EmployeeProfile` model in `users` app (designation, department, category,
    grade, appointment_date; OneToOne to `User`), migration `0002_employeeprofile`
  - Django admin registration with filters/search/autocomplete
  - `IsHRRole` permission; `EmployeeViewSet` (list/create/retrieve/patch, no
    delete) with `search=`/`ordering=`, routed at `/api/v1/employees/`
  - Create links an existing user by email or creates a new user with an
    unusable password (role `employee`); `is_active` mapped to `User.is_active`
  - `seed_dev_users` now also upserts employee profiles for all 7 roles
  - Backend: 26 tests passing (`EmployeeEndpointTests` covers auth, roles,
    create/rename/conflict, search, ordering, 405)
  - Frontend: `EmployeeTable` + `EmployeeForm` components, list/new/edit pages
    under `/dashboard/hr-admin/employees`, route-handler proxies for POST/PATCH,
    "Employees" sidebar item, 4 table tests (10 frontend tests total)
  - Frontend `npm run lint` and `npm run build` pass
  - End-to-end smoke tested through the Next.js proxy (create, deactivate,
    reactivate, non-HR 307/403); README API table updated

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
  - Stat-card icon styling now uses a static Tailwind class map (dynamic
    `bg-${color}-subtle` classes were not generated by Tailwind)
  - Sign-out wired into the dashboard header via `/api/auth/logout`
  - Removed the dark-mode toggle and `.dark` token overrides to match the
    documented light-only theme decision
  - Added `frontend/components/ui/` and root `storage/` placeholder directories
  - Strong development `SECRET_KEY` replaces the short placeholder
  - `User` registered in Django admin with role columns/filters
  - `RefreshView` now uses SimpleJWT's `TokenRefreshView`; login is rate-limited
    (`login` scope, 10/min)
  - Sidebar selection now derives from the current route
  - Frontend tests gained sign-out and no-theme-toggle assertions

## In Progress

- None.

## Next Up

- This developer owns the HR track only (Units 2–11). Units 12+ belong to the
  Employee + Approver track, so Unit 12 is **not** ours to build.
- Remaining HR units are both blocked on application rows that the
  Employee + Approver track has not produced yet:
  - Unit 9 — HR Emergency Reassignment (view applications requiring
    intervention, reassign pending applications to replacement approvers with a
    mandatory reason, notify affected users, preserve reassignment history).
    **Deferred (2026-09-17, developer decision):** every deliverable needs
    application rows, which do not exist until Units 13+ and are consumed in
    Unit 21.
  - Unit 11 — HR Finalized Leave and Audit View. Depends on finalized
    applications/history, so it is blocked the same way.
- No buildable HR unit remains until the application units land. **Decision
  (2026-09-17): pause HR work** and resume Unit 9 (then Unit 11) once the
  Employee + Approver track produces the application model and rows.

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
  superseding same-range rules. This intentionally drops the build-plan §4
  Unit 3 "future-effective entitlement changes" supersession mechanism for V1
  (user decision, 2026-09-17); `effective_from` still governs resolution and
  future-dated rules for previously unmapped bands remain supported.

## Session Notes

- Unit 9 deferred (2026-09-17, developer decision): HR Emergency Reassignment
  operates on pending applications, which do not exist until Units 13+ and are
  consumed in Unit 21 — nothing is implementable yet. Unit 10 was built next;
  Unit 11 is blocked for the same reason. Resume Unit 9 once applications exist.
- Unit 10 backend suites green (265 tests) and frontend suites green (109
  tests); `uv run manage.py test --noinput` (~571 s) and `npm test`, plus
  `npm run lint` and `npm run build`
- Unit 10 review follow-up (2026-09-17): removed an unused backend `preview/`
  endpoint plus `render_preview`/`SAMPLE_VALUES` and the frontend
  `getLeaveDocumentTemplatePreview`/`TemplatePreview` types (nothing consumed
  them — preview is client-side only); moved the field catalog to a single
  backend definition exposed as read-only `available_fields`, so the frontend no
  longer duplicates keys/labels/samples; tightened the admin to fully
  view-only; replaced the hardcoded "2000 characters" message with
  `MAX_TEXT_LENGTH` and the O(n²) duplicate-key scan with a set
- Unit 10 note (2026-09-17): the template is a configuration singleton in the
  `documents` app, not a document. It stores the fixed data-field catalog's
  label/inclusion/order and signature captions; values always come from the
  approved application record, so template customization cannot alter approved
  application data. The real renderer is Unit 23.
- Unit 10 note (2026-09-17): logo/branding is header *text* only — image upload
  would hit the file-storage decision that architecture.md still marks TBD.
- Unit 10 note (2026-09-17): `fields`/`signature_areas` are validated JSON
  columns rather than relational inline rows — light config for one singleton,
  documented as a divergence from the `WorkflowStage`-style relational pattern.
  A field list can never exceed the catalog size (allowed-key + unique-key
  validation), so no separate max-count check is needed.
- Unit 10 note (2026-09-17): singleton API is an `APIView` (GET/PATCH) rather
  than a `ViewSet`; the default template uses `get_or_create(pk=1)` in
  `documents/services.get_template()` so reads never 404 and no seed/command
  change is needed.
- Unit 10 note (2026-09-17): the catalog's `sample` values are presentational
  preview data only; the frontend reads them from `available_fields` and the
  authoritative Unit 23 renderer will use real approved-application data.
- Unit 8 backend suites green (241 tests) and frontend suites green (94 tests);
  `uv run manage.py test --noinput` (~502 s) and `npm test`, plus `npm run lint`
  and `npm run build`
- Unit 8 note (2026-09-17): delegation is person-based (approver → delegate
  `User`), so a delegation carries no workflow/stage FK; the role shown is the
  approver's role and the actual pending-application transfer is Unit 21 via
  `active_delegation_for`
- Unit 8 note (2026-09-17): the delegate is confirmed at approval time — the
  request's nomination is optional and HR substitutes when approving; approve
  also rejects period overlap with another approved delegation via
  `find_conflicting_delegation` (reusing `leave.services.date_ranges_overlap`)
- Unit 8 note (2026-09-17): delegations are view-only in Django admin (decisions
  are API-driven) and `approve`/`reject`/`cancel` are implemented as shared
  service functions so the serializer/views/admin stay thin
- Unit 8 note (2026-09-17): seed unchanged — no delegation rows; the seeded
  per-role users provide approvers/delegates for testing
- Unit 7 note (2026-09-17): DRF normalizes every value in a serializer
  `ValidationError` dict into a list (`as_serializer_error`), so the activation
  missing-role error is `{"detail": ["No active user exists for: Dean."]}`
  rather than the spec's single-string `detail`; the frontend `apiErrorMessage`
  still extracts it as `detail: ...`
- Unit 7 note (2026-09-17): `validate_workflow_for_activation` returns
  structured `ActivationIssue(field, message)` records instead of the spec's
  bare `list[str]` so the serializer can map issues to `effective_from` (scope
  conflict) vs `detail` (missing approver roles) from one shared implementation
- Unit 7 note (2026-09-17): PATCH still replaces stages wholesale (Unit 6
  contract), so deactivation/editing requests must resend the stage list
- Unit 1 implementation complete; review fixes applied
- PostgreSQL 18 installed on Windows, user `luanar` created with `CREATEDB` privilege
- On the Linux dev machine the `luanar` role lacks `CREATEDB`; run
  `sudo -u postgres psql -c "ALTER USER luanar CREATEDB;"` to use
  `uv run manage.py test` directly (otherwise point `DATABASE_URL` at a
  throwaway instance)
- Unit 2 backend suites green (26 tests) and frontend suites green (10 tests);
  both run via the throwaway Postgres workaround on this machine
- `ALTER USER luanar CREATEDB` applied on this machine (2026-09-17), so
  `uv run manage.py test` now runs directly (no throwaway workaround needed)
- Unit 3 backend suites green (60 tests) and frontend suites green (21 tests)
- Background tasks use Django-Q2 with Postgres as ORM broker (no Redis)
- Backend: `uv run manage.py test` passes all 60 tests
- Frontend: `npm test` passes all 21 tests
- Unit 3 flow review fixes (2026-09-17): admin overlap guard moved to a
  `GradeEntitlementAdminForm.clean()` (was a `save_model` raise that 500'd);
  `has_delete_permission=False` in admin to honor no-hard-delete; date defaults
  now use `timezone.localdate()` on the backend and a timezone-aware
  `currentDateIso()` on the frontend (was UTC `toISOString`, off by a day after
  22:00 CAT); list/new copy no longer promises future-effective same-range
  changes
- Development users seeded with password `testpass123`
- Optional dev superuser `admin@test.luanar` / `testpass123` created for Django
  admin and Django-Q2 task inspection
- Unit 4 backend suites green (99 tests) and frontend suites green (39 tests);
  `uv run manage.py test` and `npm test`, plus `npm run lint` and `npm run build`
- Unit 4 note (2026-09-17): `LeaveType.code` is a stable, unique identifier set
  on save from the name when blank — leave types are edited, not deleted, so
  historical rule lookups keep working
- Unit 4 note (2026-09-17): custom leave types from the E2E smoke test were
  removed from the dev DB afterward (rules: 4, types: 4)
- Unit 5 backend suites green (144 tests) and frontend suites green (55 tests);
  `uv run manage.py test --noinput` and `npm test`, plus `npm run lint` and
  `npm run build`
- Unit 5 note (2026-09-17): public-holiday integration is out of scope per
  build-plan §9 — the resolve boundary (`financial_year_for_date`,
  `public_holidays_between`) is ready for the leave-application units, but the
  source/fallback decisions remain TBD
- Unit 6 backend suites green (171 tests) and frontend suites green (68 tests);
  `uv run manage.py test --noinput` and `npm test`, plus `npm run lint` and
  `npm run build`
- Unit 6 note (2026-09-17): DRF test `APIClient` sends dict bodies as multipart
  when `format="json"` is omitted, which silently drops nested list-of-dicts
  (`stages`) — workflow POST/PATCH tests must pass `format="json"`, and
  child-serializer errors surface as `{"stages": {"0": {...}}}`
- Unit 6 note (2026-09-17): runtime-only UI constants (approver roles, category
  labels) live in the client-safe `lib/workflows-client.ts`; the server-safe
  `lib/workflows.ts` re-exports them for server components — client forms must
  not import runtime values from a lib that transitively imports `api-client`
  (`next/headers`) or `next build` fails
- Unit 6 note (2026-09-17): person resolution (who approves a real
  application) and workflow activation/validity checks are deliberately out of
  scope; they land in Units 21 and 7 respectively
