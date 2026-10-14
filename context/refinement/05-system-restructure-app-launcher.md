# Unit 5— System Restructure into Feature Modules + App Launcher

read `context/AGENTS.md` before starting

## 1. Goal

Reorganize the existing codebase (backend Django apps and frontend routes/components) into clearly bounded **feature modules** — Leave, Approvals, Organization, Documents, HR Administration — each spanning both sides of the stack under a matching name. Add a role-filtered **App Launcher** landing page that replaces the current default dashboard route: after login, the user sees cards for only the apps their role can access, with live badge counts, and selecting one enters that app's own scoped dashboard/sidebar.

### Assumptions (flag if wrong)

| # | Assumption |
|---|---|
| A1 | This is a **retroactive reorganization** of Units 13-19's existing code, not just a convention for future units — confirmed by "restructure my existing system." |
| A2 | This unit reorganizes **where code lives and how it's routed/accessed**, not the underlying data models. The `backend/workflows/` app splits into `backend/org/` and `backend/approvals/` by *moving* existing models/logic, but `ApplicationStage`/`ApprovalDecision` stay leave-application-specific here — the earlier idea of a generic content-type-based approval engine (for Plans to share) is a separate, bigger decision and is explicitly **not** done in this unit. Flag if you want that folded in now instead of later. |
| A3 | Naming convention: backend and frontend feature folders use the **same key** (e.g. `approvals` on both sides) so the pairing is always obvious by name, not just by convention knowledge. |
| A4 | The app registry (which apps exist, their display name/description/icon/route) is **frontend static config**; which apps a given user can access and their badge counts come from the backend launcher endpoint, merged client-side. This keeps "backend is sole authority on access" intact while keeping display metadata (icons, copy) out of the API payload. |
| A5 | The launcher becomes the **new default post-login route** — whatever currently loads first after login (e.g. a flat `/dashboard`) is replaced by the launcher at that same top-level slot, and each app's own dashboard moves to its own sub-path. |

### Out of scope

The generic/content-type approvals engine (A2), the Plans feature itself (separate future unit), redesigning any page's visual content beyond what moving it into the new shell requires, changing any business logic, validation, or API contracts — this unit moves and re-routes existing, working code.

---

## 2. Design

### 2.1 Feature module boundaries

| Module key | Backend app | Frontend route group | Frontend components | Owns |
|---|---|---|---|---|
| `leave` | `backend/leave/` (existing, unchanged) | `frontend/app/(dashboard)/leave/` | `frontend/components/leave/` | `LeaveApplication`, `LeaveType`, balances, Units 13/14/17 |
| `approvals` | `backend/approvals/` (new — split out of `workflows`) | `frontend/app/(dashboard)/approvals/` | `frontend/components/approvals/` | `ApplicationStage`, `ApprovalDecision`, chain-resolution logic, Unit 16, the Stepper's approval-chain usage |
| `org` | `backend/org/` (new — split out of `workflows`, plus the org-tree blueprint's new models) | `frontend/app/(dashboard)/org/` | `frontend/components/org/` | `OrgUnit`, `ActingAssignment`, Teams/Roles (from `feature/hr-track`), the org tree UI |
| `documents` | `backend/documents/` (existing, unchanged) | `frontend/app/(dashboard)/documents/` | `frontend/components/documents/` (existing — `SupportingDocumentsPanel`) | Unit 19, unchanged |
| `hr-admin` | spans `backend/users/` + relevant parts of `org`/`leave` admin endpoints | `frontend/app/(dashboard)/hr-admin/` | `frontend/components/hr-admin/` | Employee management, leave-type/grade rule admin, the onboarding unit if built |

`backend/users/`, `backend/notifications/`, `backend/audit/` stay as shared/infrastructure apps — not feature modules with their own launcher card, since nothing user-facing is "the users app" as a destination.

`frontend/components/ui/` stays as-is: shared, type-based primitives (Button, Card, Dialog, Stepper, Avatar, Badge, Table, Skeleton) used *by* every module, owned by none. This is the one directory this unit does **not** reorganize by feature.

### 2.2 Splitting `workflows` → `org` + `approvals`

This is the one genuinely nontrivial move, since `workflows` currently holds both org/team structure and approval-decision logic together. Split rule:

- **Goes to `org`:** anything that answers "who/what is this unit, who is its approver, what's its structure" — `OrgUnit`-equivalent data (or whatever `feature/hr-track`'s Teams/Roles currently model), `ActingAssignment`, org-tree read endpoints, HR org-configuration endpoints.
- **Goes to `approvals`:** anything that answers "what stage is this application at, who decided what, what happens next" — `ApplicationStage`, `ApprovalDecision`, the chain-walk/resolution function, decision endpoints, Unit 16's approver queue logic.
- The chain-resolution function in `approvals` **imports from** `org` (to call `resolve_approver()` on each unit) — this is the one expected cross-module dependency, and it's one-directional (`approvals` depends on `org`, never the reverse).

### 2.3 App Launcher — page

Replaces the current default landing route. One page, `frontend/app/(dashboard)/page.tsx` (or a dedicated `/launcher` if you'd rather keep `/dashboard` reserved for something else — pick one; this spec assumes the former).

- Fetches `GET /api/apps/launcher/` on load.
- Merges the response (accessible app keys + badges) against the static frontend registry (A4) to render cards — any key the backend doesn't return is simply not rendered, no frontend-side permission logic.
- Card grid, responsive, per the visual spec already designed (icon badge, name, description, optional count badge, hover lift+arrow).
- Clicking a card navigates to that module's own root route (e.g. `/approvals`).

### 2.4 App Launcher — backend endpoint

```
GET /api/apps/launcher/
```

Thin aggregator, no new business logic — calls existing service functions from each module and assembles counts, per the design already agreed:

```python
def get_launcher_apps(user) -> list[dict]:
    apps = []
    if can_access_leave(user):
        apps.append({"key": "leave", "badge": _leave_badge(user)})
    if can_access_approvals(user):
        apps.append({"key": "approvals", "badge": _approvals_badge(user)})
    if can_access_org(user):
        apps.append({"key": "org", "badge": _org_badge(user)})
    if can_access_documents(user):
        apps.append({"key": "documents", "badge": None})
    if can_access_hr_admin(user):
        apps.append({"key": "hr-admin", "badge": _hr_admin_badge(user)})
    return apps

def _approvals_badge(user) -> dict | None:
    count = approvals.services.pending_stage_count_for(user)  # reuses Unit 16's existing query
    return {"count": count, "label": "pending", "tone": "amber"} if count else None
```

`badge: None` (no key present, or `None` value) → frontend renders no badge, per the already-agreed "absence, not zero" rule.

### 2.5 Each app's own shell once entered

Per the Stitch design already approved: once inside a module, the sidebar shows **only that module's nav items**, plus a distinct "← All Apps" link back to the launcher at the top, visually separated from the module's own nav. This sidebar is module-scoped — it is not the same global sidebar re-skinned, it's genuinely showing a different, smaller nav tree per module.

### 2.6 Route structure, before and after

```
Before (flat):
  /dashboard
  /applications/[id]
  /applications/[id]/edit
  /approvals
  /approvals/[id]
  /hr-admin/employees
  /hr-admin/workflows/...   (or /hr-admin/roles/... post team-base merge)

After (grouped):
  /                          ← App Launcher (new default landing page)
  /leave/applications/[id]
  /leave/applications/[id]/edit
  /approvals
  /approvals/[id]
  /org/...                   ← org tree, teams, acting assignments
  /documents/...              ← if documents ever gets dedicated pages beyond the embedded panel
  /hr-admin/employees
  /hr-admin/...
```

Next.js route groups (`(dashboard)`) can keep the shared layout/shell wiring without the parentheses appearing in the URL — use a route group per module if that fits the existing Next.js App Router structure, or plain nested folders if simpler; either way the *module boundary* is what matters, not the specific Next.js mechanism used to achieve it.

---

## 3. Implementation

### 3.1 Backend — create `org` and `approvals` apps

```bash
cd backend
python manage.py startapp org
python manage.py startapp approvals
```

1. Move `OrgUnit`/`ActingAssignment`-equivalent models (or `feature/hr-track`'s Teams/Roles models, once merged per the earlier merge prompt) from `workflows/models.py` into `org/models.py`.
2. Move `ApplicationStage`, `ApprovalDecision`, and the chain-resolution service from `workflows/` into `approvals/`.
3. Write Django migrations that **move tables, not drop/recreate them** — use `migrations.SeparateDatabaseAndState` or a manual state-only migration pointing the existing tables at the new app label, so no data is lost and no destructive migration runs against a populated database. This is the single highest-risk step in this unit — test it against a copy of real/staging data before running on anything with live applications in it.
4. Update every `import` across the codebase referencing the moved models/services (`workflows.models.ApplicationStage` → `approvals.models.ApplicationStage`, etc.) — a project-wide search-and-replace, then a full test run to catch anything missed.
5. Delete `workflows/` once empty, or repurpose it as a thin shim re-exporting from the two new apps for one release cycle if you want a softer transition — your call; a clean cut is simpler if nothing external depends on the old import paths.
6. Add `org/services.py` with `can_access_org(user)`, `approvals/services.py` with `can_access_approvals(user)` and `pending_stage_count_for(user)` — small access/badge helper functions each module needs for the launcher endpoint (§3.3).

### 3.2 Backend — new `launcher` app

```bash
python manage.py startapp launcher
```

Thin app, no models — just `launcher/services.py` (the `get_launcher_apps` function from §2.4, importing from every other module) and `launcher/views.py` / `launcher/urls.py` exposing `GET /api/apps/launcher/`.

### 3.3 Backend — per-module access/badge helpers

Each module gets two small functions, used only by the launcher (and reusable wherever else access-checking is needed):

```python
# leave/services.py
def can_access_leave(user) -> bool: ...
def _leave_badge(user) -> dict | None: ...  # e.g. count of own applications in Correction Required

# approvals/services.py
def can_access_approvals(user) -> bool: ...  # true if user is ever a designated/acting approver anywhere
def pending_stage_count_for(user) -> int: ...  # already exists as part of Unit 16's queue query — reuse, don't duplicate

# org/services.py
def can_access_org(user) -> bool: ...  # true for HR/superuser
def _org_badge(user) -> dict | None: ...  # vacant-unit count, once the org-tree blueprint lands

# hr_admin — wherever HR admin endpoints currently live
def can_access_hr_admin(user) -> bool: ...
```

### 3.4 Frontend — reorganize folders

1. Create `frontend/app/(dashboard)/leave/`, `.../approvals/`, `.../org/`, `.../documents/`, `.../hr-admin/` (the last two may already mostly exist).
2. Move existing pages into their module's folder, updating `next/link` hrefs and any hardcoded route strings across the codebase.
3. Create `frontend/components/leave/`, `.../approvals/`, `.../org/` and move feature-specific components out of wherever they currently sit (flat under `components/`, or miscategorized) into their module.
4. Leave `frontend/components/ui/` untouched — confirm nothing module-specific has leaked in there; move anything that has back out to its owning module.

### 3.5 Frontend — app registry + launcher page

```ts
// frontend/lib/apps-registry.ts
export const APPS_REGISTRY = {
  leave: { name: "Leave Applications", description: "Submit and track your leave requests", icon: Calendar, route: "/leave" },
  approvals: { name: "Approvals", description: "Review and decide on leave requests assigned to you", icon: ShieldCheck, route: "/approvals" },
  org: { name: "Organization", description: "Manage units, approvers, and teams", icon: Building2, route: "/org" },
  documents: { name: "Documents", description: "Manage supporting documents", icon: FileStack, route: "/documents" },
  "hr-admin": { name: "HR Administration", description: "Manage employees, grades, and leave rules", icon: Users, route: "/hr-admin" },
} as const;
```

```tsx
// frontend/app/(dashboard)/page.tsx
export default function LauncherPage() {
  const { data } = useLauncherApps(); // GET /api/apps/launcher/
  const apps = data?.apps.map(a => ({ ...APPS_REGISTRY[a.key], ...a })) ?? [];
  return <AppLauncherGrid apps={apps} />;
}
```

Build `AppLauncherGrid` and `AppCard` per the Stitch-approved visual design — icon badge, name, description, optional count pill, hover lift, following the existing Card/token conventions, not raw new styling.

### 3.6 Frontend — module-scoped shell

Each module's layout (`frontend/app/(dashboard)/approvals/layout.tsx`, etc.) renders the floating-card sidebar with **only that module's nav items** plus the "← All Apps" link at the top, per §2.5. If a shared `ModuleShell` component can parametrize this (nav items list + module name passed as props) rather than duplicating the shell markup five times, build it that way — one shell component, five small nav-item arrays, not five copies of the shell.

### 3.7 Order of operations (to avoid a broken intermediate state)

1. Backend: create `org`/`approvals`/`launcher` apps, migrate data (§3.1, step 3) — verify with full test suite before touching frontend.
2. Backend: add access/badge helper functions (§3.3) and the launcher endpoint (§3.2) — verify via API client/tests.
3. Frontend: build `AppLauncherGrid`, `AppCard`, `ModuleShell`, and the registry — build these new pieces without yet moving existing pages, so they can be reviewed in isolation.
4. Frontend: move existing pages/components into their module folders one module at a time (leave, then approvals, then org, then hr-admin), running the app and testing after each move before starting the next — not all five at once.
5. Switch the default post-login route to the launcher last, once every module's internal routes work from their new locations.

### 3.8 Tests

- Backend: every moved model/service still passes its existing test suite, unchanged, from its new app location — this is a strong signal the migration didn't lose or break anything.
- Launcher endpoint: returns only apps the user's role permits; badge counts match the same numbers shown once inside each app; `badge: null` renders no badge, never a "0".
- Access helpers (`can_access_*`) correctly gate each app for at least one user per role (employee, approver, HR, superuser).
- Frontend: every existing Unit 13-19 test still passes against the new file locations (import paths updated).
- Manual: full click-through as each role — launcher shows the correct card set, each card navigates correctly, each module's sidebar shows only its own nav plus "All Apps," and that link correctly returns to the launcher.

---

## 4. Dependencies

**No new packages.** This is a reorganization of existing code plus one new thin aggregator endpoint and one new frontend page, built entirely with what's already in the stack.

---

## 5. Verification checklist

**Data integrity (highest priority)**
- [ ] The `workflows` → `org`/`approvals` migration preserves all existing `ApplicationStage`/`ApprovalDecision`/org data with zero loss — verified against a staging copy of real data before running anywhere near production.
- [ ] No duplicate or orphaned rows exist after migration.

**Backend**
- [ ] `org` and `approvals` apps exist as separate, independently testable Django apps.
- [ ] `approvals` imports from `org` (one-directional); `org` has no dependency on `approvals`.
- [ ] Every existing API endpoint still works at its existing URL (no accidental breaking changes to API contracts during the move) — or, if any endpoint URLs intentionally changed, the frontend is updated to match and nothing is left calling a stale path.
- [ ] `/api/apps/launcher/` returns the correct app set and badge counts per role, verified for employee, approver, HR, and superuser accounts.

**Frontend**
- [ ] Every page/component has moved into its owning module's folder; `components/ui/` contains only genuinely generic primitives.
- [ ] The launcher is the new default landing page after login.
- [ ] Each app card navigates correctly and only renders for roles with access.
- [ ] Each module's internal sidebar shows only that module's nav items plus a working "← All Apps" link.
- [ ] No broken internal links/hrefs remain pointing at pre-restructure routes anywhere in the app.

**Regression**
- [ ] Full existing test suite (backend and frontend) passes unchanged in content, only in new locations.
- [ ] A full manual click-through of Units 13-19's actual functionality (submit, approve, reject, correct, resubmit, cancel, upload/replace documents) still works end-to-end inside the new module structure.
