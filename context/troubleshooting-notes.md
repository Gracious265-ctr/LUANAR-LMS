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