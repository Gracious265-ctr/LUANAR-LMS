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

**Interim:** `lib/apps-registry.ts` routes still point at the pre-restructure
`/dashboard/*` pages because the module pages (`/leave`, `/approvals`, `/org`,
`/documents`, `/hr-admin`) have not been moved yet — those folders currently
contain only `layout.tsx`, so their routes would 404. Swap each `route` back to
its module root once that module's pages land. `documents` has no standalone
page at all yet, so it points at `/dashboard`.

**Out of scope / still open:** module routes under `(dashboard)` are wrapped by
both `DashboardShell` (from `(dashboard)/layout.tsx`) and their own `ModuleShell`
— a double shell that should be resolved when the page moves are completed.

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
