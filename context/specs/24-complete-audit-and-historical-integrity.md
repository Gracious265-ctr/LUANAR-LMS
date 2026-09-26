# Unit 24 — Complete Audit and Historical Integrity

> Depends on Units 11 (HR audit view — already exists), 14, 16, 17, 18, 19, 21, 22, 23.
> Also **absorbs the Unit 12 employee leave dashboard** (profile/balance/history surface) per the current team decision — see §"Absorbed Unit 12".

## Goal

Connect every significant leave operation into the authoritative audit trail,
prove that submitted applications preserve the rules/workflow context that
existed at submission (invariant 12.5), and make a complete, reconstructable
application history viewable by HR and the employee. Unit 11's HR
administrative audit view already exists; Unit 24 completes, connects, and
verifies the remaining audit surface rather than rebuilding HR's view.

## Design

### 1. Audit source of truth

`AuditEvent` (`audit/models.py`) is the single, append-only trail, written
only through `record_event` / `record_config_change` (`audit/services.py`).
Every significant operation already writes a row; Unit 24 adds the two
missing writers and **enforces** append-only at the ORM layer:

| Gap | Fix |
|---|---|
| Draft-path document removal records `object_id=None` (event written after `document.delete()` nulls the pk) | Move the `record_event` in `remove_document` ahead of the delete/retire branch (`leave/services/documents.py`) |
| HR-config edits through the Django admin write no audit | New `AuditedModelAdmin` mixin (`audit/admin.py`) on the writable config admins |

`AuditEvent` gains the same immutability guarantees `ApprovalDecision`
already has (Unit 16): custom manager + queryset that refuse `update()` /
`delete()`, plus `save()`/`delete()` guards on the model. DB-level cascade from
a parent row's delete is unaffected (FKN CASCADE calls `DELETE` in SQL, not the
ORM `delete()`), so deleting a draft application still purges its events as
today.

### 2. Subject list — every item writes an `AuditEvent`

| Subject | Action strings | Target | Source |
|---|---|---|---|
| Submission | `leave_application.submitted` | application | `leave/services/submission.py:110` |
| Workflow assignment | `leave_application.workflow_assigned` | application | `workflows/assignment.py:77` |
| Decision (approve/reject/return) | `leave_application.{approve,reject,return_for_correction}` (+ `decision_id`, `stage_order`, `reason`) | application | `workflows/approval.py:73` |
| Resubmission | `leave_application.changes_saved`, `application_resubmitted` | application | `leave/services/resubmission.py:144,301` |
| Document replace/remove/upload | `document_replaced`, `document_removed`, `document_uploaded` | document | `leave/services/documents.py` |
| Cancellation | `cancellation.withdrawn`, `.requested`, `.stage_approved`, `.approved`, `.rejected`; `balance.restored` | application | `leave/cancellations/services.py` |
| Delegation decide | `delegation.approved`, `.rejected`, `.cancelled` | delegation | `workflows/services.py:331,379,428` |
| Reassignment | `application.reassigned` | application | `workflows/services.py:524` |
| Finalisation | `balance.deducted`, `approved_document.generated` | application | `documents/finalisation.py:58,108` |
| HR-config (API) | `{prefix}.created/updated` | config row | `audit/serializers.py` (`AuditedModelSerializer`) |
| HR-config (admin) | `{app}.{model}.created/updated/deleted` | config row | **new** `AuditedModelAdmin` |

`delegation.requested` stays unrecorded by design: a delegation request is a
person-to-person handover with no application yet, and per §4 the per-
application timeline excludes delegation events entirely (HR's organization-
wide view already shows delegation decisions). Approved delegation decisions
already capture the delegate as the decision actor.

### 3. Historical integrity guarantees (tests)

After HR edits a `LeaveRule`, a `GradeEntitlement`, a `Workflow` (stages/roles),
or reassigns an approver, an already-submitted application still renders its
**submission-time** context:

- `rules_snapshot` (Unit 14) is byte-stable — config edits never rewrite it;
- `ApplicationStage` rows (Unit 16) keep their snapshot roles/labels/approvers;
- `ApprovalDecision.action` list and `current_approver` spine are unchanged;
- the generated `ApprovedLeaveDocument` and the `LeaveBalanceTransaction`
  ledger are unaffected (ledger is append-only — only new deductions land).

The admin/API recorders write audit rows only; they never touch stored
snapshots.

### 4. Per-application timeline API

`GET /api/v1/applications/<uuid:pk>/history/` returns the application's
complete, chronological trail assembled from every audit event that targets the
application **or belongs to it** (its supporting documents, revisions,
cancellation requests) — no pagination, oldest first.

Access (fail-closed 404, project convention):

- the owner (employee);
- any approver granted `get_view_access` (Unit 16) — a reached stage;
- HR.

Drafts are owner-only. Delegation events are excluded (not per-application).

`GET /api/v1/leave/my/history/` returns the signed-in employee's own trail
across all their applications, newest first, rolled up per application as
`{application, entries[]}` — the employee dashboard card source.

### 5. Timeline entry shape

Each entry mirrors the tracked-event contract extended for the HR view
(ascending order; `kind` drives the UI badge):

```
{
  "id": "…",                       # AuditEvent pk (string)
  "kind": "decision",              # submission | workflow_assignment | decision | revision |
                                   # cancellation | document | reassignment | finalisation | audit
  "action": "leave_application.approve",
  "action_label": "Approved by Philip Chipande",
  "occurred_at": "2026-09-26T08:12:00Z",
  "actor": {"id": 3, "name": "Philip Chipande"},
  "target_type": "leaveapplication",
  "state_transition": {"from": "submitted", "to": "pending"},
  "summary": "…",                  # action-specific human sentence
  "metadata": {…},                 # original metadata payload
  "stage_order": 2,                # decisions + workflow_assigned
  "resubmission_number": 2,        # changes_saved / application_resubmitted
}
```

Rendering is resolved from the audit row alone (append-only, survives target
deletes); `ApprovalDecision`/`ApplicationRevision` rows are joined only to
enrich `stage_order` / `resubmission_number` when present.

### 6. HR / employee UI consolidation

- HR application page (`hr-admin/audit/applications/[id]`) switches its
  history roll-up to the new shared timeline component (same audit data it
  already shows, one source of truth). HR-wide views (`audit-entries`,
  `finalized-leave`) stay as-is.
- Employee dashboard gains a Recent Activity card populated from
  `leave/my/history/`; the per-application page (`leave/[id]/submitted`) shows
  the full shared timeline.
- Shared `TimelineView` component renders entries with the existing
  `ACTION_LABELS` / `TARGET_TYPE_LABELS` maps extended for the new kinds.

### Absorbed Unit 12 — employee leave dashboard

An employee-facing dashboard/history surface reading **real** profile + annual
balance (already served by `my/overview`, Unit 20) plus complete personal
history. Read-only; scoped to the signed-in employee. Delivered as the
dashboard history card + per-application timeline page — no new page tree.

## Implementation

### Backend

1. `audit/models.py`: `ImmutableAuditQuerySet` + `AuditEventManager` +
   `save()`/`delete()` guards (`RuntimeError`, mirroring
   `LeaveBalanceTransaction`/`ApprovalDecision`).
2. `leave/services/documents.py`: move the `remove_document` audit write ahead
   of the draft delete.
3. `audit/admin.py`: `AuditedModelAdmin` mixin — `save_model`,
   `delete_model`, `save_formset` (inlines) record `record_config_change`
   with actor `request.user`; FK fields snapshotted to pk; a small
   per-model `audit_ignore_fields` set (e.g. FKs already covered). Apply to:
   `workflows/admin.py::WorkflowAdmin`, `leave/admin.py`::{LeaveRuleAdmin,
   GradeEntitlementAdmin, LeaveTypeAdmin, FinancialYearAdmin,
   PublicHolidayAdmin}, and `documents/admin.py` LeaveDocumentTemplateAdmin
   (config registry; document uploads themselves are already audited).
4. `audit/services.py::application_timeline(application)` — query all
   related-target `AuditEvent` rows, join enrichment, sort ascending, render
   per §5. Kind map is the single source for `kind`/`action_label`/`summary`.
5. `audit/serializers.py::TimelineEventSerializer` + `ApplicationHistorySerializer`;
   `leave/views/history.py` with `ApplicationHistoryView` and
   `MyLeaveHistoryView`; URLs under `applications/<uuid:pk>/history/` and
   `leave/my/history/` (`leave/urls.py`).

### Frontend

1. `lib/leave-history.ts`: types + server-side fetch client mirroring
   `lib/audit.ts` (cookie access token via `apiClient`).
2. Proxy routes `app/api/applications/[id]/history/` and
   `app/api/leave/my/history/` using the existing `proxyRequest` pattern.
3. Shared `components/leave/timeline-view.tsx` (server component) used by:
   employee `leave/[id]/submitted` page, HR `hr-admin/audit/applications/[id]`
   page, and the dashboard Recent Activity card.
4. `dashboard/page.tsx` datafetch for the card; extend `lib/audit.ts`
   `ACTION_LABELS`/`TARGET_TYPE_LABELS` for the new kinds.
5. Vitest tests for `lib/leave-history.ts` and timeline rendering fixtures.

## Tests

Backend (`leave`, `audit`, `workflows` apps; `TEST_DB_NAME=test_luanar_leave_unit24`):

1. **Immutability** — `AuditEvent` refuses `update()`, `delete()`, and second
   `save()`; queryset `update`/`delete` raise.
2. **Draft-document regression** — remove a draft document and assert the
   `document_removed` event keeps a non-null, correct `object_id` and
   `file_name`, and survives the row delete.
3. **Admin recorder** — create/update a LeaveRule, a Workflow (+ inline
   stages), and a GradeEntitlement through ModelAdmin save (RequestFactory);
   audience events exist with actor = admin user and correct before/after
   diffs; no exception when `request.user` is anonymous-less (superuser).
4. **Subject matrix** — one end-to-end flow (submit → assign → approve →
   finalise) plus cancellations/reassignments asserts an event per action in
   the §2 matrix.
5. **Timeline API** — shape (fields, ordering, no pagination), access
   (owner/approver/HR 200, stranger 404, draft owner-only), documents +
   cancellations + revisions appear; delegation events do not.
6. **Historical integrity** — freeze a submitted application; mutate a
   LeaveRule, GradeEntitlement, Workflow stage, reassign approver; assert
   `rules_snapshot`, `ApplicationStage`, `ApprovalDecision`, document, and
   ledger are byte-stable; timeline unchanged apart from the new audit rows.

Frontend: `lib/leave-history` mapping tests, TimelineView renders entries by
kind, dashboard card fallback (empty state).

## Dependencies

- No new packages. Reuses `AuditEvent`/`record_event`,
  `ApprovalDecision`/`ApplicationStage`, `my/overview`, `apiClient`,
  `proxyRequest`, and the Unit 11 HR view.

## Verification checklist

- `manage.py check` and `makemigrations --check --dry-run` clean (no schema
  change is expected — immutability is ORM-level, not a DB constraint).
- Backend full suite green under `.test` settings; frontend `npm test`,
  `tsc`, `eslint`, `build` green.
- Every subject in §2 writes an `AuditEvent` row (tests assert per action).
- Historical-integrity tests green; HR + employee share one timeline UI.