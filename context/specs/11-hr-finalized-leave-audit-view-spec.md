# Unit 11 — HR Finalized Leave and Audit View

## Goal

<<<<<<< HEAD
Give HR their administrative history / audit interface (build-plan §4, Unit 11):

- Organization-wide visibility of finalized (submitted) leave applications, with
  per-application history (documents, reassignments, and the audit timeline).
- Administrative history: who changed which configuration record when, with the
  changed values and any relevant reason.

## Why this port differs from the original Unit 11

This unit follows the **port plan**: the version on `feature/hr-track` built its
own proprietary `AuditEntry` model + `record_audit()` service. `development`
instead already owns a complete append-only audit trail — `audit.AuditEvent`
written by `audit.services.record_event`, populated since Unit 14 by submission,
approval decisions, corrections, resubmissions, cancellations, and the document
lifecycle. So this port **does not create a second audit model**.

- `development` already has everything hr-track's `AuditEntry` was invented for,
  under different names: `actor` (FK), `action` (dotted code), generic
  `content_type`/`object_id` (the polymorphic target), `prev_state`/`new_state`,
  JSON `metadata`, `created_at`, and default `Meta.ordering`.
- The one structural gap was `object_id` being a `UUIDField` while HR
  configuration targets (employees, entitlements, leave types, workflows, …)
  use integer primary keys. `audit/migrations/0002` widens `object_id` to
  `CharField(max_length=100)` + index `audit_target_idx` on
  `(content_type, object_id)`.

## Assumptions made (flag if wrong)

- **Port only the user-facing result; keep `AuditEvent` as the single writer.**
  We do not replay hr-track's `AuditEntry`/`record_audit`/`AuditEntryAdmin`.
  `record_event` remains the one append-only writer; the HR view reads it.
- **`record_config_change` is the canonical Unit-11 wrapper.** It packages the
  human `summary`, optional `reason`, and a minimal before/after diff into the
  event's `metadata` so every HR-configuration action renders one shape. Raw in-
  trail events (e.g. `leave_application.submitted` from Unit 14) render fine
  with empty detail.
- **Dotted action codes.** `employee.created`, `grade_entitlement.updated`,
  `delegation.approved`, `application.reassigned`, `document_template.updated`,
  `workflow.created`, … The pre-existing trail vocabulary
  (`leave_application.submitted`, `leave_application.approved`,
  `document_uploaded`, `cancellation.*`, `balance.restored`, …) is unchanged —
  the frontend labels them in `lib/audit.ts`.
- **No double-auditing.** Code that already writes `AuditEvent` (submission,
  approval/rejection decisions, documents, cancellation, balance) is **not**
  re-wired. Only the Unit 11 HR mutation surfaces get audit hooks, and each
  writes exactly once inside the owning serializer/service transaction.
- **Audit scope is the API/service layer.** Django admin stays a development
  inspector; the API is the authoritative mutation path.
- **HR read is `submitted`-only.** HR lists/opens submitted (finalized)
  applications organization-wide. Drafts are private and hidden (404 on
  retrieve). Read-only — HR never becomes an approval stage and never edits
  applications or balances (project-overview + invariants 12.1/12.2).
- **The endpoints live in the `audit` app** (which already imports
  `leave.models.LeaveApplication`? — no: it imports nothing app-specific; the
  vertical slice reads `LeaveApplication` the way `workflows` already does).
=======
Create the HR administrative history/audit interface (build-plan §4, Unit 11):

- Organization-wide visibility of finalized leave applications.
- Application history (what happened to an application, in order).
- Administrative history: who changed which configuration record when, with the
  changed values and any relevant reason.

Normal HR visibility focuses on finalized records and administrative
intervention rather than making HR a normal approval stage (project-overview:
"HR: Organization-wide access to finalized applications").

This unit also plants the `audit`-app foundation that Unit 24 ("Complete Audit
and Historical Integrity") completes once the Employee + Approver track delivers
approvals/rejections/corrections/cancellations.

## Assumptions made (flag if wrong)

- **Scope boundary — audit only what truthfully exists today.** The build-plan
  Unit 11 lists approved/rejected applications, approval decisions, rejection
  reasons, correction history, resubmissions, cancellations, and document
  replacement history. **None of those action types exist yet** — the Employee +
  Approver track has not delivered Units 16–19 (approval decisions, rejection/
  correction/resubmission, cancellation, document lifecycle), and the build
  plan's just-in-time rule says "Do not build the final audit aggregation before
  the underlying actions exist." The `LeaveApplication` status set is still just
  `draft`/`submitted`. So Unit 11 audits the actions that **do** exist today and
  builds the reusable audit spine; approval/rejection/cancellation/decision
  events become audit entries (or their own records, per Unit 24) when those
  units land, flowing into this same interface. Deferred items are documented
  as a boundary, not silently invented.

- **The `audit` app becomes the authoritative reusable audit log.** A single
  generic `AuditEntry` model (`actor`, `action`, `target_type`, `target_id`,
  `target_summary`, `detail` JSON (a before/after diff for configuration and
  state changes; a flat payload for some actions), `reason`,
  `created_at`) plus a `record_audit(...)` service. Reusing one audit log avoids
  duplicating an audit implementation per domain (code-standards: no duplicate
  implementations, one authoritative business rule). This is the foundation
  Unit 24 extends.

- **Explicit `record_audit` calls from serializers/services — not Django
  signals.** Signals fire implicitly on every ORM save (including unrelated
  paths) and are fragile to reason about; explicit calls from serializer
  `create`/`update` overrides and the delegation/reassignment services keep the
  audit trail tied to the same code that owns each action and are easy to test.
  Audit rows are written inside the same `transaction.atomic()` as the action so
  a failed action never leaves a phantom audit entry (code-standards: failed
  operations must not leave partially updated state).

- **Application submission is audited** (the only application-lifecycle event
  today, alongside reassignment). `submitted_at`/reference creation is the
  start of an application's history spine and makes "Application history" real
  in the HR view. Draft creation/edits and document uploads are **not** audited
  (noise; document replacement history is Unit 19). Reassignment already has its
  own `Reassignment` history model — it is **also** recorded as an audit entry so
  the HR audit log (and the application detail trail) has one consistent view;
  the `Reassignment` row remains the authoritative record (no deletion).

- **Audit scope is the API/service layer.** The Django admin remains a
  development inspector (previous units already made most admins view-only);
  the API is the authoritative mutation path. Admin-driven changes are not
  audited in this unit — documented boundary; Unit 24 can revisit if admin
  becomes a production entry point.

- **HR gets an organization-wide finalized-leave read.** HR can list and open
  any `submitted` application (reference-numbered = the finalized-equivalent
  records that exist today). Drafts are private employee working state and are
  never shown to HR. This is read-only — HR still never becomes an approval
  stage and never edits balances or applications (project-overview + invariant
  12.1/12.2).

- **The finalized-leave and audit endpoints live in the `audit` app.** The app
  imports `leave.models.LeaveApplication` the same way `workflows` already does
  (established cross-app pattern). This keeps the whole Unit 11 vertical slice
  (audit log + finalized-leave read + per-application history) in one domain
  boundary instead of splitting one feature across two apps.

- **Simplicity over taxonomy in the HR interface.** One "Audit" page under HR
  Administration with two sections — "Finalized leave" (submitted applications
  table) and "Administrative history" (audit-entries table with filters) — plus
  a per-application detail page showing the application, its documents, its
  reassignment history, and its audit trail. Filters (`action`, `target_type`)
  are server-side query params, matching the existing `DelegationViewSet`
  `state=`/`approver=` filter pattern.

- **No notifications, no seeding, no backup/changes to existing API
  contracts.** Existing endpoints are untouched; this unit only adds new
  endpoints and audited service calls. Audit entries append-only — no update/
  delete endpoints, no delete permission in admin.
>>>>>>> feature/plans-teams

## Visible result

An HR "Audit" page under `/dashboard/hr-admin/audit`:

- **Finalized leave**: every submitted leave application organization-wide
  (reference, employee, leave type, dates, days, submitted at, current
<<<<<<< HEAD
  approver). Each row opens `/dashboard/hr-admin/audit/applications/{id}`
  showing the application summary, supporting documents, reassignment history,
  and the application's audit timeline.
- **Administrative history**: a chronological audit log of HR configuration and
  administrative actions (actor, action pill, target + summary, before/after
  values, reason, timestamp), filterable server-side by `action` and
  `target_type`. The sidebar gains an "Audit" item (lucide `History`); the HR
  index gains an Audit card.

## Dependencies

- Units 14–19 trail already in `AuditEvent` via `record_event` (submission,
  decisions, corrections, resubmissions, cancellations, document lifecycle,
  balance).
- Unit 2 `EmployeeProfile`/`EmployeeViewSet`/`IsHRRole` — employee changes
  audited; names in HR tables.
- Units 3–5 `GradeEntitlement`/`LeaveType`/`LeaveRule`/`FinancialYear`/
  `PublicHoliday` — configuration changes audited.
- Units 6–7 `WorkflowSerializer` — audited.
- Unit 8 delegation services — decisions audited.
- Unit 9 `reassign_application` — audited.
- Unit 10 `LeaveDocumentTemplateView.patch` — audited.
- Unit 13 `LeaveApplication` (submitted status, reference, documents,
  `submitted_at`) — the finalized-leave listing.
- Unit 20 `PendingApplicationSerializer` shape — reused for the HR listing.
=======
  approver), each opening a detail page with the application summary, supporting
  documents, reassignment history, and the application's audit trail.
- **Administrative history**: a chronological audit log of HR configuration and
  administrative actions (actor, action, target, before/after values, reason,
  timestamp), filterable by action and target type.

## Dependencies

- Unit 2 (`EmployeeProfile`, `EmployeeViewSet`, `IsHRRole`) — employee changes
  audited; employee names for HR tables.
- Unit 3 (`GradeEntitlement`), Unit 4 (`LeaveType`/`LeaveRule`), Unit 5
  (`FinancialYear`/`PublicHoliday`) — configuration changes audited.
- Units 6–7 (`Workflow` create/update incl. activation) — audited.
- Unit 8 (`Delegation` + `approve_delegation`/`reject_delegation`/
  `cancel_delegation`) — decisions audited inside the services.
- Unit 9 (`Reassignment` + `reassign_application`) — audited inside the service;
  `Reassignment` rows surfaced on the application detail view.
- Unit 10 (`LeaveDocumentTemplate` singleton PATCH) — audited.
- Unit 13 (`LeaveApplication` rows incl. `submitted` status, reference numbers,
  documents, `submitted_at`) — the finalized-leave listings and the submitted
  event audit depend on these.
>>>>>>> feature/plans-teams

## API contract

Namespace additions. Authentication required; every endpoint HR-only
<<<<<<< HEAD
(`[IsAuthenticated, IsHRRole]`), read-only
(`http_method_names = ["get", "head", "options"]`).

### `GET /api/v1/audit-entries/`

HR audit-log listing, paginated, newest first. Query filters: `action=` (exact
dotted code, e.g. `employee.updated`), `target_type=` (content-type model
lowercase, e.g. `employeeprofile`, `leavedocumenttemplate`,
`leaveapplication`), `target_id=`, `actor=` (user pk). Response shape:
=======
(`IsHRRole`). Both are read-only resources (no create/update/delete for audit —
entries are append-only).

### `GET /api/v1/audit-entries/`

HR audit-log listing, paginated, newest first. Query filters: `action=`,
`target_type=`, `target_id=`, `actor=` (user pk). Response object shape
(snake_case):
>>>>>>> feature/plans-teams

```json
{
  "id": 1,
  "actor": 1,
  "actor_name": "Aisha HR",
<<<<<<< HEAD
  "action": "grade_entitlement.updated",
  "target_type": "gradeentitlement",
  "target_id": "3",
  "target_summary": "Entitlement 3",
  "detail": { "before": { "days": 20 }, "after": { "days": 21 } },
  "reason": "",
  "prev_state": "",
  "new_state": "",
=======
  "action": "update",
  "target_type": "entitlement",
  "target_id": "3",
  "target_summary": "Annual leave: A–C, 21 days (from 2026-01-01)",
  "detail": { "before": { "days": 20 }, "after": { "days": 21 } },
  "reason": "",
>>>>>>> feature/plans-teams
  "created_at": "2026-09-18T13:00:00Z"
}
```

`GET /api/v1/audit-entries/{id}/` retrieves one entry.

### `GET /api/v1/finalized-leave/`

HR organization-wide list of `submitted` leave applications, paginated, newest
<<<<<<< HEAD
`submitted_at` first. Search `?employee=` (name/email icontains). Reuses
`PendingApplicationSerializer`. List shape:
=======
`submitted_at` first. Search `?employee=` (name/email icontains) reuses the
employee search convention. List object shape:
>>>>>>> feature/plans-teams

```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "reference_number": "LUANAR-2026-00001",
  "employee": 3,
  "employee_name": "Jane Dean",
  "leave_type_name": "Annual",
  "start_date": "2026-10-01",
  "end_date": "2026-10-05",
  "calculated_days": 5,
  "reason": "Family visit",
  "submitted_at": "2026-09-18T10:00:00Z",
  "current_approver": null,
  "current_approver_name": ""
}
```

### `GET /api/v1/finalized-leave/{id}/`

<<<<<<< HEAD
One submitted application with its history roll-up: the fields above plus
`documents` (`SupportingDocumentSerializer`), `reassignments`
(`ReassignmentSerializer`), and `audit_entries` (application events, oldest
first) via `events_for_target`.

Validation: **401** unauthenticated; **403** any non-HR role; a non-SUBMITTED
id on retrieve → **404** (drafts hidden). No write methods anywhere.

## Implementation

### 1. Model + migration (`audit/models.py`)

- Widen `AuditEvent.object_id` from `UUIDField` to `CharField(max_length=100)`
  (mixed int/UUID targets); add index `audit_target_idx` on
  `("content_type", "object_id")`. Migration `audit/0002`.

### 2. Service (`audit/services.py`)

- `record_event` / `_jsonable` / `target_summary` / `changed_fields` (all
  existing) remain the spine.
- Add `record_config_change(*, actor, action, target, summary="", before=None,
  after=None, reason="", prev_state="", new_state="")` — writes one `AuditEvent`
  with `metadata = {"summary", "reason", "before", "after"}` (empty pieces
  omitted; `before`/`after` reduced via `changed_fields`).
- Add `current_actor(serializer)` and `events_for_target(instance)` (target's
  events, oldest first).

### 3. Serializers (`audit/serializers.py`, new)

- `AuditEventSerializer` (ModelSerializer, read-only): `actor`, `actor_name`,
  `action`, `target_type` (`content_type.model`), `target_id` (`object_id`),
  `target_summary` (`metadata.summary` or `target_summary(content_object)`),
  `detail` (`{before, after}` from metadata), `reason` (metadata), `prev_state`,
  `new_state`, `created_at`.
- `AuditedModelSerializer` (ModelSerializer base): subclasses declare
  `audit_prefix` + `audit_fields`; default `create`/`update` record
  `{prefix}.created` / `{prefix}.updated` inside the existing
  `transaction.atomic()`. Serializers that override create/update for their own
  transaction boundaries call `_audit_after_create` / `_audit_after_update`
  explicitly (or bypass the base audit with
  `super(AuditedModelSerializer, self)` when their ordering demands it).
- `HRLeaveApplicationListSerializer` / `HRLeaveApplicationSerializer` — read-
  only views over `PendingApplicationSerializer` + documents + reassignments +
  `audit_entries`.

### 4. Views + urls (`audit/views.py`, `audit/urls.py`, `config/urls.py`)

- `AuditEventViewSet` (List/Retrieve): filters in `get_queryset` (`action`
  exact, `content_type__model=`, `object_id`, `actor_id`),
  `select_related("actor", "content_type")`.
- `FinalizedLeaveViewSet` (List/Retrieve): `status=SUBMITTED`,
  `?employee=` icontains, `order_by("-submitted_at")`; retrieve 404s on any
  non-SUBMITTED application.
- `audit/urls.py`: `SimpleRouter` basenames `audit-entry`, `finalized-leave`;
  `config/urls.py` mounts `path("api/v1/", include("audit.urls"))`.

### 5. Audit hooks into existing HR mutations (write exactly once, in-transaction)

- `users/serializers.py` `EmployeeSerializer` → `employee.created`/`.updated`
  (`audit_fields`: designation, department, category, grade, appointment_date,
  is_active; summary = "Jane Grey (Chemistry)"); user `__str__` snapshot for the
  `after` diff.
- `leave/serializers/__init__.py`: `GradeEntitlementSerializer`,
  `LeaveTypeSerializer`, `LeaveRuleSerializer`, `PublicHolidaySerializer`
  (default base behavior); `FinancialYearSerializer` (custom create/update —
  calls `_audit_after_create`/`_audit_after_update` itself after
  `_settle_active_flag`).
- `workflows/serializers.py` `WorkflowSerializer` — `workflow.created`/
  `.updated`; snapshot includes `state`, `scopes`, and the ordered stage role
  list; update audits **after** `_replace_stages` (bypasses the base auto-audit
  via `super(AuditedModelSerializer, self).update(...)`).
- `workflows/services.py` `approve_delegation`/`reject_delegation`/
  `cancel_delegation` — `delegation.approved/rejected/cancelled` with
  prev/new state and the HR decision reason in metadata.
- `workflows/services.py` `reassign_application` — `application.reassigned`
  with to/from approvers in the diff.
- `documents/views.py` `LeaveDocumentTemplateView.patch` —
  `document_template.updated` (changed fields only).

### 6. Frontend

- `lib/audit.ts` (server-safe, via `apiClient`): types `AuditEntry`,
  `FinalizedApplication`, `SupportingDocument`, `ApplicationDetail`,
  `AuditEntryListResponse`, `FinalizedListResponse`; `ACTION_LABELS` (dotted
  codes → friendly labels), `TARGET_TYPE_LABELS` (content-type model names →
  friendly labels); `listAuditEntries({action?, targetType?})`, `getAuditEntry`,
  `listFinalizedApplications({employee?})`, `getFinalizedApplication`.
- `components/hr/`: `audit-meta.tsx` (tone + `AuditActionPill` +
  `auditChangesText` + `auditEditHref` routing to existing HR edit pages),
  `edit-action-link.tsx`, `audit-entries-table.tsx`, `finalized-leave-table.tsx`,
  `application-history-view.tsx`.
- Pages `app/(dashboard)/dashboard/hr-admin/audit/page.tsx` (two panels +
  action/target-type filter form bound to query params) and
  `audit/applications/[id]/page.tsx` (async params, 404 on miss). Auth guards
  identical to existing HR pages.
- Sidebar "Audit" item (`History`) in the HR section + HR index card; no
  client-side mutating lib or route-handler proxy (read-only → `apiClient`
  directly, like `lib/reassignments.ts`).

### 7. Tests

- `backend/audit/tests.py` (26 tests): read-only permissions (401/403),
  audit-entries listing + all filters + retrieve (int and UUID targets),
  finalized-leave list (SUBMITTED-only, `-submitted_at`, `?employee=` search),
  retrieve roll-up (documents + reassignments + audit entries, oldest first,
  id is the UUID), 404 for drafts; wiring for employee/entitlement/leave-type/
  leave-rule/financial-year/holiday/workflow create+update, delegation
  approve/reject/cancel, reassign, template PATCH — each producing exactly one
  event with correct before/after/reason; failed delegation writes no event;
  `AuditEventAdmin` read-only (`has_add_permission`/`has_delete_permission`
  False).
- Frontend: `audit-entries-table.test.tsx`, `finalized-leave-table.test.tsx`,
  `application-history-view.test.tsx` (rows, link hrefs, pill fallback, empty
  states).

### 8. Docs

- `context/specs/11-hr-finalized-leave-audit-view-spec.md` (this file).
- `context/progress-tracker.md`: Unit 11 complete with the port decisions.
- `README.md` API table: audited `/api/v1/audit-entries/` and
=======
One submitted application with its history roll-up:

- the application fields above,
- `documents` (existing `SupportingDocumentSerializer` shape),
- `reassignments` (array of the existing `ReassignmentSerializer` shape, newest
  first),
- `audit_entries` (array of audit-entry objects for
  `target_type == "application"` and this target id, oldest first — the
  application timeline).

Validation summary:

- **401** unauthenticated; **403** any non-HR role anywhere.
- `submitted`-only: a draft application id on the retrieve endpoint → 404
  (permission-style hiding; integrity: drafts are never exposed to HR).
- Read-only: no POST/PATCH/DELETE on either resource.

## Implementation

Work in the following order; verify each backend step before frontend work begins.

### 1. Model changes (`audit/models.py`)

- `AuditEntry` model:
  - `actor` FK `settings.AUTH_USER_MODEL` (`on_delete=CASCADE` matches the
    project's convention; there is no user-deletion feature), related_name
    `audit_entries`.
  - `action` CharField, `TextChoices`: `created`, `updated`, `approved`,
    `rejected`, `cancelled`, `reassigned`, `submitted`.
  - `target_type` CharField (string codes: `employee`, `entitlement`,
    `leavetype`, `leaverule`, `financialyear`, `publicholiday`, `workflow`,
    `delegation`, `reassignment`, `document-template`, `application`).
  - `target_id` CharField (the polymorphic id — digits for int pks, uuid text
    for `LeaveApplication`).
  - `target_summary` CharField (human-readable target description).
  - `detail` JSONField (`null=True, blank=True`) — **free-form**, not always a
    diff. Configuration and state changes use `{"before": {...}, "after":
    {...}}` limited to the changed fields, with `"before": null` on creates; other
    actions store a flat payload instead (`document_generated` records the file,
    `stage_skipped` records the stages the self-approval check bypassed). Readers
    must not assume the diff shape — see "Superseded" below.
  - `reason` TextField (`blank=True, default=""`).
  - `created_at` DateTimeField (`auto_now_add`).
  - `Meta.ordering = ["-created_at"]` + index on `("target_type",
    "target_id")` for the application-timeline lookup.
- Migration `audit/0001_initial` via `makemigrations audit`.

### 2. Service (`audit/services.py`)

- `record_audit(*, actor, action, target_type, target_id, target_summary,
  detail=None, reason="") -> AuditEntry` — trimmed/normalized values, stores the
  entry. Thin, single-responsibility; callers build `detail`
  (`{"before": ..., "after": ...}`) and `target_summary`.
- A small `changed_fields(instance_before: dict, instance_after) -> dict`
  helper neighbors the service so serializers build lean `before`/`after`.
  Helper lives here so multiple serializers reuse one implementation.

### 3. Wire audit calls into existing mutations

Within the owning serializer/service, wrap the save and the `record_audit` call
in the existing transaction (create/update serializers already run inside
`transaction.atomic()` where relevant):

- `users/serializers.py` `EmployeeSerializer`: override `create`/`update`,
  record `employee` created/updated with changed fields (designation,
  department, category, grade, appointment_date, active...).
- `leave/serializers.py`: `GradeEntitlementSerializer`,
  `LeaveTypeSerializer`, `LeaveRuleSerializer`, `FinancialYearSerializer`,
  `PublicHolidaySerializer` — `created`/`updated` per type.
- `workflows/serializers.py` `WorkflowSerializer`: `created`/`updated` after the
  existing `transaction.atomic()` stage replacement; `target_summary` carries
  the workflow name and scope; include `state`/`effective_from`/stage-role
  changes in `detail` when present.
- `workflows/services.py` `approve_delegation` / `reject_delegation` /
  `cancel_delegation`: inside the existing `transaction.atomic()`, record
  `delegation` action with `reason` = the HR decision reason and changed fields
  in `detail`.
- `workflows/services.py` `reassign_application`: inside its existing
  `transaction.atomic()`, record `reassignment` action with `reason` and
  `from_approver` → `to_approver` in `detail`.
- `documents/views.py` `LeaveDocumentTemplateView.patch`: record
  `document-template` updated (changed fields only; values are labels/wording,
  never approved data).
- `leave/views.py` `LeaveApplicationViewSet.submit`: after the successful
  atomic submit, record `application` `submitted` with the reference number in
  `target_summary`.

### 4. Serializers + views (`audit/serializers.py`, `audit/views.py`, `audit/urls.py`)

- `AuditEntrySerializer` (ModelSerializer, read-only): exposes `id`, `actor`
  (pk), `actor_name` (method), `action`, `target_type`, `target_id`,
  `target_summary`, `detail`, `reason`, `created_at`.
- `HRLeaveApplicationSerializer` (Serializer, read-only) reusing the
  `PendingApplicationSerializer` shape + `documents` (nested
  `SupportingDocumentSerializer`) + `reassignments` (nested
  `ReassignmentSerializer`, reused from `workflows.serializers`) +
  `audit_entries` (nested `AuditEntrySerializer`, oldest first). `leave_type_name`
  resolution identical to `PendingApplicationSerializer`.
- `AuditEntryViewSet` (List/Retrieve, `permission_classes=[IsAuthenticated,
  IsHRRole]`, `http_method_names=["get", "head", "options"]`): filters via
  `get_queryset` (`action`, `target_type`, `target_id`, `actor`), select_related
  `actor`.
- `FinalizedLeaveViewSet` (List/Retrieve): list = `submitted` applications with
  `select_related("employee", "current_approver")`, ordered `-submitted_at`,
  `?employee=` search; retrieve enforces `status == SUBMITTED` else 404
  (drafts hidden); serializer context renders the history roll-up.
- `audit/urls.py` registers both with a `SimpleRouter` (basenames `audit-entry`,
  `finalized-leave`); add `path("api/v1/", include("audit.urls"))` to
  `config/urls.py`.

### 5. Admin (`audit/admin.py`)

- `AuditEntryAdmin` view-only inspector: `list_display` actor, action,
  target_type/target_id, target_summary, created_at; `list_filter` action/
  target_type; `raw_id_fields` actor; read-only everything, no delete — matches
  the `DelegationAdmin`/`ReassignmentAdmin` pattern.

### 6. Seed

- No seeding. Existing `seed_dev_users` unchanged; demos come from HR actions
  and submitted applications created through the leave UI or tests.

### 7. Frontend

- `lib/audit.ts` (server-safe): `AuditEntry`, `FinalizedApplication`,
  `ApplicationDetail`, `AuditEntryListResponse`, `FinalizedListResponse`,
  `listAuditEntries({action?, targetType?})`, `getAuditEntry(id)`,
  `listFinalizedApplications({employee?})`, `getFinalizedApplication(id)` —
  reading via `apiClient`.
- Components under `components/hr/`:
  - `audit-entries-table.tsx` — entries: actor, action pill, target +
    summary, changed fields detail (or reason), timestamp, empty/filter UI.
  - `finalized-leave-table.tsx` — submitted applications: reference (link),
    employee, leave type, dates/days, submitted at, current approver, empty
    state.
  - `application-history-view.tsx` — the application detail: summary card,
    documents list, reassignment history, and the audit timeline.
- Pages:
  - `app/(dashboard)/dashboard/hr-admin/audit/page.tsx` — header + two panels
    ("Finalized leave" table; "Administrative history" with action/target-type
    filters bound to the API query params), each with loading/empty/error
    states. Auth guard identical to existing HR pages.
  - `app/(dashboard)/dashboard/hr-admin/audit/applications/[id]/page.tsx` —
    loads one finalized application via `getFinalizedApplication(id)` and
    renders `ApplicationHistoryView`. Loading/error/404 states.
- Since both resources are read-only, no client-side mutating lib and no route-
  handler proxy are required (reads go through `apiClient`, as
  `lib/reassignments.ts` already does; the proxy pattern exists for writes).
- Sidebar: add an "Audit" item (lucide `History`) under the HR section; add an
  HR index card; update the HR index footer note to reflect the new unit.

### 8. Tests

- `backend/audit/tests.py`:
  - Model: `AuditEntry.__str__`/`created_at`; ordering newest-first.
  - Service: `record_audit` persists actor/action/target/detail/reason;
    `changed_fields` drops unchanged fields.
  - API: 401 unauthenticated; employee/approver → 403 on both resources;
    audit-entries listing + filters (`action`, `target_type`, `target_id`,
    `actor`) + retrieve; finalized-leave lists only `submitted`, ordered,
    `?employee=` search; retrieve on a submitted app returns the roll-up
    (documents + reassignments + audit entries) and 404 for a draft id.
  - Audit wiring: entitlement/leave-type/leave-rule/financial-year/holiday
    create+update, workflow create+update, employee create+update, delegation
    approve/reject/cancel, reassign, template PATCH, and application submit each
    produce the expected audit entry (target_type, action, before/after
    detail); a failed delegation action writes no audit entry.
  - Admin renders; `has_delete_permission` False.
- Frontend: `audit-entries-table.test.tsx`, `finalized-leave-table.test.tsx`,
  `application-history-view.test.tsx` (renders entries/list/detail, filter
  selection, empty states).

### 9. Docs

- `context/specs/11-hr-finalized-leave-audit-view-spec.md` (this file).
- `context/progress-tracker.md`: Unit 11 complete; record the big decisions
  (audit app foundation + `record_audit` service, explicit serializer/service
  wiring, deferred approval/rejection/cancellation history is a Units 16–19/24
  boundary, HR org-wide finalized-leave read in the `audit` app, no admin
  mutation auditing, no notifications/seeding).
- Root `README.md` API table: add the `/api/v1/audit-entries/` and
>>>>>>> feature/plans-teams
  `/api/v1/finalized-leave/` rows.

## Verification

<<<<<<< HEAD
- `DJANGO_SETTINGS_MODULE=config.settings.test TEST_DB_NAME=test_luanar_leave_11
  uv run manage.py test audit leave workflows users documents --keepdb` green
  (669 tests).
- `npm test` green (286), `tsc --noEmit`, `npm run lint`, `npm run build` green.
- Manual smoke: HR updates a leave rule and approves a delegation, an employee
  submits an application; open `/dashboard/hr-admin/audit` — Finalized leave
  lists the submitted app, its detail shows documents + reassignment history +
  trail, and Administrative history lists the rule update / delegation decision
  / submission with before/after values; employee and approver roles get 403.

## Implementation notes

- No second audit model: `AuditEvent` + `record_event` stay the single
  writer; the Unit-11 HR surface adds `record_config_change` and read views.
- Reassignment remains doubly recorded (its own `Reassignment` row + an audit
  entry) so the HR timeline is one consistent view; the dedicated model stays
  authoritative.
- Admin mutations remain outside the audited API path (boundary documented in
  the tracker).
=======
- `uv run manage.py test --noinput` green (existing 299 + new audit tests).
- `npm test` green, `npm run lint` and `npm run build` green.
- Manual smoke via `npm run dev` + seeded backend: HR updates a leave rule and
  approves a delegation, submits a leave application (or seeds one), then opens
  `/dashboard/hr-admin/audit` — Finalized leave lists the submitted app, its
  detail shows documents + reassignment history + audit trail, and
  Administrative history lists the rule update/delegation decision/submission
  entries with before/after values; an employee and an approver get 403s.

## Implementation notes

- This unit deliberately stops before approval/rejection/cancellation history:
  those action types do not exist until the Employee + Approver track delivers
  Units 16–18, and the build plan forbids building audit aggregation for
  actions that don't exist yet. The `detail` before/after JSON and the
  polymorphic `target_type`/`target_id` are the spine Unit 24 and future
  decision records attach to.
- Reassignment remains doubly recorded (its own `Reassignment` row + an audit
  entry) so the HR timeline is one consistent view; the dedicated model stays
  authoritative.
- Admin mutations are outside the audited path in this unit (the API is the
  authoritative mutation surface); document this boundary in the tracker.

## Superseded (2026-09-26) — `detail` is not always a before/after diff

This spec, the model `help_text`, and the TypeScript `AuditEntry` type all stated
that `detail` is a `{"before": ..., "after": ...}` diff. That was true of the
configuration and state-change callers, but not of the field as a whole:
`documents/tasks.py` writes a flat payload for `document_generated`, and
`workflows/services.py` writes one for `stage_skipped`.

`auditChangesText()` believed all three sources and did
`Object.keys(entry.detail.after)` unguarded, so any audit page containing a
`document_generated` or `stage_skipped` row died with
`TypeError: Cannot convert undefined or null to object` — the whole HR audit view,
not one row. The rows had been there all along; the view was simply never opened
against a database containing them.

Fixed in three places, because the wrong contract was recorded in all three:

* `auditChangesText()` sniffs the shape — a non-null object `after` is a diff and
  renders as `field: old → new`; anything else is summarised as `key: value`. Long
  values are capped and the entry-level reason is only appended when the payload
  does not carry its own, so `stage_skipped` does not print its reason twice.
* `AuditEntry.detail` is typed `Record<string, unknown> | null`, not a fixed diff.
* The model `help_text` now says free-form, with the two counter-examples
  (`audit/migrations/0010_auditentry_detail_helptext.py`).

Covered by five cases in `frontend/tests/audit-entries-table.test.tsx`, including
the two real payload shapes, an empty `detail`, and an `after: null`.

The general lesson, recorded here because it is the second time in this codebase
that a guard designed to isolate failures hid a defect: the notification composer's
`except Exception` swallowed a `FieldError` and the mail silently never sent. A
catch-all is not a substitute for a test that asserts on the real payload.
>>>>>>> feature/plans-teams
