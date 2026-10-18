# Troubleshooting Notes

Document known issues and their resolutions here.

## Launcher never shown after login (2026-10-14)

**Symptom:** after signing in the user landed on the leave dashboard (`/dashboard`)
instead of the App Launcher.

**Cause:** three separate issues compounded:

1. **Conflicting root route.** Both `app/page.tsx` (old flat root that
   `redirect("/dashboard")`d authenticated users) and the new
   `app/(dashboard)/page.tsx` resolved to `/`. Route groups are transparent, so
   Next.js rejects/ignores one of them and the old page served `/`.
2. **Proxy redirect.** `proxy.ts` sent any authenticated visitor to `/login`
   straight to `/dashboard`, short-circuiting the launcher on the way in.
3. **Server-only fetch in a client component.** `components/launcher/app-launcher-grid.tsx`
   is `"use client"` but `lib/launcher.ts` called `apiClient`, which imports
   `next/headers` and cannot run in the browser. There was also no Next route
   handler for the launcher endpoint.

**Fix:**

- Deleted `app/page.tsx`; the launcher is now `app/(launcher)/page.tsx` on `/`,
  wrapped by `app/(launcher)/layout.tsx` + `components/launcher/launcher-shell.tsx`
  (its own minimal shell — no `DashboardShell` sidebar).
- `proxy.ts` now redirects authenticated auth-route hits to `/`.
- Added `app/api/apps/launcher/route.ts` (via `apiFetch`) and changed
  `lib/launcher.ts` to a browser `fetch("/api/apps/launcher/")`.

**Interim (RESOLVED 2026-10-15):** `lib/apps-registry.ts` now points at the
module roots — `/leave`, `/approvals`, `/organisation`, `/documents`,
`/hr-admin` — since the page moves completed (Phase 2d). Legacy `/dashboard/*`
paths still work via `next.config.ts` redirects.

**Double shell (RESOLVED 2026-10-15):** `(dashboard)/layout.tsx` is now only the
auth guard; `DashboardShell` moved to `dashboard/layout.tsx`, scoped to the
legacy tree, so module pages render only their own `ModuleShell`.

## Launcher grid empty for every role (2026-10-15)

**Symptom:** the App Launcher always showed "No apps available for your role"
even for HR/superusers.

**Cause:** frontend/backend path mismatch. `lib/launcher.ts` and
`app/api/apps/launcher/route.ts` request `apps/launcher/`
(`/api/v1/apps/launcher/`), and `launcher/services.py`'s own docstring names
`/api/v1/apps/launcher/`, but `launcher/urls.py` registered `launcher/`
(`/api/v1/launcher/`). The proxy's request 404'd, the grid swallowed the error
and rendered the empty state.

**Fix:** registered the endpoint at `path("apps/launcher/", ...)` in
`launcher/urls.py`, matching the proxy and the spec. Added `launcher/tests.py`
(per-role app sets + badge flow-through) and frontend
`tests/launcher-proxy.test.ts` / `tests/app-launcher-grid.test.tsx`.

## "Each child in a list should have a unique key prop" on HR admin lists (2026-10-15)

**Symptom:** `/hr-admin/employees` (and the same pattern on
`/hr-admin/calendar`) logged `Each child in a list should have a unique "key"
prop. Check the top-level render call using <EmployeesSection>` pointing at the
search `<form>`.

**Cause:** the server page authored a search/filter `<form>` (two or more
sibling children) and passed it to a client section component through a JSX
slot prop (`filter`). Markup authored in a server component and rendered inside
a client component crosses the RSC boundary, where React re-creates the elements
without the dev runtime's "written as static siblings" flag and treats the
form's children as an array — the per-child `key`s do not survive. This is the
exact case `TeamsSection`/`DelegationsSection` already avoid by taking plain
data (`filters`/`tabs`) instead of markup.

**Fix:** the client sections now render their own controls from plain data, the
approach already documented in `TeamsSection.tsx`:
- `EmployeesSection` renders the `?search` GET form itself (props unchanged).
- `HolidaysSection` renders the `?year` GET form itself from a new
  `availableYears: string[]` prop; the calendar page passes it and drops its
  `filter` slot. Updated `tests/hr-admin-form-overlays.test.tsx` to assert the
  section renders the year filter rather than a passed-in slot.
Pages still own the URLs; only the markup moved to the client side.

## "Only plain objects can be passed to Client Components" on module pages (2026-10-15)

**Symptom:** navigating to a restructured module (e.g. `/hr-admin`) logged
`Only plain objects can be passed to Client Components from Server Components.
{... icon: {$$typeof: ..., render: ...}}` and the page failed to render.

**Cause:** the five module layouts (`leave`, `approvals`, `organisation`,
`documents`, `hr-admin`) were server components passing `navItems` — whose
`icon` entries are lucide component references — to `ModuleShell`, a client
component. Component references are not serializable across the RSC boundary.

**Fix:** added `"use client";` to each module layout, keeping the icons in
client scope. The legacy `/dashboard` tree is unaffected: its shell
(`dashboard-shell.tsx`) is already a client component and defines its icons
internally, and `dashboard/layout.tsx` passes only plain data (`user`,
capability booleans/counts). Guard: `tests/module-layouts-client.test.ts`
walks `app/**/layout.tsx`, finds every layout that passes icons to
`ModuleShell`, and asserts it is a client component.

## Missing `/leave` index 404 (2026-10-15)

**Symptom:** the launcher "Leave" card and the leave sidebar's "My Leave" link
led to a 404.

**Cause:** the restructure pointed the apps registry and leave nav at `/leave`,
but no `app/(dashboard)/leave/page.tsx` existed (the applicant landing is
`/leave/drafts`; the pre-restructure registry used `/dashboard`).

**Fix:** added `leave/page.tsx` redirecting to `/leave/drafts`, mirroring
`organisation/page.tsx` → `/organisation/teams`.

## 2026-10-14: Airbnb DESIGN.md applied app-wide (theme tokens)
- Generated DESIGN.md (767 lines) from Airbnb reference (`npx @designmdcc/cli "https://www.airbnb.com/" --force --quiet > DESIGN.md`); source of truth for colours, radius, elevation, motion, typography.
- Remapped semantic tokens in `frontend/app/globals.css` (`:root` light) to DESIGN.md values: primary `#ff385c` (Rausch), page `#f7f7f7`, text `#222222/#6c6c6c`, inputs `#c1c1c1`, borders `#e5e5e5/#c1c1c1`, radius `sm 8px md 8px lg 14px xl 32px control 20px full 50px`, elevation `card-default` with 1px 2% ring (cards made borderless), duration `fast/base 150ms slow 250ms`, focus ring black `#222222`, font stack `Airbnb Cereal VF` with system fallbacks.
- Adapted `:root.dark` analogously to a neutral dark palette keeping dark mode intact. 
- Primitives: `components/ui/card.tsx` → cardStyles now borderless (shadow carries elevation). `components/ui/checkbox.tsx` → radius-sm (8px). `components/ui/badge.tsx` comment/geometry unchanged (uses 8px radius-sm).
- Verified: `frontend/npm run lint` clean, `frontend/npx tsc --noEmit -p tsconfig.json` clean, `frontend/npm test` 974 passed, live compiled CSS contains `#ff385c` and `--control-radius: 20px`. Dev server still serving login successfully.

## 2026-10-14: Stripe DESIGN.md applied app-wide (theme tokens)
- Generated DESIGN.md (750 lines) from Stripe reference (`npx @designmdcc/cli stripe.com > DESIGN.md`); source of truth for Stripe's design tokens.
- Updated semantic tokens in `frontend/app/globals.css` to Stripe palette: primary `#533afd`, surfaces `#ffffff` page, text `#000000`, borders `#e3e8ef`, radius `sm 4px md 6px lg 8px full 100px control 4px`, shadows from Stripe values, focus ring `#533afd`, font stack `sohne-var` with system fallbacks.
- Adapted dark theme analogously. 
- Primitives: card borderless (elevation), checkbox radius-sm. 
- Verified: `frontend/npm run lint` clean, `frontend/npx tsc --noEmit -p tsconfig.json` clean, live compiled CSS contains `#533afd`, `sohne-var`, `--control-radius: 4px`. Dev server serving normally.
