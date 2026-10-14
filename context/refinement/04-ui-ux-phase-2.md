# Unit — UI/UX Phase 2 (Calendar, Forms, Bulk Actions, Accessibility)

read `context/AGENTS.md` before starting

## 1. Goal

Add a second wave of UI/UX features beyond the first polish pass: a team leave calendar with conflict detection for approvers, form-quality improvements (multi-step, autosave, smart defaults, undo), small interaction details (relative timestamps, contextual help, a what's-new popover), bulk operations for HR, and accessibility-as-polish items. Each item ships independently.

### Assumptions (flag if wrong)

| # | Assumption |
|---|---|
| A1 | Light mode, existing tokens, Lucide icons only — same constraints as every other unit in this pass. |
| A2 | The team leave calendar (§3.1-3.2) needs a way to know "who is on this employee's team" — this spec assumes that comes from the org-tree blueprint's `OrgUnit`/home-unit model. If that unit isn't built yet, the calendar can be built against a simpler "same department" grouping as a fallback and upgraded later. |
| A3 | "Conflict" in §3.2 means overlapping approved-or-pending leave for members of the same team/unit, not a hard business rule — this spec treats it as a visual flag for the approver to consider, not an automatic block, unless you want it to be a hard constraint (flag if so). |
| A4 | Stepper, Avatar, Toast, EmptyState, and Dialog components from the earlier polish unit already exist and are reused here, not rebuilt. |

### Out of scope

Resource/room booking (this is leave visibility only), a fully drag-and-drop calendar editor, real-time multi-user collaborative editing of a draft form (autosave is single-user), a full in-app changelog/CMS for the what's-new popover (content is a small static/config-driven list, not an authored feed).

---

## 2. Design — priority tiers

### Tier 1 — new, high-value feature

| # | Feature | Why first |
|---|---|---|
| 1 | Team leave calendar | Genuinely new capability, not polish on existing UI — directly supports approver decision-making |
| 2 | Conflict detection in the calendar | Builds directly on #1, low additional effort once the calendar exists |

### Tier 2 — form quality

| # | Feature | Notes |
|---|---|---|
| 3 | Leave balance as a progress ring | Small, high visual payoff, touches the dashboard and application form |
| 4 | Multi-step application form with Stepper | Reuses the existing Stepper component, not a new pattern |
| 5 | Autosave drafts | Needs a draft-persistence endpoint; see §3.5 |
| 6 | Smart defaults (last-used leave type, next working day) | Small backend + frontend change |
| 7 | Undo toast on cancel | Needs a short grace-period pattern on the backend |

### Tier 3 — interaction and discoverability details

| # | Feature | Notes |
|---|---|---|
| 8 | Relative timestamps with absolute-on-hover | Pure frontend, applies broadly (audit log, notifications, stepper timestamps) |
| 9 | Inline contextual help icons | Content-authoring overhead (someone has to write the help text) more than engineering effort |
| 10 | "What's new" popover | Needs a small config/content source, decide format before building |

### Tier 4 — operational and accessibility

| # | Feature | Notes |
|---|---|---|
| 11 | Multi-select + sticky bulk-action bar (HR employee list, approver queue) | Needs backend bulk-action endpoints, not just frontend selection UI |
| 12 | Visible focus states everywhere | Audit task across all existing components, not a new component |
| 13 | Skip-to-content link | One-line addition |
| 14 | Blur-up / fade-in for images | Only matters once real photos/thumbnails exist (currently using initials avatars — low priority until then) |

---

## 3. Implementation

### 3.1 Team leave calendar (`components/calendar/TeamLeaveCalendar.tsx`)

**Data shape:**

```ts
type CalendarEntry = {
  employee: { id: string; name: string; avatar_color: string };
  start_date: string;
  end_date: string;
  leave_type: string;
  status: "pending" | "approved"; // rejected/cancelled entries are excluded entirely
};

type TeamCalendarResponse = {
  unit_name: string;
  month: string;        // "2026-10"
  entries: CalendarEntry[];
};
```

**Backend:** `GET /api/calendar/team/?unit_id={id}&month=2026-10` — returns all approved and pending leave for members of the given unit (team/department, per the org-tree model) within that month. Scoped by the same access policy as the approval chain: an approver only sees calendars for units within their actual approval scope, not arbitrary units.

**Frontend:**

- Month-grid layout, one row per team member (not per day) — a Gantt-style horizontal bar per person showing their leave span(s) that month, colored by leave type using the existing status/leave-type color tokens.
- Approved entries: solid bar. Pending entries: striped/hatched bar (visually distinct from approved, since a pending request isn't guaranteed to happen).
- Month navigation (prev/next), defaulting to the current month.
- Avatar (reused component) next to each row's name.
- Empty state (reused component) when a unit has no team members or no leave this month: "No leave scheduled this month."

**Where it's used:** embedded on the approver review page (Unit 16) as supporting context when reviewing a request — "here's who else on this team is out around this time" — and optionally as its own page under HR/manager views for forward planning.

### 3.2 Conflict detection

```ts
function detectConflicts(entries: CalendarEntry[], threshold = 2): ConflictRange[] {
  // for each day, count overlapping approved+pending entries;
  // flag any day where count > threshold as a conflict day
}
```

- `threshold` is the maximum number of simultaneously-out team members considered normal — configurable per unit if needed, otherwise a sensible system default (e.g. more than 30% of the unit out at once).
- Flagged days render with a subtle warning background stripe across the calendar grid (using the existing amber/warning token, not a new color) rather than altering individual bars.
- On the approver review page specifically, if the request being reviewed would itself push a day into conflict, show an inline warning near the Approve button: "Approving this would mean 3 of 5 team members are out on Oct 14." — informational, not a block, per A3.

### 3.3 Leave balance progress ring (`components/ui/BalanceRing.tsx`)

```tsx
<BalanceRing used={9} total={21} label="Annual leave" />
```

Small SVG radial progress (circle with a stroke-dasharray trick, no chart library needed for something this simple), using `primary-500` for the filled arc and `muted` for the track. Pair with the existing numeric display, don't replace it — "12 of 21 days remaining" as text next to the ring, not instead of it.

**Used on:** dashboard stat cards, the leave application form (showing remaining balance for the selected leave type as the employee fills the form).

### 3.4 Multi-step application form

Reuse the existing `Stepper` component (from the chain-stepper unit) in its horizontal `size="sm"` form, non-interactive except for completed/current steps being clickable to jump back:

```
Step 1: Dates & leave type
Step 2: Reason & details
Step 3: Supporting documents (if required — skip entirely if not, via the Stepper's existing skipped status)
Step 4: Review & submit
```

Each step is its own form section; validation runs per-step (don't let the user advance with invalid data in the current step), with all data held in form state until final submit — no partial submission to the backend until step 4, unless autosave (§3.5) is also built, in which case autosave and step-advancement are independent concerns.

### 3.5 Autosave drafts

- Backend: a `LeaveApplicationDraft` model (or reuse `LeaveApplication` with a `status="draft"` state, if that already exists per Unit 13) with a simple `PATCH /api/leave/applications/draft/` endpoint, debounced client-side (~2s after the last change).
- Frontend: a small status indicator near the form header — "Saving…" → "Saved" (checkmark, fades out after ~2s) → stays silent until the next change. Use a toast only for save *failures*, not for every successful autosave (too noisy).
- On page reload/return, the draft is fetched and the form pre-fills from it.

### 3.6 Smart defaults

- Backend: an endpoint or field on the application-form-init response returning the employee's most-recently-used leave type and their balance per type.
- Frontend: pre-select that leave type in the form (still changeable), and default the start-date picker to the next working day (skip weekends; holiday-awareness only if a holiday calendar already exists elsewhere in the system — don't build one just for this default).

### 3.7 Undo on cancel

- Backend: cancellation takes effect after a short grace window (e.g. actually process the cancellation via a delayed Django-Q2 task scheduled ~8 seconds out) OR is immediate but reversible via a dedicated `POST /api/leave/applications/{id}/undo-cancel/` endpoint if the grace window has a cleaner implementation that way — pick whichever fits the existing Unit 18 cancellation flow with less disruption.
- Frontend: clicking Cancel immediately shows a toast — "Application cancelled — Undo" with a visible countdown or a fixed 5s action window — rather than a blocking confirm dialog beforehand.

### 3.8 Relative timestamps (`lib/format.ts`)

```ts
export function relativeTime(iso: string): string { /* "2 hours ago", "3 days ago", falls back to a date beyond ~7 days */ }
```

Wrap any rendered relative timestamp in a `title` attribute (or a proper Tooltip component if one already exists) showing the full absolute timestamp on hover. Apply to: audit log entries, notification center items, stepper `decided_at` values, document "uploaded" timestamps.

### 3.9 Inline contextual help

`components/ui/HelpTooltip.tsx` — a small `?` icon (Lucide `HelpCircle`), `h-4 w-4 text-muted-foreground`, opens a short popover on click (not hover-only, for touch/mobile support) containing 1-2 sentences of help copy. Content is passed as a prop per usage, not centrally managed — identify the 3-5 genuinely non-obvious fields across the application form and HR screens worth adding this to, rather than adding it everywhere by default (over-use dilutes the signal).

### 3.10 "What's new" popover

- Content source: a simple static JSON/config file in the frontend repo (`lib/whats-new.ts`), updated manually per release — no CMS needed at this scale.
- Shown once per user per new entry: track `last_seen_whats_new_version` in local storage or a small user-preference field; a small dot badge on the bell icon (or a separate icon) indicates unseen items.

### 3.11 Multi-select + bulk actions

- Frontend: checkbox column on the HR employee list and approver's pending-applications table; selecting any row reveals a sticky bar pinned to the bottom of the viewport with a count and action buttons ("3 selected — Export", "3 selected — Approve all").
- Backend: bulk-action endpoints are **not** just a loop of individual-record endpoint calls from the frontend — implement real bulk endpoints (`POST /api/leave/applications/bulk-approve/` with a list of IDs) so the backend can apply them atomically and audit them as one action, consistent with how individual approvals are already audited.
- "Approve all" specifically should still show a confirmation dialog listing exactly which applications will be affected before committing — bulk-approving leave is higher-stakes than a bulk-export.

### 3.12 Focus states audit

Audit task, not new component work: verify every interactive element (buttons, inputs, table rows with actions, nav items, dialog close buttons, the calendar's day cells if interactive) has a visible `focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2` or equivalent, consistent with the global baseline already defined in the design-token pass. Fix any component found missing it.

### 3.13 Skip-to-content link

```tsx
<a href="#main-content" className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-primary-500 focus:px-4 focus:py-2 focus:text-white">
  Skip to content
</a>
```

Placed as the very first focusable element in the root layout, with `id="main-content"` on the main content card from the floating-shell layout.

### 3.14 Blur-up image loading

Deferred — only relevant once real profile photos or document thumbnails exist (currently avatars are initials-only, per the earlier polish unit). Revisit when that changes; no implementation needed now.

---

## 4. Dependencies

| Package | Used for | New? |
|---|---|---|
| None required for the calendar, progress ring, help tooltip, relative timestamps | Plain React/Tailwind/SVG | — |
| Existing `motion` | Autosave indicator fade, undo toast | Already present |
| Existing Django-Q2 | Delayed cancellation processing (§3.7, if that approach is chosen) | Already present |

---

## 5. Verification checklist

**Team leave calendar**
- [ ] Shows correct team membership and leave entries for the selected unit and month.
- [ ] Pending vs. approved entries are visually distinct.
- [ ] Access is correctly scoped — an approver cannot view a calendar for a unit outside their approval scope.
- [ ] Conflict-day striping appears only when the configured threshold is exceeded, and updates correctly as the reviewed request is hypothetically applied.
- [ ] Empty state renders correctly for a unit with no team members or no leave that month.

**Forms**
- [ ] Multi-step form correctly validates per-step and skips the documents step when not required (leave-type dependent).
- [ ] Autosave triggers after the debounce window, shows Saved/Saving correctly, and restores a draft correctly on reload.
- [ ] Smart defaults pre-fill correctly but remain fully editable.
- [ ] Undo on cancel correctly reverses the cancellation within the grace window, and the cancellation takes effect correctly once the window passes.

**Details**
- [ ] Relative timestamps show correctly and display the full timestamp on hover, across all four listed surfaces (audit log, notifications, stepper, documents).
- [ ] Help tooltips open on click (not hover-only) and are legible on mobile.
- [ ] What's-new popover shows only unseen entries and correctly marks them seen.

**Bulk actions**
- [ ] Sticky bar appears/disappears correctly with selection state.
- [ ] Bulk endpoints apply atomically and produce correct individual audit entries, not one opaque "bulk action" entry.
- [ ] Bulk-approve shows the confirmation list before committing.

**Accessibility**
- [ ] Every interactive element has a visible focus state, verified by keyboard-only navigation across each major page.
- [ ] Skip-to-content link is invisible until focused, then correctly jumps to and focuses the main content region.

**Regression**
- [ ] No existing Unit 13-19 or prior polish-unit functionality changes — this unit is additive.
- [ ] All items stay within light mode and the existing color palette.
