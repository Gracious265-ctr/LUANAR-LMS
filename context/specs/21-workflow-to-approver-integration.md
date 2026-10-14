# Unit 21 — Workflow-to-Approver Integration

<<<<<<< HEAD
> Read `context/AGENTS.md` before starting. Session command:
> `DJANGO_SETTINGS_MODULE=config.settings.test TEST_DB_NAME=test_luanar_leave_21 uv run manage.py test workflows users leave --keepdb --parallel auto` (from `backend/`), plus `npm test` from `frontend/` when the tracking serializers change.
> **Parallel-session rule: Unit 21 must NOT run concurrently with Unit 20.** Use a separate worktree (`../LUANAR-LMS-unit-21`) and its own dev DB.
> This unit only specs **workflow routing + provider swap**. It does NOT touch `notifications/` (Unit 22), balance deduction or document generation (Unit 23), or audit aggregation (Unit 24).

## Goal

Replace the hard-coded development workflows with real HR-managed workflow
configuration: a submitted application is auto-routed through the `Workflow`
stages HR configured for the employee's category and department, each stage is
bound to the correct approver (honoring delegation and reassignment), stages
advance sequentially and necessarily, and the employee tracking page reflects
real workflow state instead of fixture scenarios. All changes happen through
the existing swappable provider seams — no new hard-codes in the decision
service.

## Design

### Current state (what this unit replaces)

- `config/settings/base.py`: `WORKFLOW_PROVIDER = "workflows.fixture_provider.FixtureWorkflowProvider"` and `LEAVE_TRACKING_PROVIDER = "leave.tracking.fixture_provider.FixtureTrackingProvider"`.
- `FixtureWorkflowProvider` (backend/workflows/fixture_provider.py) resolves stages from the `FIXTURE_WORKFLOWS` map keyed by `(category, department)`: academic → `supervisor, hod, registrar, dvc`; administration → `hod, dean, registrar, dvc`; unknown falls back to `hod, dean, registrar, dvc`. Each stage's approver is the first active `User` with that role.
- `FixtureTrackingProvider` (backend/leave/tracking/fixture_provider.py) returns `WorkflowTracking` from JSON scenario files keyed by `reference_number` (fallback `pending_first_stage`), doing no DB reads.
- `assign_workflow` (backend/workflows/assignment.py) resolves `StageDefinition`s through the provider, validates them, snapshots `ApplicationStage` rows, moves the app to `pending`, sets `current_stage`/`current_approver`, and writes an audit event. Invariant 12.5: the snapshot, not the live config, is authoritative after submission.
- `decide` (backend/workflows/approval.py) advances `current_stage`/`current_approver` to the next stage's `assigned_approver_id` on approve. `approval.py:160`.
- `active_delegation_for` (backend/workflows/services.py:252) is the declared Unit-21 delegation boundary but is **not yet consulted** by routing/authority: `get_decision_authority` (backend/workflows/policies.py) and `get_view_access` require `stage.assigned_approver_id == user.id`.
- `Reassignment` rows (backend/workflows/models.py) update `LeaveApplication.current_approver` atomically — the live responsible-approver spine.

### Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Workflow resolution | Precedence: exact `(category, department)` → `(category, "")` → `("", department)` → `("", "")`; first **active** workflow (`state == "active"`) wins | Matches the fixture map's spirit but now driven by real `Workflow` rows; blank scope means "any" (model semantics) |
| What "active" means | `Workflow.is_active` AND `effective_from <= today` (state `active`); drafts (`effective_from` null) and scheduled (`effective_from > today`) are never used | Reuse the existing `Workflow.state` property |
| Stage snapshot vs live config | Keep `ApplicationStage` snapshot as the source of truth after submission; provider is consulted **only** at `assign_workflow` | Invariant 12.5; the fixture provider's cancellation-stages and member-ids already read the snapshot |
| Approver binding | For each `WorkflowStage.approver_role`, pick a single active `User` with that role. Prefer an approver in the employee's department/faculty when role+profile data allows; fall back to any active user of that role | Deterministic binding avoids silent round-robin; keeps delegate-aware spine intact |
| Delegation | `active_delegation_for(assigned_approver)` consulted by `get_decision_authority` and `get_view_access` so an active delegate may act/view; `current_approver` unchanged (delegate acts on the approver's stage) | Matches the documented boundary; no new field on `ApplicationStage` |
| Reassignment | Already atomic via `reassign_application`; provider/binding must never override a live reassignment | Progress-tracker notes (line 101) record `Reassignment` rows as the history |
| Tracking provider | New DB-backed provider reading real `ApplicationStage`/`ApprovalDecision` rows replaces `FixtureTrackingProvider`; delete the `fixtures/` scenario dir + `seed_tracking_scenarios.py` | The fixture is the last hard-coded dev workflow artifact; the tracking contract already requires the snapshot (invariant 12.5) |
| No-workflow resolution | Raise `WorkflowValidationError` (submission fails cleanly) — never silently fall back to fixture map | Same policy as today (`_validate_definitions`) |

### Scope boundaries

- **In scope:** `DatabaseWorkflowProvider` (+ new DB tracking provider), settings swap for `WORKFLOW_PROVIDER` and `LEAVE_TRACKING_PROVIDER`, delegation-aware authority/view, provider/binding unit tests, tracking serializer/contract tests, fixture deletions.
- **Out of scope (later units):** `notifications/` (Unit 22), balance deduction / approved-document (Unit 23), audit aggregation endpoints (Unit 24), workflow-config admin UI (already built in HR Units 6–7), email.

## Implementation

### 1. `DatabaseWorkflowProvider` — new `backend/workflows/database_provider.py`

Implements the `WorkflowProvider` protocol (`backend/workflows/providers.py`;
dataclasses `StageDefinition`/`StageSpec` live there; examine `StubWorkflowProvider`
or the fixture provider for the shape).

```python
def get_stage_definitions(self, application) -> list[StageDefinition]
```

- Employee scope from `application.employee.employee_profile` → `(category or "", department or "")`; when a profile is missing, no workflow applies.
- Resolve the matching active `Workflow` using the precedence in the decisions table (`state == "active"`, i.e. `is_active` and `effective_from <= today`).
- Read `workflow.stages.order_by("order")`; for each stage bind `approver_role` → `approver_user_id` via an active `User` (see §2). `role_label` from `User.Role(role).label` (same as fixture).
- Raise `WorkflowValidationError("workflow", ...)` when no active workflow matches the scope, and `WorkflowValidationError("stages", ...)` when a required approver cannot be bound.

```python
def get_cancellation_stages(self, application) -> list[StageSpec]
def get_workflow_member_user_ids(self, application) -> list[int]
```

- Keep the fixture provider's semantics unchanged (they already read the `ApplicationStage` snapshot): cancellation stages = snapshot filtered to `("supervisor", "hod")`, original order preserved; member ids = all `assigned_approver_id`s from the snapshot. Reuse this logic directly rather than re-implementing.

### 2. Approver binding helper — in `database_provider.py`

```python
def _resolve_approver(self, role: str, employee) -> User | None
```

- Candidate: active `User` with `role=role`. Prefer candidates whose `employee_profile.department` (case-insensitive) matches the employee's department when they have one; if none or profiles absent, fall back to any active user with that role, ordered deterministically (`order_by("username")`, matching the fixture's tie-break).
- Deterministic, single candidate. When binding an approver would produce a duplicate "is_final" conflict for a single-stage workflow, that is valid (one stage, `is_final=True`).

### 3. Settings swap — `backend/config/settings/base.py`

```python
WORKFLOW_PROVIDER = "workflows.database_provider.DatabaseWorkflowProvider"
LEAVE_TRACKING_PROVIDER = "leave.tracking.database_provider.DatabaseTrackingProvider"
```

- Delete `backend/workflows/fixture_provider.py` only after the DB provider passes the existing workflow/assignment tests. Update the `# Approval workflow provider` and `# Leave application tracking` comments.
- Delete `backend/leave/tracking/fixtures/` (scenario JSON + `assignments.json`) and `backend/leave/management/commands/seed_tracking_scenarios.py` once nothing references them.

### 4. Delegation-aware authority and view — `backend/workflows/policies.py`

- `get_decision_authority`: currently requires `stage.assigned_approver_id == user.id`. Add: `active_delegation_for(stage.assigned_approver)` where its `delegate_id == user.id` also grants `can_decide`. Return the same `not_current_stage`/`already_decided` reasons otherwise.
- `get_view_access`: include stages where the user is the assigned approver **or** the active delegate of the assigned approver. Keep the "earliest reached stage" semantics and the 404-on-none behavior.
- Existing delegation tests (Unit 8) plus new tests for authority/view under an active delegation must pass.

### 5. DB-backed tracking provider — new `backend/leave/tracking/database_provider.py`

Implement `TrackingProvider` (`backend/leave/tracking/provider.py`) returning a `WorkflowTracking` (`backend/leave/tracking/contracts.py`) built from the **real** rows for the application:

- `status`, `approved_at`, `current_stage` from `LeaveApplication` + `current_stage.assigned_approver`.
- `stages` from `ApplicationStage` rows (`assigned_at` from the stage → fall back to workflow-assignment audit event time; `decided_at`/`comment` from the linked `ApprovalDecision`).
- `events` from `AuditEvent` rows for the application plus `ApprovalDecision` rows (decision type, stage order, actor name, comment, resubmission number).
- `rejection`/`correction`/`resubmission` from `ApprovalDecision` action `reject`/`return_for_correction` and the resubmission service state (`leave/services/resubmission.py`, `LeaveApplicationRevision`).
- `submission_cycle`/`resubmissions`/`decisions` from the revision + decision rows.
- Center the null-safety: applications with no stages (pre-routing edge) return an empty tracking payload rather than erroring.

Keep the `TrackedApprover`/`TrackedEvent`/`TrackedOutcome` shapes in `contracts.py` unchanged. Delete `fixture_provider.py` (tracking) after tests pass and the tracking app tests re-point to the DB provider.

### 6. Tests

Backend (`backend/workflows/tests.py` or a new `test_database_workflow_provider.py` + tracking tests):

- Workflow resolution precedence (exact category+department beats category-only beats department-only beats any; scheduled/draft never used).
- Approver binding across roles; department-preference falls back to any active user deterministically; a role with no active user raises `WorkflowValidationError`.
- Full submission→assignment→decide journey with a 3-stage real workflow: stages snapshot in order, first pending, rest waiting, final marked, `current_approver` = first stage approver, sequential advance on approve, advance sets delegation-eligible approver.
- Delegation: active delegate can decide (authority + view); ended/cancelled delegation restores the original approver only.
- Reassignment: after `reassign_application`, the delegate/assigned-approver policy still honors the new `current_approver`.
- No-workflow scope: submission fails cleanly with `WorkflowValidationError`.
- Tracking: DB provider renders correct stages/events/rejection/correction for a routed app; no-ledger upgrade needed.
- Seed commands still work: `seed_dev_users` + `seed_approvals_dev` must create a workflow-config + approver set that routes the seeded scenarios (verify at least one academic and one administration approval runs end-to-end in dev).

Frontend: no component changes are expected unless tracking JSON shape changes; run `npm test`.

## Dependencies

- No new packages. Requires `Workflow`/`WorkflowStage` (HR Units 6–7), `Delegation` (Unit 8), `Reassignment` (Unit 9), `ApplicationStage`/`ApprovalDecision` (Unit 16), tracking contracts (Unit 15), and the `DatabaseRulesProvider` from Unit 20.

## Verification checklist

- `TEST_DB_NAME=test_luanar_leave_21 DJANGO_SETTINGS_MODULE=config.settings.test uv run manage.py test workflows users leave --keepdb --parallel auto` green (incl. existing assignment/approval/cancellation tests under the DB provider).
- New provider/binding/delegation/reassignment/tracking tests green.
- `manage.py check` clean.
- Frontend `npm test` green; `tsc --noEmit` clean; `eslint` clean; `npm run build` clean.
- Manual dev check with `seed_dev_users` + `seed_approvals_dev`: a real submitted application routes academic → supervisor→hod→registrar→dvc (and administration → hod→dean→registrar→dvc) against **configured** workflows, sequential advance works, a delegated approver sees and can act, and the employee tracking page shows real stages/events.
- Migration safety: a single `makemigrations` pass with the new worktree; merge-time numbering reconciliation with any session that adds migrations.
=======
read `context/AGENTS.md` before starting. Depends on the HR track (Units 6–9
workflow/delegation/reassignment models + endpoints) and the Employee + Approver
track (Units 14–17, decision/service/schema spine). Build-plan §6 Unit 21.

## 1. Goal

Connect HR workflow configuration to real submitted applications. Replaces the
last two fixture providers — `WORKFLOW_PROVIDER` and `LEAVE_TRACKING_PROVIDER` —
with real workflow-backed implementations, and makes the routing that decides
**who must act now** authoritative, delegation-aware, and reassignment-aware:

```text
HR configures workflow
        ↓
Employee submits application
        ↓
System resolves applicable workflow
        ↓
Correct approver receives application
        ↓
Approver acts
        ↓
Next configured stage receives application
```

Visible result (build-plan): *"A real submitted application automatically
follows the workflow configured by HR."* Verification axes: employee category
routing, department/faculty routing, mandatory stages, sequential progression,
correct responsible approver, delegated approvers, reassigned applications.

## 2. Decisions locked in

| # | Decision |
|---|---|
| D1 | **`WORKFLOW_PROVIDER` → `DatabaseWorkflowProvider`** (`workflows/providers.py::DatabaseWorkflowProvider`). Reads real `Workflow`/`WorkflowStage` rows; fixture chains and the `FixtureWorkflowProvider` default are removed. `leave/tracking/fixtures/*`, `seed_tracking_scenarios`, and `FixtureRulesProvider`-style default tests are removed with their providers. |
| D2 | **`current_approver` is THE "who must act now" spine.** `LeaveApplication.current_approver` is authoritative for routing (as the Unit 9 spec intended). `ApplicationStage.assigned_approver` stays the immutable workflow snapshot (Unit 24 integrity). Every routing consumer — approvals pending list, capabilities count, `get_decision_authority`, and the tracking "responsible approver" — consults the spine. Writers: `assign_workflow` (first stage, already does), `decide()` advance (new), resubmit (new), `reassign_application` (already does). |
| D3 | **Acting approver (delegation).** `responsible_approver(app) = app.current_approver`; the **acting approver** = `active_delegation_for(responsible).delegate` when a delegation is active, else `responsible`. Single-level only — a delegate's own active delegation is not cascaded. Applications under a delegation are visible to the **delegate only**; on delegation end/cancel they fall back to the original approver automatically (query-time resolution). Decisions are recorded with the actual acting approver as `ApprovalDecision.approver` (the delegate, for escorted acts). |
| D4 | **Stage → approver rule kept.** A `WorkflowStage.approver_role` resolves to the lowest-id active user holding that role — the same deterministic rule the fixture used (`_first_active_user_id`), centralised so delegation/deactivation audits stay consistent. `WorkflowStage` stays role-based (Unit 6: no user column). |
| D5 | **Workflow resolution.** Applicable = `is_active=True` and `effective_from <= today`. Scope match precedence against the employee's `(category, department)`: exact `(category, department)` wins, then `(category, any)`, then `(any, department)`, then `(any, any)`; ties break to the earliest `effective_from`. No match → `WorkflowConfigError` (mapped to `workflow_unavailable`). |
| D6 | **Invariant 12.7 enforced on submission.** `leave/services/workflow_gate.check_workflow_ready` stops being a no-op: it resolves the applicable workflow + an active approver for every stage and raises a structured error when none exists. `submit_application` maps it to `ValidationFailedError` `workflow_unavailable` (the mapping `assign_workflow` already uses — that call also wraps `WorkflowConfigError` so a misconfigured/unsatisfiable workflow can never 500). |
| D7 | **Routing consumers.** `ApprovalListAPIView` (pending tab), `ApprovalsCapabilitiesView.pending_count`, and `policies.get_decision_authority` switch from `current_stage__assigned_approver=user` to acting-approver resolution (D2/D3). Decided-tab "hide if now pending with this approver" logic uses the same resolution. The review payload's current-stage approver block gains the acting approver name (delegate + "on behalf of" when escorted). |
| D8 | **Reassignment is spine-only.** No `ApplicationStage` mutation on reassignment (history lives in `Reassignment` rows; the snapshot stays intact). The new approver automatically sees and can decide purely from D2/D3. |
| D9 | **Resubmission action included in this unit** (it is the missing routing step between Unit 17's schema/payload work and real tracking): new `POST /api/v1/leave-applications/{id}/resubmit/` transitions `rejected`/`correction_required` → `submitted`, increments `submission_cycle`, re-opens the returning stage in place (`pending`, `decision_version += 1`), points `current_stage` at it, and sets `current_approver` to the returning stage's **configured** `assigned_approver` — not the rejecting actor. This is deliberate (D3 consistency): the spine always holds the configured responsible approver of the current stage, and any active delegation/reassignment re-applies automatically at query time. So a resubmitted app that lands on a delegated or reassigned stage is picked up by the delegate/reassignee only while that intervention is still active; when none is, it returns to the stage's configured approver. Re-runs validation (snapshot refresh, same reference) and records `application_resubmitted` audit. The chain is kept, not rebuilt. |
| D10 | **`LEAVE_TRACKING_PROVIDER` → `DatabaseTrackingProvider`** (`leave/tracking/database_provider.py`). Builds `WorkflowTracking` from real `ApplicationStage`, `ApprovalDecision`, `Reassignment`, and `CancellationRequest` rows. Tracking fixture scenarios + `seed_tracking_scenarios` and their tests are removed; Unit 15 fixture tests are reworked to construct real rows. |
| D11 | **Tracking payload contract unchanged.** Same dataclass shape/serializer (frontend depends only on the serialized JSON). Event type vocabulary pinned to the frontend `EVENT_ICONS` set: `submitted`, `approved`, `rejected`, `correction_requested`, `resubmitted`, `reassigned` (anything else renders "Workflow update"). Stage `state` vocabulary is `approved | awaiting | rejected | returned | skipped | upcoming`; `skipped` is a stage bypassed because routing starts after the applicant's last stage (invariant 12.3 sole exception), and both the tracking stepper and the approver approval timeline render it as neutral with an explanation. |
| D12 | **Tracking semantics.** `status` = `pending | approved | rejected | correction_required | cancelled`. `approved_at` from the final-stage approve decision. `can_resubmit` = status in `{rejected, correction_required}`; `returns_to_stage` and the outcome blocks derive from the last decision's stage. `resubmission.count` = `submission_cycle - 1`; `last_resubmitted_at` from the latest resubmit. `TrackedApprover.is_delegate` true when the deciding/acting approver ≠ the stage's `assigned_approver`, with `on_behalf_of` = the original approver's name. |
| D13 | **Cancellation chain unchanged.** `get_cancellation_stages`/`get_workflow_member_user_ids` already read the materialised `ApplicationStage` snapshot (provider-agnostic); only the fixture-only `get_stage_definitions` path changes. Cancellation approval continues consulting the same snapshot rows. |
| D14 | **No new schema expected.** `submission_cycle`, stage statuses (`superseded` exists for chain-keeping), and the spine FK already cover all of this unit. Verify with `makemigrations --check`; if a migration appears, stop and reassess before running it. |
| D15 | **Seed** `seed_approvals_dev` builds real, idempotent `Workflow` + `WorkflowStage` rows (academic → `hod`, `dean`, `registrar`, `dvc`; administration → `supervisor`, `hod`, `registrar`, `dvc`) so its submissions route through `DatabaseWorkflowProvider`; tracking scenarios move to real rows via the seed's existing submit/decide flow. |

## 3. Implementation order (verify each step)

### 3.1 `DatabaseWorkflowProvider` (D1, D4, D5) + gate (D6)

- `workflows/providers.py`:
  - Keep `StageDefinition`, `CancellationStageSpec`, `WorkflowProvider` protocol, `get_workflow_provider()`. Extend fetching a canceled flag if needed — otherwise nothing.
  - New `resolve_applicable_workflow(application) -> Workflow | None` implementing D5 precedence (one query per specificity bucket or a scored annotation; only `is_active=True` and `effective_from <= today`; order ties by `effective_from`).
  - New `DatabaseWorkflowProvider.get_stage_definitions`: resolve workflow → map `WorkflowStage` rows (ordered) → `StageDefinition` with `approver_user_id = lowest-id active user(role)` (D4). No match → `WorkflowConfigError("no_workflow", message)`; role with no active user → `WorkflowConfigError("approver", message)`.
  - `get_cancellation_stages` / `get_workflow_member_user_ids`: shared snapshot helpers already read `ApplicationStage` rows (D13) — reuse for both providers.
  - Remove `FIXTURE_WORKFLOWS` and `FixtureWorkflowProvider`; `config/settings/base.py`: `WORKFLOW_PROVIDER = "workflows.providers.DatabaseWorkflowProvider"`.
- `workflows/services.assign_workflow`: wrap `WorkflowConfigError` from `get_stage_definitions` into `WorkflowAssignmentError` (belt for the real provider; the gate also catches it).
- `leave/services/workflow_gate.py`: replace the `True` stub with `check_workflow_ready(application)` that calls the provider, validates every definition resolves an approver, and raises a new `WorkflowUnavailableError(messages)` on failure. Gate drafts too (an employee with no applicable workflow cannot submit at all).
- `leave/services/submission.py`: catch `WorkflowUnavailableError` next to `WorkflowAssignmentError` and map both to `ValidationFailedError([{code: "workflow_unavailable", message, field: "—"}])`. Confirm `AlmostAsDocumented` the `submit` view already converts `ValidationFailedError` → 422.

### 3.2 `current_approver` spine + acting approver (D2, D3, D7)

- `workflows/services.py`:
  - New helper `responsible_approver_id(application)` → `application.current_approver_id` (fall back to `current_stage.assigned_approver_id` only for legacy/migration rows where the spine is null).
  - `decide()` approve-advance (non-final): after setting `app.current_stage = next_stage`, also set `app.current_approver = next_stage.assigned_approver` and include it in `save(update_fields=...)`.
  - `assign_workflow`: unchanged (already sets the spine).
  - Resubmit service `resubmit_application(*, user, application_id)` (D9): guard status ∈ `{rejected, correction_required}` + ownership (404 foreign/nonexistent), re-run `run_validation(application=app)` (+ refresh `rules_snapshot`, re-evaluate `working_days`/`calendar_days`/`financial_year_label`), increment `submission_cycle` (via `F` inside the lock), flip the returning stage — the app's `current_stage` — back to `PENDING` with `decision_version += 1`, set `current_stage` = that stage, `current_approver` = its `assigned_approver`, `status = SUBMITTED`, reference retained, audit `application_resubmitted`, and the submission signal on commit. The chain is never rebuilt (D9).
- `workflows/policies.py`:
  - `get_decision_authority`: replace `stage.assigned_approver_id != user.id` with `acting_approver = active_delegation_for(current_approver).delegate or current_approver; acting_approver.id != user.id → not_current_stage`. Keep the closed/already-decided guards and `_decided_this_cycle`.
  - `get_view_access` (read): a user may view a stage they are assigned to **or** act on through delegation/reassignment — resolve using the same acting-approver rule for the pending stage, plus existing decided-stage rows.
- `workflows/approval_views.py`:
  - `ApprovalsCapabilitiesView.pending_count`: count submitted applications where the **acting approver is the user**.
  - `ApprovalListAPIView` pending tab: same acting-approver predicate. Implementation: `current_approver=user` **and** no active delegation covering `user` for the current date (the user acts for themself), union with `current_approver` in the set of approvers whose active delegation names `user` as delegate (D3). Keep the decided tab as-is except the "hide when pending with this approver" exclusion now keys off the acting approver.
- `workflows/approval_payloads.py`: `_current_stage_block`/`_stage_block` for the live (`pending`) stage render the **acting** approver (name; plus `acting_for` = responsible approver name when delegated) so the approver dashboard and review screen tell the user they are acting for someone. Snapshot stage blocks keep `assigned_approver` (the immutable record).

### 3.3 Resubmission endpoint (D9)

- `leave/views/resubmit.py` (mirror `views/validation.py::LeaveApplicationSubmitView`): `POST /api/v1/leave-applications/{id}/resubmit/` → 200 submit-style payload, 404 foreign, 409 invalid status/draft, 422 validation (reuse the same error shape). Wire in `leave/urls.py`.
- Reject/record the UI path: the existing review screen "resubmit" button can be linked later (this unit verifies the API + routing; the tracking payload's `can_resubmit`/`returns_to_stage` now reflect real state).

### 3.4 `DatabaseTrackingProvider` (D10, D11, D12) + fixture removal

- `leave/tracking/database_provider.py` — `DatabaseTrackingProvider.get_workflow_tracking(application)`:
  - Applies the owner + submitted guards at the service boundary (already in `services.get_application_tracking`).
  - `status`: `submitted`→`pending`; `approved`; `rejected`; `correction_required`; `cancelled`.
  - `stages`: the `ApplicationStage` chain under `workflow_chain_cycle`, ordered, mapped to `TrackedStage` (`state` D11; `approver` from the acting/deciding approver per stage with D12 `is_delegate`/`on_behalf_of`; `assigned_at` from `created_at`; `decided_at`/`comment` from the stage's latest decision).
  - `events` newest-first: `submitted` (from `submitted_at`); `approved`/`rejected`/`correction_requested` (from `ApprovalDecision` rows, actor/comment/stage); `resubmitted` (from resubmit audit or cycle deltas); `reassigned` (from `Reassignment` rows, actor = HR decided_by, comment = reason).
  - `rejection`/`correction`/`resubmission` per D12; `approved_at` from the final-stage approve decision.
  - Cancellation blocks: keep delegating to the existing additive helpers so Unit 18 contract fields stay populated (`cancelled_at`, `cancellation_action`, `has_open_cancellation_request`, `latest_cancellation`).
- `config/settings/base.py`: `LEAVE_TRACKING_PROVIDER = "leave.tracking.database_provider.DatabaseTrackingProvider"`.
- Remove `leave/tracking/fixture_provider.py`, `leave/tracking/fixtures/`, and `leave/management/commands/seed_tracking_scenarios.py` — **backend only**. The frontend `lib/tracking/__fixtures__/*` and `components/tracking/__fixtures__/*` JSONs are provider-independent component-test data and are kept.

### 3.5 Seeds (D15)

- `backend/workflows/management/commands/seed_approvals_dev.py`: create idempotent `Workflow` + `WorkflowStage` rows (scope academic / administration, active, `effective_from = FY.start`) so its 7 submit/decide scenarios route through `DatabaseWorkflowProvider`; keep `CommandError` when no active FY. `_seed_documents` unchanged.

### 3.6 Docs

- `backend/docs/leave-rules-provider-contract.md` or a new `backend/docs/workflow-to-approver-routing.md`: document the spine (D2), acting-approver resolution (D3), workflow resolution precedence (D5), resubmit contract (D9), and the tracking event vocabulary (D11).
- `context/progress-tracker.md`: mark Unit 21 spec + decisions; after completion, mark the unit complete and set "Next Up" = Unit 22.
- Cross-reference Threads: `leave/tracking/contracts.py` docstring ("Unit 20 must reconcile…"), `workflows/providers.py` ("replaced … in a later unit"), `workflow_gate.py` TODO — update to "done in Unit 21".

### 3.7 Tests

- `workflows/tests_approvals.py`: replace `WorkflowProviderFixtureTests` with `DatabaseWorkflowProvider` tests — resolution precedence (category/dept), private-chain fallback, tie → earliest effective, inactive/scheduled/draft never apply, approver = lowest-id active user.
- New `workflows/tests_routing.py`: acting-approver routing — pending list + capabilities (`current_approver` spine; delegate sees apps; original does not while delegation active; fallback on end), `decide()` advances the spine on approve (and does not on reject/correction), reassigned approver sees + can decide with no stage mutation, delegated decision records the delegate and `get_decision_authority` grants the delegate and denies the original.
- New `leave/tests/test_resubmission.py`: 404 foreign, 409 invalid status, 422 validation re-run; happy path cycle increment, stage reopened, `current_approver` returned, reference stable, audit row, signal; `assign_workflow` not re-run.
- Rework `leave/tests/test_tracking_*` to real rows (submitted/approved/rejected/correction/resubmitted/reassigned/cancelled scenarios built through the real services), asserting the D11/D12 vocabulary and the `assertNumQueries` ceiling; delete fixture-only scenario tests.
- `workflow_gate` tests: no workflow for the category/department → `WORKFLOW_UNAVAILABLE` via `workflow_unavailable` (422), and `WorkflowConfigError` inside `assign_workflow` never 500s.
- Full backend suite + `manage.py check` + `makemigrations --check` (expect no diff, D14). Frontend: run `npm test`, `tsc --noEmit -p tsconfig.test.json`, `npm run lint`, `npm run build`.

## 4. Verification checklist

- [ ] `WORKFLOW_PROVIDER` / `LEAVE_TRACKING_PROVIDER` point at the real providers; `FixtureWorkflowProvider`, tracking fixtures and `seed_tracking_scenarios` are deleted.
- [ ] A submission routes through the applicable HR-configured workflow: correct first approver by category/department scope; all stages mandatory and sequential.
- [ ] Routing starts after the applicant's last stage and continues forward only: every stage at or before it is kept as `skipped` and audited `STAGE_SKIPPED`, including lower-level non-self stages, and a bypassed stage grants no review access; an application with no stage after that position is refused at submission (422 `workflow_unavailable`) because a role resolves to a single approver — invariant 12.3 sole exception.
- [ ] An employee with no applicable workflow cannot submit (`workflow_unavailable`, 422) — invariant 12.7 enforced both at the gate and inside `assign_workflow`.
- [ ] `decide()` approve advances `current_approver` to the next stage's approver; every later approver sees the app and can decide.
- [ ] Reassignment: the reassigned approver sees the app pending and can decide; `ApplicationStage.assigned_approver` unchanged; `Reassignment` history written (D8).
- [ ] Delegation: delegate sees and can decide delegated apps ("Acting for X" on review + tracking); original approver does not see them while active; they fall back when the delegation ends/cancels; decisions recorded with the delegate (D3, D12).
- [ ] Resubmit: `rejected`/`correction_required` → `submitted`, cycle increments, returns to the rejecting/correcting stage/approver, same reference, audit recorded (D9).
- [ ] `GET .../tracking/` renders a fully real payload — stages/events/outcomes/resubmission/cancellation blocks from DB rows with the D11 vocabulary.
- [ ] Assertions: `makemigrations --check` no diff (D14); full backend suite green; frontend suite + tsc + lint + build green.
>>>>>>> feature/plans-teams
