# Unit 1 — Project Foundation and Development Contract

## Goal

Stand up a working monorepo skeleton where a Next.js frontend and a Django/DRF backend communicate over JWT-authenticated APIs against Postgres (also backing the Django-Q2 task queue), with the LUANAR design-token system wired into Tailwind and a real (but data-less) employee dashboard shell rendered for an authenticated, role-seeded test user.

## Assumptions made (flag if wrong)

Since the architecture doc leaves some of these open, this spec assumes:

- **Versions:** Python 3.12, Django 5.x, Node 20+, Next.js 15 (App Router, TypeScript).
- **Package managers:** `uv` for backend (dependency management + running commands, no `pip`/`venv` directly), `npm` for frontend. No Turborepo/npm-workspaces monorepo tooling in Unit 1 — just two sibling folders (`frontend/`, `backend/`) as architecture.md shows, with a root README tying them together. Can be layered in later if the second developer wants it.
- **Local infra:** Postgres installed and run natively on each developer's machine (no Docker, no Redis) — both developers document their exact install path (Homebrew, apt, Windows installer, etc.) in the README's setup section since it isn't standardized by a compose file. Postgres also serves as the broker/result store for Django-Q2, so no separate queue infrastructure is needed.
- **Git:** the GitHub repo already exists. Unit 1 just adds the `development` branch (as the integration branch) and the `feature/*` branch convention off it — no repo initialization.
- **JWT storage:** the frontend never touches raw tokens in client JS. Next.js Route Handlers proxy `/auth/login` and `/auth/refresh` to Django and set the access + refresh tokens as `httpOnly`, `Secure`, `SameSite=Lax` cookies. This is a deliberate seam — it's the same shape a future LUANAR SSO handoff would use, so Unit 1's dev auth isn't throwaway.
- **API key casing:** DRF's default `snake_case` JSON is kept as-is end-to-end (no camelCase transform layer) to avoid extra complexity this early. Revisit if it becomes painful.
- **Dark mode:** ui-context.md only defines light-theme tokens, so Unit 1 ships light-only. No theme toggle in the dashboard shell.
- **File storage / email / real workflow logic:** out of scope, per architecture.md's TBD list and the unit boundary — Unit 1 proves the shell works, not leave logic.

---

## Design

### Repository structure

```text
luanar-leave-system/
├── README.md                   # setup instructions for both devs
├── docs/
│   ├── project-overview.md
│   ├── architecture.md
│   └── ui-context.md
├── frontend/
│   ├── app/
│   │   ├── (auth)/login/
│   │   ├── (dashboard)/dashboard/
│   │   └── api/auth/[...]/route.ts   # login/refresh/logout proxy handlers
│   ├── components/
│   │   ├── ui/                       # 21st.dev components live here
│   │   └── dashboard/                # dashboard-specific composition
│   ├── lib/
│   │   ├── api-client.ts             # fetch wrapper, attaches cookies
│   │   ├── auth.ts                   # session/user helpers
│   │   └── utils.ts                  # cn() helper, etc.
│   ├── styles/globals.css
│   ├── components.json               # shadcn-compatible structure (see below)
│   ├── tailwind.config.ts
│   └── ...
├── backend/
│   ├── config/                       # settings, root urls, asgi/wsgi
│   ├── users/                        # custom user model, roles, JWT auth, seed command
│   ├── leave/                        # stub app, models.py placeholder only
│   ├── workflows/                    # stub app
│   ├── notifications/                # stub app
│   ├── documents/                    # stub app
│   ├── audit/                        # stub app
│   ├── manage.py
│   ├── pyproject.toml
│   └── uv.lock
└── storage/                          # empty, TBD per architecture.md
```

The five domain apps (`leave`, `workflows`, `notifications`, `documents`, `audit`) are registered in `INSTALLED_APPS` with an empty `models.py` and `apps.py` in Unit 1, purely to lock in the boundary structure from architecture.md §3. No models, no logic — that starts in later units.

### Component library structure ("shadcn project structure")

The 21st.dev prompt you pasted assumes a shadcn-compatible project layout (`components.json`, `/components/ui`, `/lib/utils.ts`, path aliases). That layout is just scaffolding convention — 21st.dev components are distributed in this format, but per ui-context.md §12 we are **not** pulling in shadcn/ui's own component set or replacing 21st.dev components with it. Unit 1 sets up:

- `components.json` (shadcn CLI config, pointed at `components/ui`, no shadcn theme presets applied)
- `lib/utils.ts` with a `cn()` helper (`clsx` + `tailwind-merge`)
- Path alias `@/*` → project root in `tsconfig.json`

### Design tokens → `globals.css`

Every token table in ui-context.md (§2–§9, §13) becomes a CSS custom property in `frontend/styles/globals.css` under `:root`, grouped by section with a comment header matching ui-context.md's numbering, e.g.:

```css
:root {
  /* Brand and Primary */
  --brand-primary: #0097F0;
  --brand-primary-hover: #0088D8;
  --brand-primary-active: #0079C0;
  --brand-primary-subtle: #EFF8FF;
  --brand-primary-muted: #DDF1FC;
  --brand-primary-border: #B8E1F8;
  --brand-primary-foreground: #FFFFFF;

  /* Institutional Secondary */
  --brand-secondary: #009119;
  /* ... */

  /* Semantic Status */
  --status-pending: #D97706;
  --status-pending-subtle: #FFF7E6;
  /* ...all 12 status tokens... */

  /* Radius */
  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-xl: 16px;
  --radius-2xl: 20px;
  --radius-3xl: 24px;
  --radius-full: 9999px;

  /* Shadows */
  --shadow-subtle: 0 1px 2px rgba(15, 23, 42, 0.04);
  --shadow-card: 0 2px 8px rgba(15, 23, 42, 0.06);
  --shadow-dropdown: 0 8px 24px rgba(15, 23, 42, 0.10);
  --shadow-modal: 0 16px 40px rgba(15, 23, 42, 0.14);
}
```

`tailwind.config.ts` then maps `theme.extend.colors`, `theme.extend.borderRadius`, `theme.extend.boxShadow`, and `theme.extend.fontFamily` to these CSS variables (e.g. `colors: { 'brand-primary': 'var(--brand-primary)', ... }`), so components use Tailwind utility classes (`bg-brand-primary`, `rounded-xl`, `shadow-card`) rather than hardcoded hex values anywhere.

**Typography:** Inter loaded via `next/font/google`, applied as the base font on `<body>`. Font-size/line-height/weight tokens from §7 are added to `tailwind.config.ts` `fontSize` (e.g. `'2xl': ['24px', '32px']`) so `text-2xl`, `font-semibold`, etc. match ui-context.md exactly rather than Tailwind's defaults.

**Icons:** `lucide-react` is the only icon source. No custom SVGs where a Lucide icon exists (ui-context.md §11).

### Dashboard shell

The pasted 21st.dev `dashboard-with-collapsible-sidebar` component is adapted, not copied verbatim:

- **Keep the structural pattern**: collapsible sidebar, main content area, header bar, card grid, activity list — this is the reusable shell.
- **Replace all e-commerce content**: no "Sales", "Products", "Orders". Sidebar nav becomes role-aware:
  - All roles: Dashboard, My Applications, New Application
  - Supervisor/HOD/Dean/Registrar/DVC: + Approvals
  - HOD and above: + Department/Team (placeholder link)
  - HR: + HR Administration (placeholder link)
  - All roles: Settings
- **Replace stat cards** with leave-relevant placeholders wired to static/dummy values in Unit 1 (real numbers arrive once the `leave` app has models/endpoints): Available Balance, Pending Applications, Applications Awaiting My Approval (approver roles only), Upcoming Leave.
- **Drop the dark-mode toggle** entirely (see assumptions above).
- **Apply LUANAR tokens**: swap the blue/gray Tailwind defaults for the `brand-primary`/`surface`/`text`/`status` token classes; swap notification badges to `status-pending`/`brand-primary` instead of arbitrary blue/red.
- **Header**: shows the authenticated user's name and role (pulled from the JWT-derived session, not hardcoded), replacing the generic "TomIsLoading / Pro Plan" block.
- This lives at `frontend/components/dashboard/` (composition) with any 21st.dev primitives it depends on in `components/ui/`, and is rendered at `app/(dashboard)/dashboard/page.tsx`, gated by the auth middleware.

---

## Implementation

### 1. Repository & tooling setup

- Repo already exists on GitHub. Create the `development` branch off `main` as the integration branch — all `feature/*` branches for Unit 1 (and beyond) branch off `development`, not `main`.
- Confirm local Postgres install on each developer's machine (no Redis needed — Django-Q2 uses Postgres as its broker); document the exact commands used (Homebrew/apt/installer) in the README so setup is reproducible without a compose file.
- Root `.gitignore` covering both `frontend/` and `backend/` artifacts (`node_modules`, `.next`, `__pycache__`, `.venv`, `*.pyc`, `.env`, `db.sqlite3` if ever used locally, `uv.lock`-adjacent caches).
- Root `README.md`: prerequisites (including native Postgres setup), backend setup commands (`uv sync`, `uv run manage.py migrate`, etc.), frontend setup commands, seed command, how to run both dev servers, how to run tests.

### 2. Backend foundation

- `uv init backend` to create `pyproject.toml`, then `uv add django djangorestframework ...` (full list in Dependencies below) instead of a `requirements.txt` + `pip install`.
- `uv run django-admin startproject config .` (run from `backend/`) then `uv run manage.py startapp` for `users`, `leave`, `workflows`, `notifications`, `documents`, `audit`. Every subsequent Django command goes through `uv run manage.py ...` so it resolves against the `uv`-managed environment.
- `config/settings/` split into `base.py`, `development.py` (import base, override `DEBUG`, `ALLOWED_HOSTS`, CORS) — keeps room for a future `production.py` without a rewrite.
- Postgres connection via `django-environ`, reading `DATABASE_URL` from `.env`, pointed at the native local Postgres instance.
- `django-cors-headers` configured to allow the frontend's origin (`http://localhost:3000`) with credentials, since the JWT cookies must round-trip.
- Custom user model in `users/models.py`: extends `AbstractUser`, adds a `role` field (choices: `employee`, `supervisor`, `hod`, `dean`, `registrar`, `dvc`, `hr`) — this is the seam architecture.md §6.1 describes (`Institutional Identity → Authentication → Application User → System Role → Permissions`); Unit 1 only needs `role`, not full employee profile fields (those belong to the `users`/HR work in a later unit).
- `AUTH_USER_MODEL = "users.User"` set before the first migration.
- `uv run manage.py seed_dev_users` management command creates one test user per role (`employee@test.luanar`, `supervisor@test.luanar`, etc.) with a known dev password, idempotent (safe to re-run).

### 3. Django REST Framework + JWT auth

- `djangorestframework` + `djangorestframework-simplejwt` installed.
- `REST_FRAMEWORK` default authentication class: `JWTAuthentication`. Default permission: `IsAuthenticated` (explicit `AllowAny` only on the login endpoint).
- Endpoints (all under `/api/v1/`):
  - `POST /api/v1/auth/login/` — email + password, returns `access` + `refresh`
  - `POST /api/v1/auth/refresh/` — returns new `access`
  - `GET /api/v1/auth/me/` — returns the authenticated user's `id`, `email`, `role`, `full_name` (protected, proves the token round-trip works)
- Access token lifetime short (e.g. 15 min), refresh longer (e.g. 1 day) — standard SimpleJWT settings, tune later.
- These are backend-only endpoints; the frontend never calls them directly (see cookie proxy below).

### 4. Frontend foundation

- `npx create-next-app@latest frontend --typescript --tailwind --app`.
- `npx shadcn@latest init` to generate `components.json` and the `lib/utils.ts` `cn()` helper — used purely for the file layout 21st.dev expects, not for installing shadcn's component set.
- Path alias `@/*` confirmed in `tsconfig.json`.
- `lucide-react` installed.

### 5. Auth cookie proxy (Next.js side)

- `app/api/auth/login/route.ts`: accepts email/password from the login form, calls Django's `/auth/login/`, sets `access_token` and `refresh_token` as `httpOnly` cookies on the response.
- `app/api/auth/refresh/route.ts`: reads the refresh cookie, calls Django's `/auth/refresh/`, rotates the `access_token` cookie.
- `app/api/auth/logout/route.ts`: clears both cookies.
- `lib/api-client.ts`: a `fetch` wrapper used by Server Components/Route Handlers that reads the `access_token` cookie and attaches `Authorization: Bearer <token>` when calling Django. On a 401, attempts one refresh-and-retry.
- `middleware.ts`: redirects unauthenticated requests to `(dashboard)` routes to `/login`.
- Login page (`app/(auth)/login/page.tsx`): simple form (email/password), posts to the local route handler, redirects to `/dashboard` on success — no 21st.dev styling investment needed yet beyond token colors, this isn't the focus of Unit 1.

### 6. Design tokens & Tailwind

- `styles/globals.css`: all CSS custom properties from ui-context.md §2–§9 and §13, as shown in Design above.
- `tailwind.config.ts`: `colors`, `borderRadius`, `boxShadow`, `fontFamily`, `fontSize` all extended to reference the CSS variables, not hardcoded values.
- `app/layout.tsx`: loads Inter via `next/font/google`, applies it as the body font, imports `globals.css`.

### 7. Dashboard shell component

- Build per the Design section above under `frontend/components/dashboard/` and `frontend/components/ui/`.
- Rendered at `app/(dashboard)/dashboard/page.tsx` as a Server Component that fetches `/api/v1/auth/me/` (via `lib/api-client.ts`) to get the current user's name/role, passed down to the shell.

### 8. Background task queue foundation (Django-Q2)

- `django-q2` added via `uv add django-q2`.
- `Q_CLUSTER` configured in Django settings with the ORM broker pointed at the default Postgres connection — no separate broker service, no Redis.
- One trivial task in `users/tasks.py`, e.g. a `ping()` function returning `"pong"`, dispatched via `async_task("users.tasks.ping")` — exists purely to prove a worker cluster can pick up and execute a task through the Postgres-backed queue. No real background jobs yet.
- `python manage.py qcluster` (run via `uv run manage.py qcluster`) is the worker process, documented in the README alongside the web server command.
- Django-Q2's admin integration (`django_q` in `INSTALLED_APPS`) is enabled so queued/completed tasks are visible in Django admin — useful for verifying the `ping` task actually ran without extra tooling.

### 9. Environment configuration

- `backend/.env.example` and `frontend/.env.example` committed; real `.env` files gitignored.
- Backend vars: `DEBUG`, `SECRET_KEY`, `DATABASE_URL`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, JWT lifetimes. No `REDIS_URL` — Django-Q2 reads its broker config from `DATABASE_URL`.
- Frontend vars: `NEXT_PUBLIC_APP_URL`, `DJANGO_API_URL` (server-side only, used by the route handlers/api-client, not exposed to the browser).

### 10. Test infrastructure

- **Backend:** Django's built-in `TestCase`, one `tests.py` (or `tests/` package) per app. Unit 1 adds exactly one real test: `users/tests.py` verifying the seeded roles can log in via `/api/v1/auth/login/` and that `/api/v1/auth/me/` returns 401 unauthenticated / 200 with the right role authenticated. `uv run manage.py test` as the run command.
- **Frontend:** `vitest` + `@testing-library/react` + `@testing-library/jest-dom`, `jsdom` environment, `vitest.config.ts` alongside `next.config.ts`. Unit 1 adds one real test rendering the dashboard shell with a mock user and asserting role-appropriate nav items appear/disappear.
- Both test commands documented in the root README and safe to run with no network dependency (mock the API client in the frontend test; use Django's test DB for the backend).

### 11. Shared API conventions

- All endpoints versioned under `/api/v1/`.
- `snake_case` JSON keys throughout (DRF default), no transform layer for now.
- Trailing slashes on all endpoint paths (DRF default `APPEND_SLASH` behavior).
- Standard DRF error shape: `{"detail": "..."}` for single errors, `{"field_name": ["error"]}` for validation errors — no custom envelope invented in Unit 1.
- Pagination: DRF's `PageNumberPagination`, default page size defined in settings, applied globally — even though no list endpoints exist yet, the convention is locked in now so `leave`/`workflows` endpoints don't reinvent it later.

### 12. Git collaboration conventions

- Repo already exists on GitHub with `main`. Create `development` off `main` as the integration branch.
- All work happens on short-lived `feature/<unit-or-ticket-slug>` branches cut from `development` (e.g. `feature/unit-1-auth`, `feature/unit-1-dashboard-shell`), merged back into `development` via PR, deleted after merge.
- `development` merges into `main` periodically when stable (not automatically on every PR).
- Commit style: `<type>(<scope>): <summary>` (e.g. `feat(auth): add JWT login endpoint`), types limited to `feat`, `fix`, `chore`, `docs`, `test`, `refactor`.
- PRs target `development`, require at least the other developer's review before merge, since this is a two-person team.
- No direct pushes to `main` or `development`.

---

## Dependencies

### Backend (managed by `uv`, in `backend/pyproject.toml`)

```
uv add django djangorestframework djangorestframework-simplejwt \
       "psycopg[binary]" django-environ django-cors-headers \
       django-q2
```

This writes the pinned versions into `pyproject.toml` and `uv.lock` (both committed) — no separate `requirements.txt`.

### Frontend (`frontend/package.json`, on top of the `create-next-app` defaults)

```
lucide-react
clsx
tailwind-merge
class-variance-authority
```

Dev dependencies:

```
vitest
@testing-library/react
@testing-library/jest-dom
jsdom
@vitejs/plugin-react
```

---

## Verification checklist

- [ ] Locally-installed Postgres is running; backend connects using `.env` values (no Docker, no Redis involved)
- [ ] `uv sync` installs backend dependencies from `pyproject.toml`/`uv.lock` into a `uv`-managed environment
- [ ] `uv run manage.py migrate` runs cleanly with the custom `users.User` model as `AUTH_USER_MODEL`
- [ ] `uv run manage.py seed_dev_users` creates one user per role (employee, supervisor, hod, dean, registrar, dvc, hr), idempotently
- [ ] `POST /api/v1/auth/login/` returns access + refresh tokens for a seeded user; wrong password returns 401
- [ ] `GET /api/v1/auth/me/` returns 401 with no token, and the correct `role`/`email` with a valid token
- [ ] Frontend login page authenticates against a seeded user via the Next.js route handlers, sets httpOnly cookies, and redirects to `/dashboard`
- [ ] `/dashboard` is unreachable without a valid session (middleware redirect to `/login`)
- [ ] Dashboard shell renders: collapsible sidebar, role-aware nav (verify at least one non-employee role sees "Approvals" and employee does not), placeholder leave-metric cards, header showing the real authenticated user's name/role — no e-commerce copy, icons, or dark-mode toggle remaining
- [ ] `globals.css` defines every token category from ui-context.md §2–§9 and §13; `tailwind.config.ts` resolves `bg-brand-primary`, `rounded-xl`, `shadow-card`, `text-2xl` etc. to the correct values (spot-check a few in devtools)
- [ ] Inter is the rendered font; Lucide is the only icon source in the dashboard
- [ ] `uv run manage.py qcluster` starts against the Postgres-backed ORM broker and successfully executes the `ping` task (visible in Django admin)
- [ ] `uv run manage.py test` passes, including the auth test in `users/tests.py`
- [ ] `npx vitest run` passes, including the dashboard-shell nav test
- [ ] `backend/.env.example` and `frontend/.env.example` committed; real `.env` files are gitignored and absent from git history
- [ ] Root `README.md` lets a second developer clone, install (including native Postgres setup), seed, and run both dev servers with no undocumented steps
- [ ] `development` branch exists off `main`; a sample PR from a `feature/*` branch into `development` follows the commit-message convention
