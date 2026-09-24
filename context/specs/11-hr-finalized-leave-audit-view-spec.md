# Unit 11 — HR Finalized Leave and Audit View

## Goal

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

## Visible result

An HR "Audit" page under `/dashboard/hr-admin/audit`:

- **Finalized leave**: every submitted leave application organization-wide
  (reference, employee, leave type, dates, days, submitted at, current
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

## API contract

Namespace additions. Authentication required; every endpoint HR-only
(`[IsAuthenticated, IsHRRole]`), read-only
(`http_method_names = ["get", "head", "options"]`).

### `GET /api/v1/audit-entries/`

HR audit-log listing, paginated, newest first. Query filters: `action=` (exact
dotted code, e.g. `employee.updated`), `target_type=` (content-type model
lowercase, e.g. `employeeprofile`, `leavedocumenttemplate`,
`leaveapplication`), `target_id=`, `actor=` (user pk). Response shape:

```json
{
  "id": 1,
  "actor": 1,
  "actor_name": "Aisha HR",
  "action": "grade_entitlement.updated",
  "target_type": "gradeentitlement",
  "target_id": "3",
  "target_summary": "Entitlement 3",
  "detail": { "before": { "days": 20 }, "after": { "days": 21 } },
  "reason": "",
  "prev_state": "",
  "new_state": "",
  "created_at": "2026-09-18T13:00:00Z"
}
```

`GET /api/v1/audit-entries/{id}/` retrieves one entry.

### `GET /api/v1/finalized-leave/`

HR organization-wide list of `submitted` leave applications, paginated, newest
`submitted_at` first. Search `?employee=` (name/email icontains). Reuses
`PendingApplicationSerializer`. List shape:

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
  `/api/v1/finalized-leave/` rows.

## Verification

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