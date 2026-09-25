# Unit 21 — Workflow-to-Approver Integration

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
| D11 | **Tracking payload contract unchanged.** Same dataclass shape/serializer (frontend depends only on the serialized JSON). Event type vocabulary pinned to the frontend `EVENT_ICONS` set: `submitted`, `approved`, `rejected`, `correction_requested`, `resubmitted`, `reassigned` (anything else renders "Workflow update"). Stage `state` vocabulary stays `approved | awaiting | rejected | returned | upcoming`. |
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
- [ ] An employee with no applicable workflow cannot submit (`workflow_unavailable`, 422) — invariant 12.7 enforced both at the gate and inside `assign_workflow`.
- [ ] `decide()` approve advances `current_approver` to the next stage's approver; every later approver sees the app and can decide.
- [ ] Reassignment: the reassigned approver sees the app pending and can decide; `ApplicationStage.assigned_approver` unchanged; `Reassignment` history written (D8).
- [ ] Delegation: delegate sees and can decide delegated apps ("Acting for X" on review + tracking); original approver does not see them while active; they fall back when the delegation ends/cancels; decisions recorded with the delegate (D3, D12).
- [ ] Resubmit: `rejected`/`correction_required` → `submitted`, cycle increments, returns to the rejecting/correcting stage/approver, same reference, audit recorded (D9).
- [ ] `GET .../tracking/` renders a fully real payload — stages/events/outcomes/resubmission/cancellation blocks from DB rows with the D11 vocabulary.
- [ ] Assertions: `makemigrations --check` no diff (D14); full backend suite green; frontend suite + tsc + lint + build green.