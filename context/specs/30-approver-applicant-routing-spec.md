# Unit 30 — Approver Applicants: Skip-Forward Routing, HR Destination, Per-Workflow Uniqueness

## The request

Approvers must be able to apply, and their own application must route past them:

- an approver applicant's stages are skipped, and the application starts at the
  **first higher** stage;
- never backward, never to a lower stage;
- a **final** approver's application skips the whole chain and goes to **HR**,
  who approves or rejects it — never auto-approved;
- within one workflow, an employee appears on **one** stage and a role on
  **one** stage.

## What already holds

Verified, not assumed. Most of the request is standing:

| Req | Holds at |
| --- | --- |
| 1 Approvers can submit | `tests_self_approval.py::SharedSectionStillRoutesTests` |
| 2 No self-approval, backend | `policies.get_decision_authority` → `Authority(False, "self_application")`, 403 |
| 4 Lower-stage cannot approve a higher-stage applicant | `user_may_act` authorises only the **current** stage's approver; a direct API call gets 403 `not_current_stage` |
| 5 Higher-stage approves a lower-stage applicant | The chain already runs in order |
| 8 Team-specific workflow | `DatabaseWorkflowProvider` reads `team.workflow`; authority never comes from another team's configuration |
| 14/15 Normal employees; workflow unmodified | Provider is pure data — planned stages, no writes |
| 18 Backend authoritative | One gate, "independent of stage assignment… holds even where assignment logic was bypassed" |

**Req 17 needs no work and must not get any.** There is no submission-time
notification in this system. The only registered consumer is
`send_decision_email`, and it fires on *decisions*
(`notifications/services.py:113`). "John is not notified" is already true because
nobody is notified on submit. Adding submission emails would be new functionality,
which the request explicitly rules out.

## What actually changes

### Part A — Per-workflow uniqueness (new)

`Section.Meta.constraints` holds only `section_workflow_order_unique`. Nothing
prevents one employee, or one role, appearing on two stages of the same workflow.

- `UniqueConstraint(workflow, approver)` — an employee on one stage per workflow.
- `UniqueConstraint(workflow, approver_role)` — a role on one stage per workflow.

`approver` is nullable so unstaffed draft steps stay legal (Postgres treats NULLs
as distinct). `approver_role` is **not** nullable. Verified no duplicates exist in
the dev database, so both apply without a data migration.

Validation lives in the chain-writing path and checks the **whole resulting set**,
which is what makes req 13 fall out for free: the edited stage is part of the
payload, so it is compared against the others rather than against itself.

Per-workflow, not global (req 10) — the same person may hold the same role on a
different team's workflow, which is exactly what `ensure_role_consistency` already
permits across teams and what its docstring says.

### Part B — Skip-forward routing (reverses invariant 12.3)

`architecture.md:506` currently states there is "**no bypass and no `skipped`
state**" and that a step the applicant holds is "**refused, never skipped**".
`assign_workflow` says so in code comments too. This unit reverses that, per the
product decision recorded on 2026-10-02.

- `ApplicationStage.Status.SKIPPED` — **necessary**, not gratuitous. Req 16 asks
  for skipped stages recorded with a reason, and req 16 also says not to add
  unnecessary states; this one is load-bearing, because without a terminal
  non-waiting status a skipped stage is indistinguishable from one still to come.
- `ApplicationStage.skip_reason` — why it was skipped.

Routing rules, computed in `DatabaseWorkflowProvider`:

| Applicant | Stages ≤ applicant's | Route to |
| --- | --- | --- |
| Approver of stage *k* | 1..*k* SKIPPED | first stage > *k* |
| Approver of the **last** stage | all SKIPPED | an appended HR stage |
| Approver of **no** stage | none | stage 1 (unchanged) |

The HR stage reuses the existing stage machinery rather than a parallel approval
system (req 7): one more `ApplicationStage` with `section_ref=None`,
`role="hr"`, `history_scope="all"`, `is_final=True`, and **every active HR user**
in `eligible_approvers`. `get_view_access` and `get_decision_authority` then work
unchanged, because both already resolve through `user_may_act` →
`acting_approver_ids` → the `eligible_approvers` snapshot. Approving it finalises;
rejecting it rejects, through the same `decide()`.

Decisions:

- **D1 — The applicant's stage is found by section, not by role.** With Part A's
  employee-uniqueness constraint an applicant holds at most one stage per
  workflow, so "the applicant's stage" is well defined. This is why A precedes B.
- **D2 — The HR stage is a stage, not a flag.** A boolean would need its own
  authority check, its own notifications, and its own history rendering. A stage
  gets all three from code that already exists and is already tested.
- **D3 — The applicant is excluded from the HR stage's eligibility.** If that
  leaves nobody — the sole HR user is applying — submission is refused with a
  message naming the cause, rather than deadlocking on an application nobody can
  decide.
- **D4 — No HR account configured is a refusal, not a silent pass.** An
  application cannot be finalised by nobody.
- **D5 — Part A's constraints apply to writes only.** An in-flight chain already
  materialised keeps its stages; the constraint is on `Section`, and a section
  cannot be edited into a duplicate anyway.
- **D6 — §12.3 is rewritten, and `tests_self_approval.py` with it.** Twelve tests
  encode refusal, including `test_nothing_is_ever_skipped`,
  `test_the_chain_starts_at_the_first_section`,
  `test_tracking_reports_no_skipped_states`, and all six of
  `SoleMemberSectionIsRefusedTests`. They are revised to assert the new policy,
  not deleted — they are the tests that will catch a regression in it.

## Out of scope

- Submission-time notifications (req 17 — see above).
- Any change to finalisation, balance deduction, or document generation. The HR
  stage runs through the existing `decide()` and `finalise()`.
- Delegation, reassignment, and cancellation routing.

## Verification

1. `workflows` + `leave` targeted, then the full backend suite on a fresh
   database, count stated.
2. `manage.py check` and `makemigrations --check --dry-run` clean.
3. The 16 required tests present, plus the twelve revised ones.
4. Frontend suite, `tsc`, `eslint` stated in the tracker.