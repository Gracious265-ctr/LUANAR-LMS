# Workflow-to-approver routing contract (Unit 21)

`backend/docs/workflow-to-approver-routing.md`

This document pins the routing spine that connects a leave application's
workflow (Unit 6 / Unit 16 model) to the human approvers who act on it. Every
consumer — the pending-approvals list, the tracking endpoint, the approval
capabilities count, `get_decision_authority`, the acting-approver resolution
and the tracking "responsible approver" block — reads the *spine first* and
falls back to the stored stage snapshots only where the spine has no answer.

## D2 — The spine (`current_approver`)

`LeaveApplication.current_approver` is the single "who must act now" fact.
It always points at the **configured** responsible approver of the current
stage of the *current* submission cycle:

- Set by `assign_workflow` (first stage), `decide()` (advance on approve),
  `resubmit_application` (returning stage's configured approver) and
  `reassign_application`.
- Never mutated by delegation or reassignment: those expire/reassign at
  query time through D3, leaving the spine's stored approver untouched.
- Read by every routing consumer through `get_decision_authority` /
  `active_delegation_for` / the tracking "stages → assigned_approver →
  responsible approver" chain.

## [D3] — Acting-approver resolution

At decision time the actual actor is resolved *in order*:

1. an **active delegation** of the stage's configured approver → the delegate
   (only while the delegation is with-in-effect; no cascade — a delegate is
   never itself delegated);
2. an **active reassignment** of the application → its reassignee;
3. otherwise the configured `assigned_approver` of the current stage.

Resolution never mutates the spine (`current_approver`); the resolved acting
approver is computed on demand (`get_decision_authority`) and recorded on the
`ApprovalDecision`/`Reassignment` rows for the tracking vocabulary.

## [D5] — Workflow resolution precedence

`resolve_applicable_workflow` selects the spine's stage definitions by
precedence:

1. exact `(category, department)` match;
2. `(category, any-department)` — category applies, department is wildcard;
3. `(any-category, department)` — department applies, category wildcard;
4. global `(any-category, any-department)` fallback.

Ties at the same precedence resolve to the **earliest effective**
definition. Configurations that are inactive, scheduled (future-effective)
or drafts never apply. If nothing matches, submission is gated with
`workflow_unavailable` (422) — never a 500.

D5 also documents the fallback contract used by Unit 16's fixture provider:
stages resolve through `get_stage_definitions` filtered to active, effective
definitions ordered by precedence, with chain fallback to the single global
spine when no category/department definition applies.

## [D9] — Resubmit contract

`resubmit_application` is the sole path that returns a rejected application
to workflow as a fresh pending approval:

- re-validates current content against the rules effective on the
  resubmission date (same reference number);
- increments `submission_cycle` (via `F` inside the lock);
- reopens the **returning stage in place** — `pending`, `decision_version + 1`;
- sets `current_stage` = returning stage and `current_approver` = its
  **configured** assigned approver (not the rejecting actor, per the Unit 21
  spine rule);
- **never rebuilds** the stage chain (the spine is kept; `assign_workflow`
  is not re-run);
- records `application_resubmitted` audit; re-emits the submission signal.

Error contract: 404 (`ResubmissionNotFoundError`), 409 (`NotResubmittableError`
/ `WorkflowInconsistentError`), 422 (`ValidationFailedError` — the re-run of
the rules validation failed).

## [D11] — Tracking event vocabulary

The tracking payload's `events` block is a newest-first vocabulary owned by
the frontend's `EVENT_ICONS`:

- `submitted` — from `submitted_at`; owner/initiator.
- `approved` / `rejected` — from the
  `ApprovalDecision` at a stage (verboten: tracking vocabulary keeps human
  readable `role_label` + `approver_name`, never raw role codes).
- `resubmitted` — from the resubmit audit / cycle deltas (D9).
- `reassigned` — from the reassignment rows (initiator = HR).

Each event carries the actor's full name and role label; stage `state`
vocabulary stays `pending | approved | rejected | upcoming`.
`current_stage` reflects the spine's *configured* approver regardless of any
active delegation/reassignment, which the tracking view re-applies at query
time (D3).

## Spine consumers

The pending-approvals list (`assignments_pending`), the capabilities count and
the tracking "responsible approver" block all use `get_decision_authority`,
which resolves D2 → D3. `workflow_gate` uses D5 to decide whether an
application has a workflow at all; `workflow_gate:TODO` (Unit 20) was
resolved in Unit 21 — see `workflows/providers.py` and the routing tests.
