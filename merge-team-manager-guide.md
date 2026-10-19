# Merging the `feature/team-manager` apps into your branch

**Audience.** A developer building a separate part of the system on their own
branch, who now needs the **documents**, **organisation**, **teams/workflows**,
and **approvals** features from `origin/feature/team-manager` so the whole system
works together.

**What "the apps" means here.** Four Django apps plus their frontend screens:

| Feature you asked for | Backend Django app(s) | Frontend |
|---|---|---|
| Documents | `documents` | `/documents/**`, `components/documents/`, `lib/documents/` |
| Organisation | `organisation` | `/organisation/**` (campuses, roles, approvers) |
| Teams (units) | `workflows` (models `Team`‑related `Section`, `Workflow`, `SectionMember`, `WorkflowMember`) | `/organisation/teams/**` |
| Approvals | `approvals` (+ `workflows` policies/providers) | `/approvals/**`, plus plan approvals under `/dashboard/plans/approvals/**` |

> There is **no** `teams` Django app. "Teams" live in the `workflows` app and
> are administered from the frontend `/organisation/teams/**` routes.

This guide is **branch-agnostic**: Step 0 tells you which of the three common
base situations you are in and what that changes.

---

## §1 — TL;DR

```bash
# 0. Figure out your base (see Step 0) and read the change list first.
git fetch origin
git diff --stat <your-base>..origin/feature/team-manager

# 1. Prepare a safety net.
git switch -c <your-branch>            # if not already on it
git switch -c backup/<your-branch>-pre-team-manager
git switch <your-branch>

# 2. Merge the whole branch (do NOT cherry-pick the four folders — see §5).
git merge origin/feature/team-manager

# 3. Resolve conflicts using the playbook in §7, then verify (§10) before pushing.
```

**Two rules that save you a day:**

1. **Never hand-merge migration files.** Take one side, then regenerate.
2. **Grep for conflict markers before you commit:**
   ```bash
   git grep -nE '^(<<<<<<<|=======|>>>>>>>)' || echo "clean"
   ```

---

## §2 — Step 0: know your base first

The instructions differ depending on what your branch already contains. Run:

```bash
git ls-tree --name-only <your-base>:backend
python manage.py showmigrations organisation approvals workflows documents
```

### Situation A — your branch has **no** `organisation`/`approvals`

Likely bases: `main`, `feature/hr-track`, or a fresh branch off them.

- On `main` both `documents` and `workflows` exist as **empty stubs**
  (`models.py` = "Create your models here.", migrations dir = `__init__.py` only),
  and `organisation`, `approvals`, `plans`, `system_admin`, `launcher` do not
  exist **at all**.
- You are **adding the whole feature set**, so a full merge (§6) is exactly
  right. Expect large additions and a few deleted stub files, not many conflicts.

### Situation B — your branch has the old **`org`** app + `approvals`

Likely base: `development`.

- `feature/team-manager` **renamed/split** development's `org` into
  **`organisation`**. After the merge you will have **both** `org` and
  `organisation` unless you clean up.
- Do this after the merge:
  1. Delete the stale `backend/org/` directory.
  2. Remove `"org"` from `INSTALLED_APPS` and ensure `"organisation"` is present.
  3. Make sure `config/urls.py` includes `organisation.urls` (not an `org` one).
  4. `git grep -n "from org\b\|import org\b\|'org'\|\"org\"" backend` and repoint
     any hits to `organisation`.
- The moved models kept their old `workflows_*` **table names** on purpose
  (§5), so no database rename is needed — just don't create a second set of
  tables.

### Situation C — your branch **already has** `organisation` + `approvals`

You are on a descendant of this line of work. You mostly need the **migration
leaf alignment** and **migration-graph reconciliation** described in §9; the
merge should be small. Run
`git merge-base --is-ancestor origin/feature/team-manager HEAD` to confirm
whether it is already contained.

---

## §3 — Step 0b: migration-leaf requirements (all situations)

`feature/team-manager`'s migrations are wired to **specific leaves** of other
apps. The receiving branch's `users`, `leave`, `notifications`, and `plans` must
be at (or reachable from) these migrations:

| App | Required leaf on `feature/team-manager` |
|---|---|
| `users` | `0012_alter_employeeprofile_team` |
| `leave` | `0021_alter_cancellationrequest_status` |
| `notifications` | `0009_alter_notificationoutbox_delegation_and_more` |
| `plans` | `0005_alter_planapprovalstage_section_ref` |
| `organisation` | `0008_convert_team_draft_to_active` |
| `approvals` | `0004_alter_applicationstage_section_ref_and_more` |
| `workflows` | `0034_workflow_effective_to_and_more` |
| `documents` | `0002_approvedleavedocument` |

If your base is **behind** these, the full merge brings the newer versions of
those apps along too (that is normal and intended). If your branch has **extra
migrations** on these apps that team-manager does not know about, resolve them
with §9 ("Your branch added a migration …").

---

## §4 — What you are merging (inventory)

### Backend apps

| App | Contents | Notes |
|---|---|---|
| `backend/organisation/` | `models.py` (`ApproverRole`, `Campus`, `Team`, `RoleAssignment`, `TeamRoleAssignment`, `CampusRoleAssignment`), `serializers.py`, `services.py`, `permissions.py`, `views.py`, `urls.py`, `migrations/0001–0008` | Split out of the old `workflows` monolith |
| `backend/approvals/` | `models.py` (`ApplicationStage`, `ApplicationStageApprover`, `ApprovalDecision`, `Delegation`, `Reassignment`), `payloads.py`, `serializers.py`, `services.py`, `views.py`, `urls.py`, `migrations/0001–0004` | Split out of the old `workflows` monolith |
| `backend/workflows/` | `models.py` (`Workflow`, `Section`, `SectionMember`, `WorkflowMember`), `providers.py`, `policies.py`, `presets.py`, `services.py`, `events.py`, `permissions.py`, `views.py`, `urls.py`, `migrations/0001–0034` | The slim "teams / chains" app |
| `backend/documents/` | `models.py` (`LeaveDocumentTemplate`, `ApprovedLeaveDocument`), `services.py`, `tasks.py`, `views.py`, `urls.py`, `migrations/0001–0002` | Approved-leave PDF + template |

**Hard prerequisites** (already exist on most bases but must be co-evolved —
a full merge brings their team-manager versions): `users`, `leave`, `audit`,
`notifications`. **Migration-only prerequisites:** `plans`. **Dependents you may
also want:** `system_admin`, `launcher`.

### Frontend footprint

| Feature | Routes | API proxies | Components | Lib |
|---|---|---|---|---|
| Organisation + teams | `app/(dashboard)/organisation/**` | `app/api/hr/{teams,workflows,section-members,approver-roles,campuses,role-assignments,team-role-assignments,campus-role-assignments}/**` | `components/hr/team-*.tsx`, `workflow-form.tsx`, `approver-role-*.tsx`, `campus-*.tsx`, `wide-holding-panel.tsx`, `TeamsSection.tsx`, `RolesSection.tsx` | `lib/teams*.ts`, `lib/workflows*.ts`, `lib/approver-role*.ts`, `lib/team-access.ts`, `team-category.ts`, `team-members*.ts` |
| Approvals | `app/(dashboard)/approvals/**`, `app/(dashboard)/dashboard/plans/approvals/**` | `app/api/approvals/**`, `app/api/plans/approvals/**` | `components/approvals/**`, `components/plans/plan-approval*`, `plan-decision-*` | `lib/approvals/**`, `lib/plans/**` |
| Documents | `app/(dashboard)/documents/**` | `app/api/approved-leave-documents/**`, `app/api/hr/approved-leave-documents/**` | `components/documents/**` | `lib/documents/` |

**Shared infrastructure** these depend on (must be present and current):
`components/module-shell.tsx`, `components/ui/**`,
`app/api/_lib/api-fetch.ts`, `lib/api-client.ts`, `lib/apps-registry.ts`, and the
module redirects in `frontend/next.config.ts`.

---

## §5 — Why merge the whole branch, not just the four folders

It is tempting to copy only `backend/{documents,organisation,approvals,workflows}`.
**Do not.** They are entangled:

1. **Cyclic imports.** `organisation` imports `workflows` (`organisation/services.py`
   uses `Section`, `SectionMember`, `Workflow`, `WorkflowMember`) and `workflows`
   imports `organisation`, including *private* helpers such as
   `_resolve_stage_role`. `approvals` imports both. Splitting them apart breaks
   imports and migrations.

2. **Cyclic migration graph.** `organisation/0001` depends on `workflows/0030`;
   `organisation/0004`,`0007` depend on `workflows/0033`,`0034`; `workflows/0031–0034`
   depend on `organisation/0002–0005`; `approvals/0004` depends on
   `workflows/0033`. Django can only order these if **all four apps ship in the
   same tree**.

3. **Migration edges reach outside the four apps.** `organisation/0004` also
   depends on `notifications/0009` and `plans/0005`; `approvals/0001` depends on
   `leave/0006`. Cherry-picking the four folders while leaving the rest of the
   tree behind produces `NodeNotFoundError` on `migrate`.

4. **The old tables must not move.** The refactor kept every moved model's
   `db_table` at `workflows_<model>` and wrapped the moves in
   `SeparateDatabaseAndState(state_operations=[...], database_operations=[])`.
   This is a **non-destructive** model-state move. Never rename/drop these
   tables by hand or with raw SQL; let `migrate` handle state only.

A full merge takes the dependency closure in the right commit order, which is the
least error-prone path.

---

## §6 — Merge procedure

### 6.1 Prepare

```bash
git status                       # must be clean — stash or commit your work first
git fetch origin
git switch -c backup/my-branch-pre-team-manager   # safety net
git switch my-branch
```

Note your current leaves so you can compare after:

```bash
python manage.py showmigrations users leave notifications plans organisation approvals workflows documents
```

Make sure dependencies are installed (the branch adds none to the backend, but the
frontend `package.json` may change):

```bash
cd backend  && uv sync
cd ../frontend && npm install
```

### 6.2 Inspect before you merge

```bash
git log --oneline --no-merges <your-base>..origin/feature/team-manager | head -40
git diff --stat <your-base>..origin/feature/team-manager | tail -30
git diff --name-status <your-base>..origin/feature/team-manager -- backend/documents backend/organisation backend/approvals backend/workflows
```

### 6.3 Merge

```bash
# Optional dry run: let git stop before committing so you can review.
git merge --no-commit --no-ff origin/feature/team-manager

# ... resolve conflicts (§7), then:
git add -A
git commit                     # completes the merge

# Or, if you want to back out entirely:
git merge --abort
```

If you merge without `--no-commit`, resolve, `git add -A`, then `git commit` to
finalise the merge commit.

---

## §7 — Conflict resolution playbook

Resolve by **understanding intent**, never by blindly taking one side (see
`context/code-standards.md`). Then:

```bash
git status                                    # list conflicted files
git grep -nE '^(<<<<<<<|=======|>>>>>>>)'     # must return nothing before committing
```

### 7.1 Config and wiring — usually a union

| File | Resolution |
|---|---|
| `backend/config/settings/base.py` | Keep **both** sides' `INSTALLED_APPS` entries. Ensure all of `users`, `organisation`, `approvals`, `leave`, `workflows`, `notifications`, `plans`, `documents`, `audit`, `launcher`, `system_admin` are present. Ensure the line `WORKFLOW_PROVIDER = "workflows.providers.DatabaseWorkflowProvider"` exists. |
| `backend/config/urls.py` | Union of the `path("api/v1/", include("..."))` lines for `approvals`, `organisation`, `workflows`, `plans`, `documents`, plus whatever your branch added. |
| `frontend/next.config.ts` | Keep the module **redirects** (legacy `/dashboard/**` → `/leave`, `/approvals`, `/organisation`, `/hr-admin`). Merge with your own `redirects()`/config entries. |
| `frontend/lib/apps-registry.ts` | Union of `APPS_REGISTRY` entries (`leave`, `approvals`, `organisation`, `documents`, `hr-admin`, and yours). |
| `frontend/package.json` | Union of `dependencies`/`devDependencies`; rerun `npm install`. |
| `frontend/lib/api-client.ts`, `frontend/app/api/_lib/api-fetch.ts` | Merge carefully — both branches likely touched the fetch/token-refresh helper. Preserve your auth behaviour **and** theirs. |

### 7.2 Migrations — never hand-merge

- If both sides changed the **same app's** migrations (most likely `users`,
  `leave`, `notifications`, `plans`), take `feature/team-manager`'s migration
  files for the **four target apps** (`organisation`, `approvals`, `workflows`,
  `documents`) wholesale, then reconcile the prereq apps as in §9.
- Do not invent a migration that "does both sides". After resolving, run
  `python manage.py makemigrations --check --dry-run`. It must say **"No changes
  detected"**. If it proposes changes, either generate the missing migration or
  fix the model/state mismatch.

### 7.3 Deleted files — accept deletions unless your work depends on them

`feature/team-manager` **removed**, among others:

- `backend/workflows/approval.py`, `backend/workflows/database_provider.py`,
  `backend/workflows/utils.py` (old monolith pieces moved into `organisation`/`approvals`).
- `backend/workflows/management/commands/seed_approvals_dev.py`.
- `backend/documents/generator.py`, `backend/documents/finalisation.py`, and
  `backend/documents/tests_approved_document.py` (superseded by the current
  documents app; note `documents/migrations/0002_approvedleavedocument.py` still
  exists but is **modified**, so treat it as theirs, not deleted).

If a conflict shows "deleted by them / modified by you", decide from intent:
- If your change was to the **old** mechanism that no longer exists → accept the
  deletion and port your change to its new home (`organisation`/`approvals`/`documents`).
- If you added something genuinely independent to that file → keep your version
  and re-home it under the new app.

### 7.4 Frontend conflicts

- Component/lib conflicts are ordinary merges; both sides usually add to files.
- If a route moved (`/dashboard/hr-admin/teams` → `/organisation/teams`), keep the
  new route and the `next.config.ts` redirect; search for stale links:
  ```bash
  git grep -n "dashboard/hr-admin/teams\|dashboard/hr-admin/roles" frontend -- '*.tsx' '*.ts'
  ```

### 7.5 The trap that already bit this repo once

Merge commit `726ee04` was committed **with unresolved conflict markers still in
the files**, and needed a separate rescue pass (see
`context/progress-tracker.md`, "Broken-Merge Recovery"). Before you commit:

```bash
git grep -nE '^(<<<<<<<|=======|>>>>>>>)' && echo "STOP: conflict markers present"
python -m compileall -q backend && echo "backend parses"
```

---

## §8 — Backend after merge

```bash
cd backend

# 1. Confirm the app registry and URLs are sane.
python manage.py check

# 2. Confirm no ungenerated model changes.
python manage.py makemigrations --check --dry-run     # must say "No changes detected"

# 3. See the ordered plan, then apply it.
python manage.py showmigrations
python manage.py migrate

# 4. Seed / smoke data as your environment needs.
python manage.py seed_dev_users          # grades, leave types, rules, financial year, workflows
python manage.py seed_e2e                # optional: full demo scenario smoke
# uv run manage.py retire_demo_users      # only when you want the demo accounts gone
```

- Bring up the worker if you use real mail/scheduled jobs:
  `uv run manage.py qcluster` (requires `croniter`; `uv sync` if it complains).
- Storage env vars used indirectly by `documents` via `leave.services.storage`:
  `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_BUCKET`,
  `SUPABASE_SIGNED_URL_EXPIRY` (see `backend/.env.example`).

### §9 — Reconciling migration graphs when the merge conflicts

Symptom: `NodeNotFoundError: Migration ... depends on nonexistent node ...`, or
`makemigrations --check` proposes new migrations.

1. **Your branch is *behind* on a prereq leaf.** Usually easiest: take
   `feature/team-manager`'s migration files for the conflicted prereq app and let
   `migrate` walk forward. Confirm no data migration you care about is skipped.
2. **Your branch added a migration to a prereq app that team-manager doesn't
   have.** Keep your migration, and set its `dependencies` so it sits **after**
   the team-manager leaf, e.g.:
   ```python
   dependencies = [
       ("leave", "0021_alter_cancellationrequest_status"),   # team-manager leaf
       ("your_app", "0003_previous_local_migration"),
   ]
   ```
   Then `makemigrations --check` must report no changes.
3. **Both sides renamed a migration to different numbers.** Renumber once, fix
   every `dependencies` reference (grep the string), then re-run
   `makemigrations --check` and `migrate --plan`.
4. **Never** run `migrate --fake` to paper over a missing node — fix the graph.

---

## §10 — Frontend & verification checklist

### Frontend

```bash
cd frontend
npm install
npm run lint
npx tsc --noEmit          # if your branch has a typecheck script, prefer it
npm test
npm run build
```

- If the Next dev server is running, it may generate a broken
  `.next/dev/types/validator.ts`; if `tsc` fails inside `.next/`, delete that
  generated file and rerun.
- Confirm modules resolve: `/organisation`, `/organisation/teams`,
  `/approvals`, `/documents` are reachable and the launcher
  (`lib/apps-registry.ts`) shows the entries.

### Backend

```bash
cd backend
python manage.py check
python manage.py makemigrations --check --dry-run     # "No changes detected"
python manage.py test organisation approvals workflows documents --noinput
# then the wider suites that reference them:
python manage.py test leave users notifications plans --noinput
```

### End-to-end

```bash
# backend test DB must allow CREATEDB on the role
cd frontend && npm run test:e2e     # canned leave scenario end-to-end
```

**Green gate before pushing:** backend `check` clean, `makemigrations --check`
clean, targeted + full backend tests green, `npm test` + `npm run lint` +
`npm run build` clean, no conflict markers anywhere.

---

## §11 — Rollback

```bash
# Before committing the merge:
git merge --abort

# After committing but before pushing:
git reset --hard backup/my-branch-pre-team-manager

# If migrations were applied and you must undo them:
python manage.py migrate <app> <previous_migration>   # e.g. migrate approvals 0003
```

Keep the `backup/<your-branch>-pre-team-manager` branch until your branch is
pushed and verified. The moved `workflows_*` tables are preserved by design, so a
code rollback does not lose organisation/approval data.

---

## Appendix — File ownership map (what comes with each app)

### Backend

| App | Owns |
|---|---|
| `documents` | `backend/documents/**` (models, services, tasks, views, urls, migrations 0001–0002, tests) |
| `organisation` | `backend/organisation/**` (models, serializers, services, permissions, views, urls, migrations 0001–0008, tests) |
| `approvals` | `backend/approvals/**` (models, payloads, serializers, services, views, urls, migrations 0001–0004, tests) |
| `workflows` (teams/chains) | `backend/workflows/**` (models, providers, policies, presets, services, events, permissions, views, urls, migrations 0001–0034, `tests_*.py`) |
| config | `backend/config/settings/base.py` (INSTALLED_APPS + `WORKFLOW_PROVIDER`), `backend/config/urls.py` |

### Frontend

| Feature | Paths |
|---|---|
| Organisation + teams | `frontend/app/(dashboard)/organisation/**`; `frontend/app/api/hr/{teams,workflows,section-members,approver-roles,campuses,role-assignments,team-role-assignments,campus-role-assignments}/**`; `frontend/components/hr/team-*.tsx`, `workflow-form.tsx`, `approver-role-*.tsx`, `campus-*.tsx`, `wide-holding-panel.tsx`, `TeamsSection.tsx`, `RolesSection.tsx`; `frontend/lib/{teams,teams-client,workflows,workflows-client,approver-roles,approver-roles-client,approver-role-scopes,team-access,team-category,team-members,team-members-client}.ts` |
| Approvals | `frontend/app/(dashboard)/approvals/**`; `frontend/app/(dashboard)/dashboard/plans/approvals/**`; `frontend/app/api/approvals/**`; `frontend/app/api/plans/{approvals,capabilities}/**`; `frontend/components/approvals/**`; `frontend/components/plans/plan-approval*.tsx`, `plan-decision-*.tsx`; `frontend/lib/approvals/**`, `frontend/lib/plans/**` |
| Documents | `frontend/app/(dashboard)/documents/**`; `frontend/app/api/approved-leave-documents/**`; `frontend/app/api/hr/approved-leave-documents/**`; `frontend/components/documents/**`; `frontend/lib/documents/**` |
| Shared | `frontend/components/module-shell.tsx`; `frontend/components/ui/**`; `frontend/app/api/_lib/api-fetch.ts`; `frontend/lib/api-client.ts`; `frontend/lib/apps-registry.ts`; `frontend/next.config.ts` |

### Tests to expect

- Backend: `backend/{documents,organisation,approvals}/tests.py`,
  `backend/workflows/tests*.py`, plus interactions in `backend/leave/tests/**`.
- Frontend: `frontend/tests/{team-*,workflow-form-*,approver-*,campus-*,approvals-*,approval-detail,plan-approvals-*, module-shell, ...}.test.*`.

---

## Where to read more

| If you want… | Read this |
|---|---|
| Product scope and features | `context/project-overview.md` |
| How the parts fit together | `context/architecture.md` |
| Coding rules / conflict expectations | `context/code-standards.md` |
| The merge history and the split rationale | `context/progress-tracker.md` ("Broken-Merge Recovery… `org`/`approvals` Split") |
| Where to edit things day-to-day | `DEVELOPER-GUIDE.md` |
