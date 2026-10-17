# Unit 3 — Leave App Dashboard

read `AGENTS.md` before starting.

**This spec is written to be followed step by step, even by a developer new to the project.** Every file has an exact path. Every component has its exact props. Every API call has its exact request/response shape. Where a decision was made for you, it says so and why — you shouldn't need to guess anything while building this.

---

## 1. Goal

Build the landing dashboard for the **Leave** app — the page an employee sees immediately after clicking the "Leave Applications" card on the App Launcher. It shows their own leave balance, anything needing their attention (corrections/rejections), their recent applications, and a clear path to start a new one. It shows **only** things that belong to the Leave module — nothing about approving other people's applications, nothing about org structure, nothing about HR administration.

Every core action on this page must be reachable in **3 clicks or fewer**, counted from the moment the user lands on this dashboard (§2.5 defines exactly how clicks are counted, with a worked example for every flow).

### Assumptions (flag if wrong)

| # | Assumption |
|---|---|
| A1 | `backend/leave/` already has `LeaveApplication`, `LeaveType`, and balance logic from Units 13/14/18. This unit adds **one new read endpoint** (the dashboard summary) and **no new models**. |
| A2 | `frontend/app/(dashboard)/leave/` is the module's route root (per the System Restructure unit), with its own `layout.tsx` providing the module-scoped sidebar (per that unit's §2.5/§3.6 — "← All Apps" link plus Leave-only nav items). |
| A3 | Shared components already exist and are reused here, not rebuilt: `Card`, `Badge`, `Button`, `Dialog`, `EmptyState`, `Avatar`, `Stepper`, `BalanceRing` (from the Phase 2 UI/UX unit). If `BalanceRing` doesn't exist yet, build it as part of this unit (it's small — see §3.4). |
| A4 | "My Applications" in this dashboard means applications **this employee submitted**. It never shows applications this employee is reviewing as an approver — that belongs entirely to the Approvals app, even if this employee happens to also be an approver elsewhere in the org. |
| A5 | Leave Plans (if/when built) gets its own app/module later — this spec does not include a Plans section, even as a placeholder. |

---

## 2. Design

### 2.1 What belongs on this dashboard (and what doesn't)

This is the most important design decision in this whole unit — be strict about it.

**Belongs here (Leave module's own concern):**
- The employee's own leave balance(s)
- The employee's own applications needing attention (rejected / correction required)
- The employee's own recent applications and their status
- The employee's own in-progress drafts
- A clear way to start a new application

**Does NOT belong here — do not add these, even if it seems convenient:**
- Anything about applications this employee is approving for others (that's the Approvals app)
- Organization structure, team membership, who the approver chain is (that's the Organization app)
- Document management beyond what's attached to this employee's own applications (the Documents app owns the general document experience; this dashboard may *link into* a specific application's documents, but doesn't manage documents generally)
- HR administration content (employee lists, grade rules, etc. — that's HR Administration)
- System health, stats about other users, anything superuser/HR-admin related

If you're ever unsure whether something belongs here, ask: **"Is this about MY OWN leave, as the person taking leave?"** If not, it doesn't go on this page.

### 2.2 Page layout (top to bottom)

```
┌─────────────────────────────────────────────────────────┐
│  Leave Applications                    [+ New Application]│  ← page header + primary CTA
│  Welcome back, {first name}                                │
├─────────────────────────────────────────────────────────┤
│  ⚠ Needs Your Attention (only rendered if non-empty)      │  ← §2.3
│  [application card] [application card]                    │
├─────────────────────────────────────────────────────────┤
│  Your Balance                                              │  ← §2.4
│  [BalanceRing] [BalanceRing] [BalanceRing]  (per leave type)│
├─────────────────────────────────────────────────────────┤
│  Continue a Draft (only rendered if non-empty)             │  ← §2.6
│  [draft card] [draft card]                                 │
├─────────────────────────────────────────────────────────┤
│  Recent Applications                    [View all →]       │  ← §2.7
│  [application row] [application row] [application row]     │
└─────────────────────────────────────────────────────────┘
```

Every section that can legitimately be empty (Needs Attention, Drafts) is **hidden entirely** when empty — it does not render as an empty card. This keeps the dashboard clean for the common case (nothing needs attention, no drafts in progress).

### 2.3 "Needs Your Attention" section

Shows applications in `rejected` or `correction_required` status. This section exists specifically so these can't be missed — they're the one thing on this dashboard that represents the employee being blocked from something.

Each card shows: leave type, dates, a `Badge` in the matching status color (purple for correction required, red for rejected per `STATUS_STYLES`), and a short reason excerpt (first ~60 characters of the approver's comment, truncated). The whole card is clickable → goes directly to `/leave/applications/{id}/edit` (the Unit 17 edit/resubmit page), **not** the read-only tracking page — since the entire point of this card is "you need to act," the click should land them somewhere they can act, not somewhere they have to click again to find the edit button.

### 2.4 Balance section

One `BalanceRing` per leave type the employee has an entitlement for (typically Annual, Sick, maybe others per LUANAR's rules). Each ring shows `used / total` with the numeric values beside it, per the Phase 2 spec's design (§3.3 there). If there are more than 4 leave types, show the top 4 by total entitlement and a "View all" link — but for most employees this will just be 2-3 types, no overflow handling needed in practice.

This section is **read-only display** — no actions live here.

### 2.5 The 3-click rule — exact definitions and worked examples

**Definition: a "click" is any action that navigates the user somewhere or submits something — a button press, a link, a card click.** Filling in individual form fields does NOT count as a click for this rule; typing into an input or selecting a dropdown value is normal form interaction, not a navigation step. The rule governs *how many distinct screens/actions* stand between the user and their goal, not how many fields a form has.

Every core flow is counted starting from the moment the user lands on this dashboard (click 0 = arriving here, not counted).

| Flow | Click 1 | Click 2 | Click 3 | Total |
|---|---|---|---|---|
| **Start a new application** | Press "New Application" → lands on the form | *(user fills form, not a counted click)* Press "Submit" | — | **2 clicks** |
| **View a specific application's status** | Click its card/row in Recent Applications → lands on `/leave/applications/[id]` tracking page | — | — | **1 click** |
| **Resume a draft** | Press "Continue" on a draft card → lands directly in the edit form, pre-filled | *(fill remaining fields)* Press "Save" or "Submit" | — | **2 clicks** |
| **Fix a rejected/correction-required application and resubmit** | Click the card in "Needs Your Attention" → lands directly on the edit form | *(make edits)* Press "Resubmit" | — | **2 clicks** |
| **Cancel an application** | Click its row in Recent Applications → lands on tracking page | Press "Cancel Application" → opens confirm dialog | Confirm in the dialog | **3 clicks** |

Every flow above is at or under 3 — **cancellation is the tightest one, at exactly 3**, and it's the one place in this spec you must not add an extra step (e.g. don't route cancellation through a separate "manage" page first — the Cancel action must be directly on the tracking page itself, per Unit 18's existing design).

**Rule for anyone adding a new action to this dashboard later:** before adding a step, count the clicks for the resulting flow using this same method. If it exceeds 3, the action needs a shortcut added directly on the dashboard (a card, a button) rather than requiring the user to drill down through an intermediate page first.

### 2.6 "Continue a Draft" section

Shows applications in `draft` status (started but not yet submitted, per Unit 13). Each card: leave type (or "Untitled draft" if not yet selected), dates if set, last-edited relative time (reuse the `relativeTime` helper from Phase 2 §3.8), and a "Continue" button. Clicking anywhere on the card (not just the button) goes to `/leave/applications/{id}/edit` — one click, straight into the form, per §2.5.

### 2.7 "Recent Applications" section

The 5 most recent applications **regardless of status** (including ones already shown in "Needs Attention" above — it's fine for an application to appear in both sections; Needs Attention is for urgency, Recent is for a general overview). Each row: leave type, date range, status `Badge`, submitted date. Clicking a row → `/leave/applications/{id}` (the read-only tracking page, since from here the user is most likely just checking status, not necessarily acting — this is different from the Needs Attention section, which routes straight to edit because action is the whole point there).

A "View all →" link at the top-right of this section goes to `/leave/my-applications` — a full, paginated/filterable list page. **This full list page is explicitly out of scope for this unit** — note it as a follow-up if you want it built separately, or fold it into this unit if you'd rather build it now (flag which you want).

---

## 3. Implementation

### 3.1 Backend — one new endpoint

**File:** `backend/leave/views.py` (add to the existing file — don't create a new one for one endpoint)

```
GET /api/leave/dashboard/
```

Returns everything this page needs in **one call** — don't make the frontend fire 4 separate requests for balance/needs-attention/drafts/recent, since that's slower and more code for no benefit.

```python
# backend/leave/services.py — add this function near the other leave services

def get_dashboard_data(user) -> dict:
    applications = LeaveApplication.objects.filter(employee=user).select_related("leave_type")

    needs_attention = applications.filter(
        status__in=["rejected", "correction_required"]
    ).order_by("-updated_at")[:5]

    drafts = applications.filter(status="draft").order_by("-updated_at")[:5]

    recent = applications.exclude(status="draft").order_by("-created_at")[:5]

    balances = get_balances_for_employee(user)  # reuses the existing Unit 14/18 balance service — do not reimplement balance math here

    return {
        "needs_attention": [_serialize_summary(a) for a in needs_attention],
        "drafts": [_serialize_summary(a) for a in drafts],
        "recent": [_serialize_summary(a) for a in recent],
        "balances": balances,
    }

def _serialize_summary(application) -> dict:
    return {
        "id": str(application.id),
        "leave_type": application.leave_type.name if application.leave_type else None,
        "start_date": application.start_date,
        "end_date": application.end_date,
        "status": application.status,
        "updated_at": application.updated_at,
        "created_at": application.created_at,
        "last_comment_excerpt": _latest_comment_excerpt(application),  # only needed for needs_attention, fine to compute for all
    }
```

**Response shape** (what the frontend receives):

```json
{
  "balances": [
    { "leave_type": "Annual Leave", "used": 9, "total": 21 },
    { "leave_type": "Sick Leave", "used": 2, "total": 10 }
  ],
  "needs_attention": [
    {
      "id": "uuid-here",
      "leave_type": "Annual Leave",
      "start_date": "2026-11-03",
      "end_date": "2026-11-07",
      "status": "correction_required",
      "last_comment_excerpt": "Please attach the medical certificate...",
      "updated_at": "2026-10-12T09:15:00Z"
    }
  ],
  "drafts": [ /* same shape, status: "draft" */ ],
  "recent": [ /* same shape, any status */ ]
}
```

**View:**

```python
# backend/leave/views.py

class LeaveDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = get_dashboard_data(request.user)
        return Response(data)
```

**URL:** add to `backend/leave/urls.py`:

```python
path("dashboard/", LeaveDashboardView.as_view(), name="leave-dashboard"),
```

### 3.2 Frontend — data fetching hook

**File:** `frontend/lib/leave/useLeaveDashboard.ts`

```ts
export type LeaveDashboardData = {
  balances: { leave_type: string; used: number; total: number }[];
  needs_attention: ApplicationSummary[];
  drafts: ApplicationSummary[];
  recent: ApplicationSummary[];
};

export type ApplicationSummary = {
  id: string;
  leave_type: string | null;
  start_date: string | null;
  end_date: string | null;
  status: "draft" | "pending" | "approved" | "rejected" | "correction_required" | "cancelled";
  last_comment_excerpt: string | null;
  updated_at: string;
  created_at: string;
};

export function useLeaveDashboard() {
  // use whatever data-fetching pattern the rest of the project already uses
  // (e.g. a shared `useApi` hook, SWR, or React Query — match the existing
  // pattern from Unit 15/16's tracking/approval pages, don't introduce a new one)
  return useApi<LeaveDashboardData>("/api/leave/dashboard/");
}
```

**If the project doesn't have a shared `useApi` hook yet**, check how Unit 15's tracking page fetches its data and copy that exact pattern — consistency with existing code matters more than which library is "better."

### 3.3 Frontend — the page itself

**File:** `frontend/app/(dashboard)/leave/page.tsx`

```tsx
"use client";

import { useLeaveDashboard } from "@/lib/leave/useLeaveDashboard";
import { NeedsAttentionSection } from "@/components/leave/NeedsAttentionSection";
import { BalanceSection } from "@/components/leave/BalanceSection";
import { DraftsSection } from "@/components/leave/DraftsSection";
import { RecentApplicationsSection } from "@/components/leave/RecentApplicationsSection";
import { Button } from "@/components/ui/Button";
import { useRouter } from "next/navigation";

export default function LeaveDashboardPage() {
  const { data, isLoading, error } = useLeaveDashboard();
  const router = useRouter();

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Leave Applications</h1>
          <p className="text-muted-foreground">Welcome back</p>
        </div>
        <Button onClick={() => router.push("/leave/applications/new")}>
          + New Application
        </Button>
      </div>

      {isLoading && <DashboardSkeleton />}
      {error && <DashboardErrorState />}

      {data && (
        <>
          {data.needs_attention.length > 0 && (
            <NeedsAttentionSection applications={data.needs_attention} />
          )}

          <BalanceSection balances={data.balances} />

          {data.drafts.length > 0 && (
            <DraftsSection drafts={data.drafts} />
          )}

          <RecentApplicationsSection applications={data.recent} />
        </>
      )}
    </div>
  );
}
```

Note the `data.needs_attention.length > 0 &&` and `data.drafts.length > 0 &&` guards — this is what implements "hide the section entirely when empty" from §2.2. Don't render `<NeedsAttentionSection applications={[]} />` and let the component itself decide to render nothing — keep the empty-check at the page level so it's obvious at a glance which sections are conditional.

### 3.4 Frontend — `BalanceRing` component (build only if it doesn't already exist)

**File:** `frontend/components/ui/BalanceRing.tsx`

```tsx
type BalanceRingProps = {
  used: number;
  total: number;
  label: string;
};

export function BalanceRing({ used, total, label }: BalanceRingProps) {
  const remaining = total - used;
  const percentage = total > 0 ? (used / total) * 100 : 0;
  const circumference = 2 * Math.PI * 40; // radius = 40
  const offset = circumference - (percentage / 100) * circumference;

  return (
    <div className="flex flex-col items-center gap-2 rounded-xl border bg-white p-6 shadow-sm">
      <svg width="100" height="100" viewBox="0 0 100 100">
        <circle cx="50" cy="50" r="40" fill="none" stroke="var(--color-muted)" strokeWidth="8" />
        <circle
          cx="50" cy="50" r="40" fill="none"
          stroke="var(--color-primary-500)" strokeWidth="8"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          transform="rotate(-90 50 50)"
        />
        <text x="50" y="50" textAnchor="middle" dominantBaseline="middle" className="text-lg font-semibold fill-current">
          {remaining}
        </text>
      </svg>
      <div className="text-center">
        <div className="text-sm font-medium">{label}</div>
        <div className="text-xs text-muted-foreground">{used} of {total} days used</div>
      </div>
    </div>
  );
}
```

### 3.5 Frontend — the four section components

Each is a small, focused component. Build them in this order (each is straightforward once the one before it exists, since they share the same card/row patterns):

**`frontend/components/leave/NeedsAttentionSection.tsx`**

```tsx
export function NeedsAttentionSection({ applications }: { applications: ApplicationSummary[] }) {
  const router = useRouter();
  return (
    <section>
      <h2 className="mb-3 text-lg font-semibold">Needs Your Attention</h2>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {applications.map((app) => (
          <Card
            key={app.id}
            className="cursor-pointer p-4 hover:shadow-md"
            onClick={() => router.push(`/leave/applications/${app.id}/edit`)}
          >
            <Badge tone={app.status === "rejected" ? "red" : "purple"}>
              {app.status === "rejected" ? "Rejected" : "Correction Required"}
            </Badge>
            <div className="mt-2 font-medium">{app.leave_type ?? "Leave application"}</div>
            <div className="text-sm text-muted-foreground">
              {formatDateRange(app.start_date, app.end_date)}
            </div>
            {app.last_comment_excerpt && (
              <p className="mt-2 text-sm text-muted-foreground line-clamp-2">
                "{app.last_comment_excerpt}"
              </p>
            )}
          </Card>
        ))}
      </div>
    </section>
  );
}
```

**`frontend/components/leave/BalanceSection.tsx`** — maps `balances` into `BalanceRing`s in a `flex flex-wrap gap-6` row.

**`frontend/components/leave/DraftsSection.tsx`** — same card pattern as Needs Attention, but navigates to `/leave/applications/{id}/edit` directly (no intermediate confirmation), with a "Continue" label on the card instead of a status badge, plus the relative "last edited" time.

**`frontend/components/leave/RecentApplicationsSection.tsx`** — a `Table` (reuse the existing shared `Table` component), one row per application, status `Badge` per `STATUS_STYLES`, row click → `/leave/applications/{id}` (tracking page, not edit — per §2.7). Include the "View all →" link in the section header, pointing at `/leave/my-applications` (build that page now or stub it as a TODO — your call, flagged in §2.7).

### 3.6 Loading and error states

`DashboardSkeleton`: reuse the shared `Skeleton` component, sized to roughly match the real layout (a few skeleton rectangles where the balance rings and cards will be) — don't just show a spinner, per the Phase-1 UI/UX conventions already established.

`DashboardErrorState`: a simple centered message — "Couldn't load your dashboard" with a "Retry" button that re-fetches.

### 3.7 Empty states (genuinely new user, zero applications ever)

If `recent`, `drafts`, and `needs_attention` are **all** empty (a brand new employee who's never submitted anything), the Recent Applications section still renders (it's the one section that's always shown), but uses the `EmptyState` component instead of a table:

```tsx
<EmptyState
  icon={<Inbox className="h-10 w-10" />}
  title="No applications yet"
  description="When you submit a leave application, it'll show up here."
  action={{ label: "New Application", onClick: () => router.push("/leave/applications/new") }}
/>
```

---

## 4. Dependencies

**No new packages.** Uses existing React/Next.js, Tailwind, Lucide icons, and whatever data-fetching pattern Units 15/16 already established. `BalanceRing` is plain SVG, no charting library needed.

---

## 5. Verification checklist

**Scoping (most important — check this first)**
- [ ] Nothing on this page shows applications the employee is *approving* for others, even if they're also an approver elsewhere.
- [ ] Nothing on this page shows org structure, team membership, or HR-admin content.
- [ ] Every piece of data shown is scoped to `employee=request.user` on the backend — verify by checking as two different employee accounts and confirming each sees only their own data.

**3-click rule**
- [ ] Starting a new application takes exactly 2 clicks (New Application → Submit), per §2.5.
- [ ] Viewing an application's status takes exactly 1 click from this dashboard.
- [ ] Resuming a draft takes exactly 2 clicks (Continue → Save/Submit).
- [ ] Fixing and resubmitting a rejected/correction-required application takes exactly 2 clicks (card click → Resubmit) — confirm the Needs Attention card goes straight to the **edit** page, not the tracking page first.
- [ ] Cancelling an application takes exactly 3 clicks (row → Cancel → Confirm) and no more.

**Sections**
- [ ] "Needs Your Attention" is completely absent from the page (not an empty card) when there's nothing rejected/correction-required.
- [ ] "Continue a Draft" is completely absent when there are no drafts.
- [ ] Balance rings show correct used/total per leave type, matching what Unit 14/18's balance logic actually computes.
- [ ] Recent Applications shows the 5 most recent, any status, correctly ordered by most recent first.

**States**
- [ ] Loading state shows a layout-matching skeleton, not a bare spinner.
- [ ] Error state offers a working Retry.
- [ ] A brand-new employee with zero applications sees the EmptyState with a working "New Application" action, not a broken/blank table.

**Regression**
- [ ] The dashboard endpoint reuses the existing balance service (no duplicated balance-calculation logic).
- [ ] No changes to Unit 13/14/17/18's existing endpoints or business logic — this unit only adds the one new dashboard-summary endpoint.
