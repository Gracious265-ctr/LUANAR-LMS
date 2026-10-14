# Unit 25 — End-to-End System (Detailed Design)

**Scope:** prove the complete LUANAR leave-management journey works end to end,
and fix the wiring-level breaks that stop it completing.
**Status:** Phase 1 — spec drafted; **do not begin Phase 2 (implementation) until
the developer approves.**

**Developer decisions taken at Phase 1 (2026-09-25):**
1. Unit 25 = the E2E journey test **plus the wiring fixes**. Unit 23's
   unbuilt approved-document half is **split out into its own unit** ("23b"), with
   its own spec.
2. **No new third-party dependency** may be added in this unit. `reportlab` in
   particular requires a fresh approval and belongs to 23b.

---

## 1. Context recap

The build plan's Unit 25 (`context/specs/luanar-build-plan.md:858-905`) asks us
to verify and finish this journey, then verify six side paths:

```text
HR creates employee → assigns grade → configures leave rules → configures
workflow → employee logs in → creates application → system validates →
reference number generated → supervisor receives → supervisor approves →
next approver receives → all mandatory stages approve → final approver approves
→ annual balance updated → approved document generated → emails sent →
employee views approved leave → HR sees finalized record
```

Side paths: **rejection, correction, resubmission, cancellation, delegation,
reassignment**.

Unit 25 is the first unit whose job is *acceptance*: every other unit tested its
own slice in isolation. Phase-1 verification against the real code found that
several slices were never actually connected to each other, so the composed
journey does not run. This unit writes the composed test first, then closes the
gaps it exposes.

---

## 2. What Phase 1 verified

### 2.1 Confirmed breaks — in scope

**B1 — Final approval never records the annual-balance deduction.**
`leave/services/finalise.py` has **zero callers**: `record_deduction` and
`consume_deduction_decision` are never invoked from `decide()`
(`workflows/services.py`). On final approval `decide()` only sets
`app.status = APPROVED` (`:805-806`). So the journey's "annual balance updated"
step never happens. Unit 23's existing
`test_full_approval_chain_finalises` only asserts the status, never a ledger
row, which is why this was invisible.

**B1b — the deduction is not actually idempotent.** `record_deduction`'s
docstring states the partial unique constraint `(application, type='deduction')`
makes the write "idempotent and race-safe". That constraint **does not exist**:
`LeaveBalanceTransaction.Meta.constraints` (`leave/cancellations/models.py`)
contains only `balance_transaction_days_gt_0` and
`one_restoration_per_cancellation`. `get_or_create` is therefore not
DB-guaranteed for deductions.

**B2 — rejection and correction emit the wrong event kind.**
`workflows/services.py:869-872` reads:

```python
kind=(
    APPLICATION_FINALISED
    if after_status != LeaveApplication.Status.SUBMITTED
    else DECISION_RECORDED
)
```

`REJECTED` and `CORRECTION_REQUIRED` are both `!= SUBMITTED`, so **a rejection
emits `application_finalised`**. Proven with a throwaway test: a rejection
produced `['application_finalised']`. Consequences: the Unit 22 outbox row is
filed under the wrong `kind`, and `_decision_recipients`
(`notifications/services.py:67`) treats the rejecting approver as a finaliser and
CCs them on a rejection email. The notification tests build events *directly*
(`notifications/tests.py:73`) rather than through `decide()`, so nothing caught it.

**B3 — HR cannot see the finalised record.** `FinalizedLeaveViewSet.get_queryset`
(`audit/views.py:70-71`) filters `status=LeaveApplication.Status.SUBMITTED`, and
`get_object` (`:84-85`) 404s anything else. An **approved** application is
therefore invisible to HR, so the journey's last step fails. (The frontend
surface exists — `hr-admin/audit/` with `finalized-leave-table.test.tsx` — it
just receives an empty approved set.)

**B4 — a correction cannot be acted on, so correction→resubmit cannot complete.**
`LeaveApplicationViewSet.update` / `partial_update` (`leave/views/__init__.py`
`:222-237`) reject **any** non-draft status with 400 "Submitted applications
cannot be edited." So an application returned for correction cannot be edited,
which makes the side path pointless. This is a **contract break**: the frontend
already assumes it is editable —
`frontend/components/leave/LeaveApplicationForm.tsx:249` sets
`editable={... || status === "correction_required"}` and `:250`
`canReplace={status === "correction_required"}`, and
`READ_ONLY_STATUSES` (`:20`) deliberately omits `correction_required`. The form
allows the edit and PATCHes it; the backend 400s.

**B5 — frontend status union is incomplete.**
`frontend/lib/leave-api.ts:22` declares `status: "draft" | "submitted"`, but the
API returns six statuses. This is latent rather than breaking today, because
`LeaveApplicationForm` keeps its own `useState<string | null>` (`:31`) and so
bypasses the union — which is also why `typecheck:test` currently passes.

### 2.2 Claims investigated and disproven — do **not** "fix" these

* **"Resubmission crashes serializing a `CombinedExpression` into audit JSON."**
  False. `resubmission.py:97` does use `F("decision_version") + 1`, but Django
  6.1 refreshes expression-backed attributes after save (psycopg3 `RETURNING`),
  so `stage.decision_version` is a plain `int` by the time `record_audit` reads
  it. Verified: the audit detail `json.dumps` cleanly and carries
  `decision_version == 3` (1 → 2 on reject → 3 on resubmit). A passing regression
  test now pins this
  (`leave/tests/test_resubmission.py::test_resubmission_audit_detail_is_json_safe`).
* **"Cancellation can record a restoration with no matching deduction."** False.
  `_restore_balance` (`leave/cancellations/services.py:571-575`) calls
  `provider.get_deduction(application)` and returns early when it is `None`.
  Today it always no-ops (because B1 means no deduction ever exists); once B1 is
  fixed it restores correctly. No change needed.

### 2.3 Already correct — verified, no change

* All twelve operations write audit entries from inside the owning transaction,
  and `AuditEntry` / `ApplicationRevision` are now genuinely append-only (Unit 24).
* `ApplicationStage` materializes the approval chain with no FK to `Workflow`, so
  HR config edits cannot rewrite a submitted application's history.
* `record_deduction` / `consume_deduction_decision` logic is sound and reads the
  frozen `rules_snapshot`, so it agrees with Unit 18's restoration gate.
* The frontend is substantially built out (40+ routes, 50 test files) and its
  contract *intends* `correction_required` to be editable (B4).

---

## 3. Decisions (D1–D11)

* **D1 — The E2E test is the deliverable; the fixes serve it.** Write one
  composed journey test first, let it expose the breaks, then close them. No
  speculative refactoring of working code.
* **D2 — Wire `record_deduction` only; never `finalise_approved_application`.**
  The latter imports `documents.models.ApprovedLeaveDocument` and
  `documents.services.enqueue_approved_document_render`, **neither of which
  exists** — calling it raises `ImportError`. Unit 25 touches the balance half
  only; the document half is 23b. The unused import surface is left exactly as
  it is.
* **D3 — Add the missing `one_deduction_per_application` constraint.** A partial
  `UniqueConstraint(fields=["application"], condition=Q(type="deduction"))` on
  `LeaveBalanceTransaction`, so the idempotency `record_deduction` already
  promises is enforced by the database rather than by `get_or_create` luck.
  Requires **one migration**. This is the only schema change in the unit.
* **D4 — Balance is transactional.** The deduction runs inside `decide()`'s
  existing `transaction.atomic()`, so a deduction failure rolls the approval
  back. (23b's document render is a retryable derived artifact and will *not* be
  transactional — that asymmetry is the Unit 23 D5 rule, preserved.)
* **D5 — Fix the event kind to key off approval.** The condition becomes
  `after_status == LeaveApplication.Status.APPROVED`. Rejection, correction, and
  mid-chain approval all correctly emit `DECISION_RECORDED`.
* **D6 — HR's finalized view covers in-flight and approved.**
  `FinalizedLeaveViewSet` filters `status__in=[SUBMITTED, APPROVED]` in both
  `get_queryset` and `get_object`. Rejected/cancelled history is left to the
  audit log, which already records it (Unit 24 D1) — this keeps the change
  minimal rather than turning the view into a full status archive.
* **D7 — Editable statuses are DRAFT and CORRECTION_REQUIRED only.** Both
  `update` and `partial_update` allow those two and keep the 400 for every other
  status (SUBMITTED, APPROVED, REJECTED, CANCELLED). Editing a
  correction-required application leaves its status alone; the employee then
  calls `resubmit`, which re-validates, bumps `submission_cycle` and writes the
  new revision row (Unit 24). This is the minimum that makes the side path real.
* **D8 — Widen the frontend union, change no behaviour.**
  `LeaveApplication.status` becomes
  `"draft" | "submitted" | "approved" | "rejected" | "correction_required" | "cancelled"`,
  matching `LeaveApplication.Status`. Verified low-risk: the three consumers
  (`leave-validation.ts:127`, `SubmittedClient.tsx:22`, `DraftsList.tsx:12`) all
  compare against members of the widened set.
* **D9 — New cross-app test package.** The journey spans leave, workflows, audit
  and notifications, so it does not belong to any one app. Add
  `backend/tests/__init__.py` + `backend/tests/test_end_to_end.py` rather than
  overloading a per-app `tests/`.
* **D10 — The E2E test drives real services, not HTTP.** It calls
  `submit_application` → `decide` (per stage) → `resubmit_application` →
  cancellation/delegation/reassignment services, on the stub provider's role
  spine, exactly as the Unit 15/17/21 tests do. A thin API-level pass/fail check
  is added only where the journey's *contract* is the thing under test (the HR
  finalized view).
* **D11 — Explicitly out of scope.** The approved-document build (model,
  `reportlab`, render task, `approved/{id}/` storage prefix, signed-URL
  endpoints, frontend viewer) → **Unit 23b**. Also out: `row_version` optimistic
  concurrency enforcement (pre-existing, and no new risk is introduced because
  drafts are already editable without it), carry-forward, document invalidation
  on later cancellation, and DOCX.

---

## 4. Deliverables (when approved — Phase 2)

* `backend/tests/__init__.py`, `backend/tests/test_end_to_end.py` — the composed
  journey: HR config → employee submit → full multi-stage approval → **balance
  deducted exactly once** → emails sent → employee sees approved leave → **HR sees
  the finalised record**. Plus one scenario each for rejection, correction,
  resubmission (asserting the cycle-2 revision and that cycle 1 is untouched),
  cancellation (asserting the restoration now matches the deduction), delegation
  and reassignment.
* `backend/workflows/services.py` — call `record_deduction` inside the final-stage
  approval (D4); fix the event-kind condition (D5).
* `backend/leave/cancellations/models.py` +
  `backend/leave/cancellations/migrations/00XX_one_deduction_per_application.py`
  — the missing partial unique constraint (D3).
* `backend/leave/views/__init__.py` — allow edit on DRAFT and
  CORRECTION_REQUIRED (D7).
* `backend/audit/views.py` — `status__in=[SUBMITTED, APPROVED]` (D6).
* `frontend/lib/leave-api.ts` — widen the status union (D8).
* Tests: rejection emits `DECISION_RECORDED` (the probe test proven in Phase 1
  and then reverted); correction emits `DECISION_RECORDED`; final approval emits
  `APPLICATION_FINALISED` **and** writes exactly one deduction; a second
  finalisation attempt does not double-deduct; the HR view lists an approved
  application; PATCH succeeds on `correction_required` and still 400s on
  `submitted`/`approved`.
* `context/progress-tracker.md` — mark Unit 25 complete, record the Unit 23b
  split, and set Next Up accordingly.

**Verification gates:** backend `uv run manage.py check`;
`uv run manage.py makemigrations --check --dry-run` (must now be *clean after*
the one intentional migration is generated); full `uv run manage.py test --noinput`
with the known `DROP DATABASE IF EXISTS test_luanar_leave WITH (FORCE)`
workaround chained in; frontend `npm test` and `npm run typecheck:test` and
`npm run lint` (the D8 type change touches a checked file).

**Awaiting developer approval before Phase 2 begins (per §20 discipline).**
