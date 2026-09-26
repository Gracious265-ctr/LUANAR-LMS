# Troubleshooting Notes

Standing rule (see `context/AGENTS.md`): every error, bug, or debugging
session encountered in this repo — in any session — must be recorded here
before moving on, in a new section in the same shape as the existing ones.
Check this file first when a failure resembles one already documented.

How to diagnose and fix recurring failures in the LUANAR-LMS codebase.
Add a new section for each distinct root cause you hit, in the same format,
so the next person (human or agent) recognizes it immediately.

General playbook for any test error:

1. **Classify the result marker.**
   - `F` = failed assertion — your logic produced a wrong value. Fix the code
     or the test.
   - `E` = error — an exception was raised (often in `setUp`, not the test body).
   - For `E`, read the LAST frames of the traceback first, then the FIRST
     frames that name a project file (e.g. `workflows/tests_approvals.py`,
     `backend/leave/...`). Framework/site-packages frames are usually noise.
2. **Decide: code bug or environment bug?**
   - Errors during plain inserts in `setUp`, lock/deadlock/`already exists`
     DB errors, or timeouts are usually **environment/concurrency** problems.
   - Assertion failures and exceptions raised in the test body itself are
     usually **real code bugs**.
3. **Check for concurrent test runners.** Never run two Django test suites
   against the same test database at the same time.
   ```sh
   pgrep -af "manage.py test"
   ```
   More than one process → kill the extras (`pkill -f "manage.py test"`).
4. **Reset the disposable test DB** if it is stale or was left behind by a
   killed run:
   ```sh
   PGPASSWORD=luanar psql -h localhost -U luanar -d postgres \
     -c "DROP DATABASE IF EXISTS test_luanar_leave;"
   ```
   Only ever target the `test_` database — never production data.
5. **Re-run one test first** (fast loop), then the full suite:
   ```sh
   uv run manage.py test workflows.tests_approvals.ApprovalApiTests.test_that_errored --noinput
   ```
6. **Confirmation of green:** the final lines read `Ran N tests` then `OK`
   (resolves as `FAILED (failures=N)` / `FAILED (errors=N)` otherwise).

---

## Seed approval command: zombie weekend windows (calendar-offset time bomb)

### Symptom
`workflows.tests_approvals.SeedApprovalsDevTests.test_seed_command_runs_idempotently`
and `workflows.tests_seed_cancellations.SeedCancellationsTest.setUpClass` ERROR
with `ValidationFailedError` from `submit_application` inside
`seed_approvals_dev`, on the pristine base (no local changes). Errors:
`start_date: A weekend (Saturday) cannot be the first day of leave.` +
`end_date: This date range contains no working days.` Reproduced on the
`workflows` suite before any unit-22 edit — genuinely pre-existing.

### Root cause
`seed_approvals_dev._cancellation_scenarios` computes the demo windows from
fixed day-offsets off `timezone.localdate()` with no weekend guard. The
single-day `starts(8, 0)` "cancellation_approved_tomorrow" demo opened on a
Saturday whenever today is Friday (+8d). Submission validation rejects a
weekend start, so the whole set-up-command fails. The windows also had no
mutual-non-overlap guarantee, so on other anchors (Mon/Tue/Wed) two offsets
could collide/start on a weekend.

### What to look for
- Full-suite failures that appear "random" by calendar but reproduce in
  isolation, on a branch with no related changes.
- Errors naming `A weekend (...) cannot be the first day of leave` originating
  from a seed/data command, not from a user test body.
- Scenarios built as `today + timedelta(days=offset)` with hard-coded offsets
  (no `is_weekend` check) feeding a submission that validates working-days.

### Fix
In `_cancellation_scenarios`: a window whose start would be a weekend is
pushed to the next working day and nudged past any window already claimed for
the same employee (`claimed[employee]`); the `today+14` (approved-14d) and
academic `today+12` (academic-10d) windows asserted verbatim by
`workflows/tests_seed_cancellations.py` are returned exactly as computed.
Brute-forced all 7 anchor weekdays — green except the pinned-offset anchors
that were already invalid under the old code. Uses
`leave.validation.working_days.is_weekend` (local import, matching the file's
style).

**Follow-up (2026-09-26, exposed by the unit-23 rebase):** the pinned
`today+14` / academic `today+12` windows were themselves still a time bomb —
on a **Saturday/Sunday anchor** they land on a weekend and the seed dies at
`starts(14)` (`cancellation_approved_14d`). The first fix only weekended
the *unpinned* offsets. Now `starts()` weekend-shifts the pinned windows too
and `workflows/tests_seed_cancellations.py` asserts the same shifted dates via
a `_pinned_start(offset)` helper, so all 7 anchor weekdays finally pass.

---

## Unit 23: `fixture_balance.get_deduction` ignored the stub (import-time binding)

### Symptom
`leave.tests.test_cancellation.EligibilityTests.test_approved_future_returns_request`
failed only when `documents.tests_approved_document` ran **before** it in the
same process (`estimated_restoration_days` 0 != 5); green in isolation and
green in the reverse order. Full suite failed at exactly that pair boundary.

### Root cause
`leave/cancellations/fixture_balance.py` did `from ..providers import
get_provider` at module-import time. `StubProviderMixin.use_stub()` patches the
module attribute `leave.providers.get_provider`, which does **not** rebind a
name already imported into another module. Whether `get_deduction` saw the
stub or the real `DatabaseRulesProvider` therefore depended on *when*
`leave.cancellations.fixture_balance` was first imported in the process. Unit-23
added `documents.tests_approved_document` (first-ever importer of
`fixture_balance` before the cancellation suite), flipping the binding to the
real provider, whose `get_leave_type_rules` returned `None` for the untested
DB → `get_deduction` → `None` → estimate 0.

### What to look for
- A test pair whose pass/fail flips with ordering but both pass individually.
- `from X import y` where a mixin patches `X.y`: patch the call site, not the
  origin, or call through the module (`import X; X.y()`).

### Fix
`fixture_balance.py` now resolves the provider through the module at call time
(`from .. import providers` + `providers.get_provider()`), so
`use_stub()`'s patch of `leave.providers.get_provider` applies regardless of
import order. Full suite 708 OK, both orders green.

---

## Django 6.1: `captureOnCommitCallbacks` is now a classmethod

### Symptom
Unit 22 tests failed to import:
`ImportError: cannot import name 'captureOnCommitCallbacks' from
'django.test.utils'` — and the same from `django.test`. (Django 6.1.1.)

### Root cause
`captureOnCommitCallbacks` stopped being a module-level context manager;
it is now `django.test.testcases.TransactionTestCase.captureOnCommitCallbacks`
(a classmethod usable as `self.captureOnCommitCallbacks(execute=True)` on any
`TestCase`). It is not re-exported from `django.test`/`django.test.utils`.

### What to look for
- `from django.test.utils import captureOnCommitCallbacks` raising ImportError
  when the code targets a fresh Django ≥ 6.1 test suite.
- `TransactionTestCase` subclasses that need `transaction.on_commit` to fire
  by hand.

### Fix
Call it on `self` instead of importing it:
`with self.captureOnCommitCallbacks(execute=True):` (drop the import).

---

## psycopg.errors.DeadlockDetected

### Symptom
A test aborts with `E` and a traceback ending in:

```
psycopg.errors.DeadlockDetected: deadlock detected
DETAIL:  Process 26460 waits for ShareLock on transaction 22714; blocked by process 27065.
Process 27065 waits for ShareLock on transaction 22708; blocked by process 26460.
CONTEXT:  while inserting index tuple (0,4) in relation "users_user_username_key"
```

Often fired from a plain `User.objects.create_user(...)` in `setUp`,
ending in `django.db.utils.OperationalError`.

### Root cause
Two `manage.py test` processes ran against the **same test database**
(`test_luanar_leave`) at the same time. Each inserted rows holding
unique-index locks; each then needed a lock the other held, so PostgreSQL
killed one transaction (the trigger that raised the error is the *innocent
victim*, not the actual offense). Common sources of a second runner:

- a backgrounded/detached run that is still alive when a new run starts,
- running the suite in two shells or via two agents at once,
- a run interrupted by a tool/terminal that left the process orphaned.

### What to look for
- Missing `F`s but one `E` in `setUp` — assertions never even ran.
- The unique-index insert (`users_user_username_key`, `..._email_key`, …)
  as the deadlocked statement — classic multi-writer collision, not a schema bug.
- `pgrep -af "manage.py test"` showing two or more processes.

### Fix
1. Confirm no other runs are alive, and no locks remain:
   ```sh
   pgrep -af "manage.py test" || true
   PGPASSWORD=luanar psql -h localhost -U luanar -d postgres -tAc \
     "SELECT pid FROM pg_stat_activity WHERE datname='test_luanar_leave' AND state<>'idle';"
   ```
2. If a stray runner exists: `pkill -f "manage.py test"`.
3. Drop the leftover test DB and run the suite once, single process:
   ```sh
   PGPASSWORD=luanar psql -h localhost -U luanar -d postgres \
     -c "DROP DATABASE IF EXISTS test_luanar_leave;"
   uv run manage.py test workflows.tests_approvals --noinput
   ```
4. Success = `Ran 51 tests` then `OK`. The deadlock does not indicate any
   product-code change is required.

---

## RTL: step-2 content of a dialog "not found" after clicking Continue

### Symptom
New Vitest tests for `CancelApplicationDialog` failed with
`Unable to find an accessible element with the role "button" and name
"Submit cancellation request"` — the step-2 confirm button — even though the
reason text asserted via `await findByText(...)` was present. Vitest and the
test itself passed debug reproductions where a `setTimeout` was added.

### Root cause
The tests clicked buttons with a raw DOM method:
`dialog.getByRole("button", {...}).click()`. RTL's `fireEvent` (and
`userEvent`) wrap dispatches in `act()`, so React flushes the resulting
state update synchronously. A raw `.click()` does **not** — React 18 batches
the update, and a *synchronous* `getByRole` immediately after it runs against
the pre-render DOM (the step-2 button is absent). `findBy*`/`waitFor` flush
React, which is why text-based asserts still passed; the famous
`An update to ... was not wrapped in act(...)` warnings accompany this.

This also applies to setting React-controlled input values: `setAttribute(...)`
+ `dispatchEvent(new Event("input"))` does not update a controlled component
(React reads the value-tracker property, not the attribute); `fireEvent.change`
does.

### What to look for
- `act(...)` warnings in test stderr followed by "not found" for content that
  logically must be rendered.
- Direct `.click()` on query results, or `setAttribute`+`dispatchEvent` input
  mutation, instead of `fireEvent.click(...)` / `fireEvent.change(...)`.
- Same flow passes with an added `await waitFor(...)`/`setTimeout`.

### Fix
Always interact through RTL events:
```ts
fireEvent.change(textarea, { target: { value: "reason" } });
fireEvent.click(continueBtn);
expect(await screen.findByRole("button", { name: "Submit ..." })).toBeInTheDocument();
```

---

## React controlled inputs: SetAttribute+dispatchEvent leaves the value empty

### Symptom
Unit 18 dialog/panel tests typed into textareas via
`textarea.setAttribute("value", x); textarea.dispatchEvent(new Event("input"))`
and the live character counter stayed `0/1000`, the Continue button stayed
disabled, and submitted payloads were missing the comment/reason.

### Root cause
For a React *controlled* input, the input's value lives in React state driven
by the value tracker that React installs on the DOM node — not in the
`value` attribute. Setting the attribute neither changes `.value` nor
satisfies the tracker, so React's `onChange` reads the unchanged value.

### What to look for
- Tests that "work" in other frameworks or with uncontrolled inputs.
- `toHaveValue` / counter / button-disabled assertions failing while the DOM
  attribute visibly holds the typed text.

### Fix
Use RTL's `fireEvent.change(element, { target: { value: "..." } })` (or
`userEvent.type`), which simulates a real user change and updates controlled
state.

---

## Unit 18 decision panel: 403 read-only message was dead code

### Symptom
When `submitCancellationDecision` returned `403 not_current_approver`, the
component set `readOnly = true` but the whole "Decision" panel disappeared,
so the intended "You are viewing this cancellation request in read-only mode
..." guidance never rendered. A test asserting it failed.

### Root cause
The Decision panel rendered only when `canAct || (decided && myDecision)`.
After a 403 the request is still *pending* (`decided === false`), so both
terms were false and nothing rendered. The read-only branch was unreachable:
`(decided && myDecision)` implies `myDecision` is set, and the read-only
message only shows when `myDecision` is falsy.

### What to look for
- A conditional `canAct || (decided && myDecision)` that hides its own
  `else` (read-only/blocked) branch whenever the status is still pending.
- A 403 handler that sets a flag but no visible state change follows.

### Fix
Include the `readOnly` flag itself in the render predicate:
`(canAct || (decided && myDecision) || readOnly)` so the read-only message
shows when the viewer is locked out.

---

## Unit 18 dialog: action_changed did not trigger the parent refetch

### Symptom
The `action_changed` handler surfaced "The application changed since you
opened this dialog." and a "Refreshing to the latest application state…"
banner, but the parent tracking page never re-fetched — the stale button/
eligibility state persisted on reopen. A test asserting `onSuccess` was
called failed.

### Root cause
`handleSubmitError`'s `action_changed` branch returned `true` without calling
`onSuccess`, so the parent never refetched the live tracking payload even
though the dialog claimed it was refreshing.

### What to look for
- A "refreshing to the latest state" message with no corresponding
  refetch/`onSuccess` invocation in the same code path.
- An error path that shows a recovery message but doesn't wire the screen
  refresh the message promises.

### Fix
Call `onSuccess()` from the `action_changed` branch (the dialog's reset/
refetch contract) while keeping the inline message and refreshing note so the
employee sees why their state changed.

---

## Unit 20 provider swap: workflows seed/approval tests failed against the real provider

### Symptom
After flipping `LEAVE_RULES_PROVIDER` to `DatabaseRulesProvider`:
1. `workflows.tests_approvals.SeedApprovalsDevTests.test_seed_command_runs_idempotently`
   — ERROR `ValidationFailedError: 1 validation error(s)` raised from
   `submit_application` inside `seed_approvals_dev`.
2. `workflows.tests_seed_cancellations.SeedCancellationsTest.setUpClass` —
   ERROR, same root cause.
3. `workflows.tests_approvals.ApprovalApiTests.test_detail_renders_full_review_payload`
   — FAIL: expected entitlement/used/available 24/0/24, got 0/0/0.

### Root cause
The approvals dev seed had always run against the placeholder fixture
provider, which short-circuited validation; the real provider validates
against real rows that don't exist in a bare test DB (no `FinancialYear`, no
`LeaveRule`s, no `GradeEntitlement`s — so balance resolves to 0) and it
enforces gender eligibility (the maternity scenario needed a female employee).
Two independent traps:
- **Import-site patching:** `StubProviderMixin.use_stub()` patches
  `leave.providers.get_provider`, but `workflows.approvals_serializers`
  does `from leave.providers import get_provider` at import time, so its
  `_balance()` kept calling the *real* provider for the review payload while
  validation used the stub.
- **Fixture-id coupling:** `seed_approvals_dev._leave_type_id` resolved leave
  types through `fixture_data.LEAVE_TYPES` ids (1–4), which no longer map to
  real rows.

### What to look for
- `Functions/binaries` approval payloads that changed when the default
  provider swapped — check the import site of `get_provider` vs where the test
  patches it (patch the consumer module, e.g.
  `workflows.approvals_serializers.get_provider`, not just `leave.providers`).
- Seed commands that create applications without first ensuring the
  validation-time HR config (financial year, leave types + effective rules,
  entitlements, employee gender) exists in the target DB.

### Fix
- Added shared idempotent defaults `leave/defaults.py`
  (`ensure_default_entitlements`, `ensure_default_leave_types_and_rules`,
  `ensure_default_financial_year`), called by both `seed_dev_users` and
  `seed_approvals_dev`; the approvals seed now also sets employee/approver
  gender and resolves leave types from the DB by name (no fixture ids).
- Added `workflows.approvals_serializers.get_provider` to
  `StubProviderMixin.use_stub()` so approvals (which use the injected stub)
  render stub-consistent balances.

---

## Unit 24: Django admin inline formsets are defensive by default (`get_formset`, `DeleteProtectedModelForm`)

### Symptom
`test_workflow_inline_stage_creation_records_event` first raised
`inlineformset_factory() got an unexpected keyword argument 'change'`, then —
after dropping the kwarg — silently saved **zero** stages: `formset.is_valid()`
was True, the single extra form had non-empty `changed_data`, but
`formset.save(commit=False)` returned `[]` with no audit event.

### Root cause
1. `InlineModelAdmin.get_formset(self, request, obj=None, **kwargs)` forwards
   **all** kwargs to `inlineformset_factory`; there is no `change=` kwarg, and
   `obj` is passed positionally.
2. The returned form class is Django's `DeleteProtectedModelForm`, whose
   `has_changed()` returns `False` for a new inline row when the acting user
   lacks the inline model's add permission (`can_add`):
   ```python
   def has_changed(self):
       if not can_add and self.instance._state.adding:
           return False
       return super().has_changed()
   ```
   `save_new_objects` skips every "unchanged" extra form, so nothing persists.
   The plain `make_user()` fixture user has no Django object permissions.

### What to look for
- `is_valid()` True + `errors`/`non_form_errors` empty but `save()` creates
  nothing → check `form.has_changed()` vs `form.changed_data` on the real
  (wrapped) form class — introspection of the MRO shows
  `DeleteProtectedModelForm`.
- The inline formset prefix is the **parent FK related_name**
  (`WorkflowStage.workflow` uses `related_name="stages"` → prefix `stages`),
  not `workflowstage_set`.

### Fix
Grant the acting user the add permission before exercising the formset
(`self.hr.user_permissions.add(Permission.objects.get(codename="add_workflowstage"))`),
drive the formset with the `stages-*` management prefix, and call
`inline.get_formset(request, obj=workflow)` without a `change` kwarg. The
`AuditedModelAdmin.save_formset` mixin then records
`workflows.workflowstage.created` with the created instance as target.

---

## Unit 24: reassignment timeline summary empty when users have no full names

### Symptom
`HistoricalIntegrityTests.test_reassignment_updates_spine_but_not_stage_snapshot`
failed with `'' != 'Reassigned to dean@test.luanar'`: the reassigned event had
kind `reassignment` but `summary` was `""` and `metadata` had **no**
`before`/`after` keys.

### Root cause
`reassign_application` calls `record_config_change(..., before={..., "current_approver": ""}, after={..., "current_approver": to_approver.get_full_name()})`.
`make_user`/`make_approver_chain` never set `first_name`/`last_name`, so
`get_full_name()` returns `""` and **both** sides of the diff are identical →
`changed_fields` emits an empty diff → the `before`/`after` metadata is never
stored, and `_timeline_summary` (which builds the human sentence from that
metadata) returns `""`. (Incidentally, `AuditEvent` targets are GenericFKs —
no DB FK cascade — so the trail **survives** target deletion; the "parent
delete purges events" test expectation was simply wrong.)

### What to look for
- A diff-based `record_config_change` event whose metadata lacks
  before/after even though semantically something changed (both values stringify
  equal, e.g. `""`).
- Tests asserting on `get_full_name()` should give fixture users names; expect
  empty diffs whenever stub users have no first/last names.

### Fix
Name the approver-chain users in the Unit 24 fixtures (`first_name`/`last_name`
saved per user) before asserting `"Reassigned to {full_name}"`, and assert the
cascade test now expects the events to **survive** `app.delete()`.

---