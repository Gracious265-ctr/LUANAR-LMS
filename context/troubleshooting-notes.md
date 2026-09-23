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