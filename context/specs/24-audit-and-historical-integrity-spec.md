# Unit 24 — Complete Audit and Historical Integrity (Detailed Design)

**Scope:** make the audit trail genuinely append-only, and preserve the per-cycle
context an approver actually saw across resubmission cycles.
**Status:** Phase 2 complete (implemented and verified 2026-09-25). Spec drafted
2026-09-25 and approved by the developer before any implementation code.

---

## 1. Context recap

The build plan (`context/specs/luanar-build-plan.md:814-856`) gives Unit 24 two
goals:

1. **Connect all significant operations into the audit trail** — submission,
   approval, rejection, correction, resubmission, cancellation, delegation,
   reassignment, rule changes, entitlement changes, workflow changes, document
   replacement.
2. **Historical integrity** — a submitted application preserves the rules and
   workflow context that existed at submission time; HR later editing a
   `LeaveRule`, `GradeEntitlement`, or `Workflow` must not rewrite history.
   Reinforced by `context/ai-workflow-rules.md` §14 and `context/code-standards.md`
   §"Audit and History" ("audit history must not be silently deleted";
   "historical records must not be rewritten to falsify past decisions").

Phase-1 verification against the real code changes the shape of this unit.

### 1.1 Goal 1 is already satisfied by Units 9–23 — do not re-wire

All twelve operations already write an audit entry from inside the transaction
that owns the action. Verified call sites:

| Operation | Call site | `Action` |
| --- | --- | --- |
| Submission | `leave/services/submission.py:140` | `SUBMITTED` |
| Approval / rejection / correction | `workflows/services.py:847` | `APPROVED` / `REJECTED` / `CORRECTION_REQUESTED` |
| Resubmission | `leave/services/resubmission.py:124` | `APPLICATION_RESUBMITTED` |
| Cancellation (request / withdraw / stage / approve / reject) | `leave/cancellations/services.py:277,352,544,587` | `CANCELLATION_*` |
| Delegation (create / approve / reject / cancel) | `workflows/services.py:390` | `CREATED` / `UPDATED` / `CANCELLED` |
| Reassignment | `workflows/services.py:603` | `REASSIGNED` |
| Rule / entitlement / financial-year / public-holiday / workflow / leave-type changes | `audit/serializers.py:41-68` (`AuditedModelSerializer`) | `CREATED` / `UPDATED` |
| Document add / replace / remove / retire | `leave/documents/services.py:83,114,124,168` | `DOCUMENT_*` |
| Employee changes | `users/serializers.py:174` | `CREATED` / `UPDATED` |

`backend/audit/tests.py::AuditWiringTests` already asserts per-operation
auditing, including `test_failed_delegation_action_writes_no_audit_entry` and
`test_create_rolls_back_when_audit_fails` (a failed action never leaves a
phantom entry). The existing `Action`/`TargetType` vocabulary is sufficient —
**Unit 24 adds no new audit members.**

So Unit 24 is a **hardening** unit, not a wiring unit. The two real gaps are
below.

### 1.2 Gap A — `AuditEntry` is documented append-only but enforces nothing

`backend/audit/models.py:5-96`. The docstring states "Entries are append-only
and HR-read-only" (lines 10-12), but the model has **no `save()` guard, no
`delete()` guard, and no custom QuerySet/Manager**. Any code path can rewrite or
erase history:

```python
entry.reason = "cleaned up"; entry.save()
entry.delete()
AuditEntry.objects.filter(actor=user).update(reason="")
AuditEntry.objects.all().delete()
```

The HTTP and admin surfaces are already sealed — `AuditEntryViewSet` is
`http_method_names = ["get", "head", "options"]` (`audit/views.py:26`) and the
admin has no delete permission (`audit/tests.py:748`). **The hole is the ORM
layer only**, which is exactly the layer a future refactor or admin script
reaches for.

The codebase already owns the correct pattern three times over:

* `ApprovalDecision` — `backend/workflows/models.py:357-378` (error type +
  QuerySet blocking `update`/`delete` + Manager) and `:460-472` (instance
  `delete()` always raises; instance `save()` raises unless `_state.adding`).
* `NotificationOutbox` — `backend/notifications/models.py:25-42` (same shape,
  Unit 22).
* `LeaveBalanceTransactionManager` — `backend/leave/cancellations/models.py:205`.

Unit 24 applies the identical discipline to `AuditEntry`.

**No migration required.** No model in the project sets `use_in_migrations`, so
swapping in a custom `Manager` produces no migration state change
(`makemigrations --check` stays clean).

**Blast radius is one test.** `audit/tests.py:99`
(`test_ordering_is_newest_first`) backdates `created_at` via a bulk `.update()` to
force deterministic ordering. That is the only bulk mutation of `AuditEntry`
anywhere in `backend/`. Since `created_at` is `auto_now_add`, a supplied value
is ignored at insert anyway, so the test is reworked to assert natural
descending order over consecutively created rows.

### 1.3 Gap B — per-cycle history is lost on resubmission; `ApplicationRevision` is dead code

`backend/leave/models.py:333-393` defines `ApplicationRevision` with the right
shape: `revision_number` (documented as equal to the application's
`submission_cycle`), the approver-facing projection (`leave_type_id`,
`leave_type_name`, `start_date`, `end_date`, `working_days`, `reason`),
`documents`, `changes`, `created_by`, plus a unique
`(application, revision_number)` constraint. Its docstring promises the approval
review payload "diffs a newer revision against the cycle-1 baseline to show
'changes since your decision'".

None of that happens:

1. `save()` (`:389-390`) raises `ValueError` **unconditionally** — it blocks
   *creation*, not just mutation. The model can never be written.
2. Nothing writes it. `grep -rn ApplicationRevision backend/` returns only the
   definition and its two guards.
3. It has no QuerySet guard, so bulk rewrite would be possible even after (1).

The consequence is a live historical-integrity breach. `rules_snapshot` is a
single mutable JSON column **overwritten in place** on every resubmission
(`resubmission.py:103`), and `finalise.py:57-62` reads whatever snapshot is
current. So the rules context the approver saw at cycle 1 is destroyed the
moment the employee resubmits — §14 holds only for the most recent cycle. Unit
24 freezes one revision per cycle.

### 1.4 Verified already-correct — no change needed

* **Workflow history.** `ApplicationStage` (`workflows/models.py:247+`)
  materializes the chain at first submission (`role`, `role_label`,
  `assigned_approver`, `stage_order`) and carries **no FK to `Workflow`** — the
  `workflow` FK at line 76 belongs to `WorkflowStage`, the template model. An HR
  edit to a `Workflow` therefore cannot rewrite an existing application's chain.
  Resubmission keeps the chain and increments `decision_version` in place
  (stages stay at the chain-creation cycle; the application counter advances).
  Goal 2's workflow half is satisfied by design.
* **Rules context, current cycle.** `build_rules_snapshot`
  (`submission.py:183-236`) already freezes leave-type parameters, eligibility
  rules, financial year, holidays in range, working/calendar days, and the
  balance projection.

---

## 2. Decisions (D1–D10)

* **D1 — Unit 24 hardens; it does not re-wire.** Goal 1's twelve call sites stay
  as they are. No new `Action` or `TargetType` members, no refactor of the audit
  call sites, no new endpoints.
* **D2 — `AuditEntry` becomes append-only at the ORM layer**, mirroring
  `ApprovalDecision` exactly: an `AuditEntryLockedError`, an
  `AuditEntryQuerySet` rejecting `update()`/`delete()`, an
  `AuditEntryManager` from that QuerySet, an instance `delete()` that always
  raises, and an instance `save()` that raises unless `_state.adding`.
* **D3 — Enforce at instance *and* queryset level.** Instance guards alone leave
  `AuditEntry.objects.filter(...).update(...)` wide open, which is the exact
  vector the code standard forbids.
* **D4 — Rework the ordering test; do not weaken the guard.** No test-only
  backdoor, no `Meta` escape hatch. `test_ordering_is_newest_first` asserts
  natural descending order instead of backdating via bulk update.
* **D5 — Revive `ApplicationRevision` as the per-cycle history record.** Fix
  `save()` to permit creation and reject mutation (same `_state.adding` rule);
  add `ApplicationRevisionLockedError` + `ApplicationRevisionQuerySet` +
  `ApplicationRevisionManager`; keep the unconditional `delete()` guard. Still
  no migration (manager only, no field changes).
* **D6 — Exactly one revision per successful submit/resubmit**, written inside
  the existing `transaction.atomic()` block alongside the snapshot write and the
  `record_audit` call (`submission.py:106-140`, `resubmission.py:103-124`), so a
  failed revision write rolls back the application, the snapshot, and the audit
  entry together.
* **D7 — Revision content uses the existing columns; no schema additions.**
  `revision_number = application.submission_cycle`; the approver-facing fields
  copied from the application being submitted; `documents` = the attachments at
  that cycle; `changes` = `changed_fields(previous cycle, current cycle)` on
  resubmission and `None` on first submission.
* **D8 — `finalise.py` keeps reading `rules_snapshot` as-is.** The current
  cycle's snapshot remains the operative input for finalisation. Revisions are
  preserved history, never an override — so Unit 24 cannot alter deduction
  arithmetic.
* **D9 — No API surface change.** Revisions are written and preserved but not
  exposed over a new endpoint or added to an existing serializer in this unit.
  "Changes since your decision" stays a Unit 17 follow-up; if the developer
  wants it surfaced, that is an explicit scope addition at approval time.
* **D10 — Explicitly out of scope.** Recon surfaced the following genuine
  defects, all owned by earlier units and **not** absorbed here (per the
  "smallest change that completely satisfies the current specification" rule):
  the edit/resubmit API + frontend contract break (ordinary PATCH rejected on
  non-draft applications while the frontend links to a read-only edit page; the
  frontend `LeaveApplication.status` type lists only `draft | submitted`) —
  Units 17/19/20; final-approval/deduction and cancellation-restoration pairing
  — Units 18/23; audit-JSON serialization of a `CombinedExpression` on
  resubmission — Unit 17; unenforced `row_version` — Unit 17.

---

## 3. Deliverables (when approved — Phase 2)

* `backend/audit/models.py`: `AuditEntryLockedError`, `AuditEntryQuerySet`,
  `AuditEntryManager`, instance `save()`/`delete()` guards. **No migration.**
* `backend/leave/models.py`: `ApplicationRevisionLockedError`,
  `ApplicationRevisionQuerySet`, `ApplicationRevisionManager`, fixed `save()`
  (creation allowed, mutation rejected), retained `delete()` guard. **No
  migration.**
* `backend/leave/services/submission.py`: write the cycle-1 revision in the
  submit transaction, after the snapshot and before/with the audit entry.
* `backend/leave/services/resubmission.py`: write the cycle-N revision with the
  `changed_fields` diff, in the same transaction.
* `backend/audit/tests.py`: immutability tests (instance save, instance delete,
  queryset `update`, queryset `delete`) and the reworked ordering test.
* `backend/leave/tests/test_resubmission.py` (+ the submission test module):
  revision written on submit; revision written per resubmission cycle with the
  diff; atomicity — a failed revision write leaves no application change, no
  snapshot, and no audit entry.
* `context/progress-tracker.md`: mark Unit 24 complete; set Next Up to Unit 25
  (End-to-End System).

**Verification result:** `uv run manage.py check` clean;
`uv run manage.py makemigrations --check --dry-run` clean (both deliverables are
manager-only, as predicted); full `uv run manage.py test --noinput` → **651
tests OK** (636 before + 15 new). The run's trailing `destroy_test_db`
`OperationalError` is the known test-database teardown/lock issue in this
environment and occurs *after* every test passes; it is unrelated to this unit.

**Awaiting developer sign-off before commit.**
