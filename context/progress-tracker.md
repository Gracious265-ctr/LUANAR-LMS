# Progress Tracker

Update this file after every meaningful implementation change.

## Current Phase

- Unit 23 — Final Approval, Balance, and Document Generation (SPEC DRAFTED, awaiting developer approval; the spec was revised during the Phase-1 review on 2026-09-25)
- Unit 22 — Email Notifications (DEFERRED; build-plan block retained, not spec'd)
- Unit 21 — Workflow-to-Approver Integration (COMPLETE — implemented but UNCOMMITTED on `feature/hr-track`)
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
  and resubmission is a real routing step. Implementation is present on
  `feature/hr-track` but is **working-tree only (not yet committed)**.
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
- **Reconciliation.** The Unit 13 drafts list renders draft rows only (no
  submitted rows exist), so the in-app entry point to the tracker is the
  submission-confirmation link, not the drafts list.

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

- **Unit 22 — Email Notifications (deferred).** Skipped per developer direction on
  2026-09-24; the build-plan block (§7, lines 724–766) is retained and not yet
  granular-spec'd. Implemented at a later time — **not** part of the current unit
  pass. The Unit 22 spec + detailed design remain to be written when taken up.
  (Do **not** begin Unit 22 now; see the Section-3.6 thread in Unit 23's spec.)
- **Unit 23 — Final Approval, Balance, and Document Generation (spec drafted).**
  Spec `context/specs/23-final-approval-balance-and-document-spec.md` revised
  during the Phase-1 review on 2026-09-25: decisions D1–D8 rewritten against the
  actual code (deduction inside `decide()`'s transaction from `rules_snapshot`;
  no ledger row for special leave; restoration stays owned by Unit 18;
  template-populated ReportLab PDF via `approved/{application_id}/` in storage;
  owner/HR/approver read-only access; Django-Q2 render task; no new tracking
  event). Corrections folded in: no fixture balance/document provider is
  deleted (`LedgerBalanceProvider` is already ledger-backed; `leave/providers/
  fixture*.py` stays), and the wrong "HR Unit 12" / "HR Units 8–9" references
  are gone. **DOCX is deferred (PDF only, no `python-docx`).** Awaiting
  developer approval; on completion mark complete + set Next Up = Unit 24.

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
- **Status:** implemented and uncommitted on `feature/hr-track` (Unit 21 predates
  this tracker entry). Commit/merge decision is the developer's.

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

- **Unit 21 verified complete + Unit 23 spec revised (2026-09-25):** A Phase-1
  review confirmed Unit 21 is fully implemented on `feature/hr-track` but
  **not committed** (working-tree only — `git status` shows the provider swaps,
  `resubmit.py`, `tests_routing.py`, the tracking-fixture deletions, and
  `docs/workflow-to-approver-routing.md` as modified/untracked/deleted; 32
  routing/tracking/resubmit tests pass). The Unit 23 spec draft was rewritten:
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
  treats a blank grade or missing `appointment_date` as "no employee" (matches
  the precondition `EMPLOYEE_PROFILE_MISSING`), and `department_id` stays
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