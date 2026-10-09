# Unit — UI/UX Premium Polish Pass (Beyond Tokens)

read `context/AGENTS.md` before starting

## 1. Goal

Add a set of concrete UI/UX features and interaction patterns — an approval-chain stepper, avatars, a command palette, a notification center, consistent empty/error states, and related polish — that make the system read as considered and premium, beyond what tokens and component restyling alone achieve. Each item ships independently and can be built, reviewed, and merged on its own.

### Assumptions (flag if wrong)

| # | Assumption |
|---|---|
| A1 | Light mode only, existing color palette unchanged (`#0097F0` primary, `#009119` secondary, status colors as defined in ui-context.md) — same constraint as the token/component pass. |
| A2 | The shared primitives (Button, Input, Card, Badge, Table, Skeleton, Dialog) from the token pass already exist and are token-driven. Everything below builds on them rather than introducing a second styling system. |
| A3 | The approval-chain stepper (§3.1) consumes the chain shape produced by the org-tree/approval-chain blueprint (separate spec). If that unit isn't built yet, the stepper can be built against fixture data and wired to the real chain endpoint later, same pattern as Units 13–19. |
| A4 | Icon set stays Lucide React exclusively, per ui-context.md — no new icon library introduced for any item below. |
| A5 | 21st.dev remains the primary component library; new components here (stepper, command palette, notification center) are custom-built following the same token/primitive conventions, not pulled from a different library. |

### Out of scope

Dark mode, any new brand/accent color, backend changes beyond the minimal read endpoints each feature needs (notification center, command palette search), analytics/telemetry.

---

## 2. Design — priority tiers

Each item is independently shippable. Grouped by priority so the team can build incrementally rather than as one large batch, same philosophy as the token-then-components rollout.

### Tier 1 — highest leverage, ties into existing backend work

| # | Feature | Why first |
|---|---|---|
| 1 | Approval-chain stepper | Makes the org-tree/chain-resolution work (separate spec) visible and understandable to employees and approvers — the single highest perceived-value item |
| 2 | Avatars (initials + deterministic color) | Touches every page that references a person — approvers, uploaders, audit entries — broad visual impact for low effort |
| 3 | Consistent empty states | Every list/table in the app currently has no defined empty state; this is a gap, not an enhancement |
| 4 | Status color consistency audit | Ensures the stepper, badges, table rows, and dashboard all draw from the same status tokens — a correctness pass as much as a design one |

### Tier 2 — meaningful polish, moderate effort

| # | Feature | Notes |
|---|---|---|
| 5 | Toast confirmations + optimistic UI for approve/reject/submit actions | |
| 6 | Notification center (bell + dropdown) | Needs a minimal backend list endpoint; full real-time delivery is out of scope, poll-on-interval is sufficient for v1 |
| 7 | Inline form validation (on blur/change, not only on submit) | |
| 8 | Sticky table headers + frozen first column on wide tables | |
| 9 | Row-level hover actions (icons fade in on hover) | |
| 10 | Animated dashboard counters (count-up on load) | |

### Tier 3 — nice-to-have, lower urgency

| # | Feature | Notes |
|---|---|---|
| 11 | Command palette (⌘K / Ctrl+K) | Real value once the app has enough pages/records to search; revisit priority once Units 20+ land |
| 12 | Breadcrumbs on nested HR/org pages | Most valuable once the org tree (Campus→Faculty→Department→Team) is deep |
| 13 | Table-level search/filter box | |
| 14 | Top-of-viewport navigation loading bar | |
| 15 | Dashboard sparkline/donut charts | |
| 16 | Branded 404/error page | |
| 17 | Per-route document titles + favicon | |
| 18 | Print stylesheet for exported/approved documents | Revisit once a document-generation unit exists |

---

## 3. Implementation

### 3.1 Approval-chain stepper (`components/approvals/ChainStepper.tsx`)

**Data shape expected** (from the chain-resolution endpoint, real or fixture):

```ts
type ChainStep = {
  unit_name: string;        // "Department of Computer Science"
  approver_role: string;    // "HOD"
  approver: { id: string; name: string; avatar_color: string } | null; // null = vacant
  is_acting: boolean;       // true if resolved via an ActingAssignment
  status: "completed" | "current" | "pending" | "skipped";
  decided_at: string | null;
  comment: string | null;
};
```

**Visual spec:**

- Horizontal stepper on desktop (`flex`, connecting line between nodes), vertical stack on mobile (`<md` breakpoint) — reuse the same component, switch orientation via a container query or breakpoint class, not two separate components.
- Each node: avatar (§3.2) + role label + unit name, connecting line colored by status:
  - `completed` — `bg-primary-500` line, checkmark badge over the avatar, approver name + decided date shown
  - `current` — `bg-primary-500` ring/pulse on the avatar (subtle, respects reduced-motion), "Awaiting decision" label
  - `pending` — `bg-muted` line and grayed avatar, no interaction
  - `skipped` — shown with a dashed line and a small "Skipped (self-approval)" label, not hidden — visibility into why a stage is absent matters for trust
- Vacant step (`approver: null`): render with a dashed outline avatar placeholder and "No approver assigned" in `text-destructive`, distinct from a normal pending step — this surfaces the blocking condition from the org-tree spec directly in the UI rather than only as a submission-time error.
- Acting approver (`is_acting: true`): small "Acting" badge next to the name, so it's clear this isn't the permanent role-holder.
- Clicking a completed/current node with a comment expands it inline (accordion), showing the comment text — avoids a separate page/dialog for something this small.

**Used on:** Unit 15 tracking page (`/applications/[id]`), Unit 16 approver review page, replacing whatever plain list/text currently shows stage progression.

### 3.2 Avatar component (`components/ui/Avatar.tsx`)

```tsx
const COLORS = [
  "bg-primary-100 text-primary-700",
  "bg-emerald-100 text-emerald-700",   // reuse existing secondary-green family
  "bg-amber-100 text-amber-700",
  "bg-rose-100 text-rose-700",
  "bg-violet-100 text-violet-700",
  "bg-cyan-100 text-cyan-700",
];

function colorForUser(userId: string): string {
  const hash = Array.from(userId).reduce((acc, c) => acc + c.charCodeAt(0), 0);
  return COLORS[hash % COLORS.length];
}

export function Avatar({ name, userId, size = "md" }: { name: string; userId: string; size?: "sm" | "md" | "lg" }) {
  const initials = name.split(" ").map(p => p[0]).slice(0, 2).join("").toUpperCase();
  const sizeClass = { sm: "h-6 w-6 text-xs", md: "h-8 w-8 text-sm", lg: "h-10 w-10 text-base" }[size];
  return (
    <div className={`inline-flex items-center justify-center rounded-full font-medium ${sizeClass} ${colorForUser(userId)}`}>
      {initials}
    </div>
  );
}
```

Color is deterministic per `userId` so the same person always renders the same color across every screen. If/when real profile photos are added later, `Avatar` falls back to initials only when no photo URL is present — build the `src` prop now even if unused, so this doesn't need a second pass.

**Used on:** chain stepper nodes, approver/employee names in tables, audit log entries, document uploader attribution (Unit 19), top-bar user menu.

### 3.3 Empty states (`components/ui/EmptyState.tsx`)

```tsx
<EmptyState
  icon={<Inbox className="h-10 w-10" />}
  title="No applications yet"
  description="Your submitted leave applications will show up here."
  action={{ label: "New application", href: "/applications/new" }}
/>
```

One component, reused everywhere, with per-page copy. Required coverage, each with its own icon/copy pair:

| Screen | Icon | Copy |
|---|---|---|
| Applications list (employee) | `Inbox` | "No applications yet" |
| Approvals queue (approver) | `CheckCircle2` | "Nothing pending your review" |
| Documents panel | `FileX` | "No supporting documents attached" |
| Vacant units view (org-tree spec) | `UserX` | "No vacant units — every unit has an approver" |
| Notification center | `BellOff` | "You're all caught up" |
| Search/filter with no results | `SearchX` | "No results for '{query}'" — include a "Clear filters" action here specifically |

### 3.4 Status color audit

Single source of truth, already defined in ui-context.md — this is an audit/enforcement task, not new design:

```ts
export const STATUS_STYLES = {
  pending:              "bg-amber-50 text-amber-700 border-amber-200",
  approved:             "bg-emerald-50 text-emerald-700 border-emerald-200",
  rejected:             "bg-red-50 text-red-700 border-red-200",
  correction_required:  "bg-purple-50 text-purple-700 border-purple-200",
  cancelled:            "bg-slate-100 text-slate-600 border-slate-200",
} as const;
```

Grep the codebase for any hardcoded status color (`text-orange-`, ad hoc hex values, inline conditional class strings for status) and replace with `STATUS_STYLES[status]`. This must be the only place status→color mapping is defined; the stepper (§3.1), badges, table rows, and dashboard charts all import from here.

### 3.5 Toasts + optimistic UI

- Adopt one toast primitive (21st.dev's if it has one; otherwise a small custom `Toaster` — don't introduce a second UI library for this alone).
- Approve/reject/submit/cancel actions: update local state immediately on click, show a toast confirming the action, and only revert + show an error toast if the backend call fails. Every mutating action in Units 13–19's UI gets this treatment, not just new features.
- Toast duration ~4s, dismissible, stack from one corner (bottom-right is conventional), entrance/exit per the motion tokens already defined (slide + fade).

### 3.6 Notification center

**Backend (minimal):**

```
GET /api/notifications/?unread_only=true   # poll every ~30s
POST /api/notifications/{id}/mark-read/
POST /api/notifications/mark-all-read/
```

A `Notification` model (`recipient`, `event_type`, `message`, `link`, `is_read`, `created_at`) populated by the same no-op event hooks already present in Units 16–19 — this is the first unit that actually turns those hooks into something user-visible, even before real email (separate SMTP work) exists.

**Frontend:** bell icon in the top bar with an unread-count badge; clicking opens a dropdown (not a page) listing recent notifications, each linking to the relevant application/page, with a "Mark all read" action.

### 3.7 Inline form validation

Audit the Unit 13 application form and any HR forms: validate on blur (not only on submit), show the error message directly below the field immediately, and clear it as soon as the field becomes valid again. Use the same error-state input treatment already defined in the token/component pass (`border-destructive`, `text-sm text-destructive` message).

### 3.8 Table enhancements

- `position: sticky; top: 0` headers on any table taller than one viewport (applications list, employee list, audit log).
- Frozen first column (name/title) on tables wide enough to scroll horizontally — CSS `position: sticky; left: 0` with a subtle right-side shadow/border to indicate the freeze boundary.
- Row hover: non-primary actions (edit/view/delete icons) at `opacity-0 group-hover:opacity-100 transition-opacity`, so dense tables aren't cluttered with icons on every row at rest.

### 3.9 Animated counters

Dashboard stat cards (days remaining, pending count, etc.): animate the number from 0 to its actual value over ~500–600ms on mount, using Motion's `animate()` on a `useMotionValue`. Respect `prefers-reduced-motion` — show the final value immediately rather than counting, consistent with the global `MotionConfig reducedMotion="user"` setup from the earlier motion work.

### 3.10 Tier 3 items

Implement opportunistically or defer; each is self-contained:

- **Command palette:** `cmdk` library, triggered by ⌘K/Ctrl+K, searches applications by reference number, employees by name, and static navigation targets (Settings, HR Admin, etc.). Needs a lightweight search endpoint or client-side filtering over already-fetched data for v1.
- **Breadcrumbs:** derive from the current route/org-tree position; most valuable on `/hr-admin/org/...` pages.
- **Navigation loading bar:** a thin `bg-primary-500` bar pinned to `top: 0`, driven by Next.js route-change events or a manual trigger on async page loads.
- **404/error pages:** branded, using the existing shell/typography, with a "Back to dashboard" action.
- **Document titles:** set `<title>` per route (`"Applications · LUANAR Leave"`) via Next.js metadata.
- **Print stylesheet:** `@media print` rules hiding `aside`, the top bar, and action buttons; revisit once a document-generation unit exists to know what's actually being printed.

---

## 4. Dependencies

| Package | Used for | New? |
|---|---|---|
| `motion` | Stepper pulse, counters, toast transitions | Already added in the earlier motion pass |
| `cmdk` | Command palette (Tier 3) | New, only if/when Tier 3 is built |
| None else required | Avatars, empty states, stepper, toasts, tables are all plain React/Tailwind | |

---

## 5. Verification checklist

**Stepper**
- [ ] Renders correctly for chains of varying length (2-stage admin, 4-stage academic).
- [ ] Vacant and acting-approver states are visually distinct from normal pending/completed states.
- [ ] Skipped (self-approval) stages are shown, not hidden, with a clear label.
- [ ] Horizontal on desktop, vertical on mobile, same component.
- [ ] Comment accordion expands/collapses without navigating away.

**Avatars**
- [ ] Same user renders the same color on every screen they appear.
- [ ] Falls back gracefully to initials when no photo exists; `src` prop is wired for future use.

**Empty states**
- [ ] Every list/table identified in §3.3 has its defined empty state, not a blank area or raw "No data."
- [ ] Search/filter empty state includes a working "Clear filters" action.

**Status colors**
- [ ] No hardcoded status color remains outside `STATUS_STYLES`; stepper, badges, table rows, and dashboard all draw from it.

**Toasts/optimistic UI**
- [ ] Approve/reject/submit/cancel show immediate UI feedback, with correct rollback + error toast on backend failure.

**Notifications**
- [ ] Bell badge count matches unread notifications; mark-read and mark-all-read work; links navigate to the correct application/page.

**Forms**
- [ ] Validation errors appear on blur and clear on correction, not only after a failed submit.

**Tables**
- [ ] Sticky headers and frozen first column work correctly on scroll, on the applications and employee list tables.
- [ ] Hover-only action icons don't appear in the tab order in a confusing way (keyboard users can still reach them via focus, even if not hover-visible).

**Counters**
- [ ] Count-up animates on first mount only (not on every re-render); respects reduced-motion by showing the final value immediately.

**Regression**
- [ ] No existing Unit 13–19 functionality changes — this unit is additive UI, not a logic change.
- [ ] All items remain within light mode and the existing color palette; no new accent color introduced anywhere.
