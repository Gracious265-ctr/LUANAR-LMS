# Unit 21 — Workflow-to-Approver Integration

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