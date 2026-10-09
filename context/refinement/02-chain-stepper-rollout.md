# Unit — Chain Stepper Component & Rollout

read `context/AGENTS.md` before starting

## 1. Goal

Build one reusable `Stepper` component that visualizes any ordered sequence of stages with status (completed/current/pending/skipped/blocked), and apply it everywhere in the system a multi-step sequence is currently shown as plain text or a list — not just the leave-approval chain, but every other sequential process in the app that would benefit from the same treatment.

### Assumptions (flag if wrong)

| # | Assumption |
|---|---|
| A1 | The approval-chain stepper described in the UI/UX polish unit (§3.1 there) and this unit's `Stepper` are the same component — this spec supersedes that section with the full generalized design and the complete rollout list. |
| A2 | "Everywhere it can be implemented" means every *sequential, ordered, multi-stage* process in the app — not single-state badges (a document's `current`/`superseded`/`removed` status, for instance, is not a sequence and stays a badge, not a stepper). §2.2 draws this line explicitly per surface. |
| A3 | Light mode, existing tokens, Lucide icons only — same constraints as every other unit in this pass. |

### Out of scope

Editing/reordering a sequence from the stepper itself (display-only in every case below except the document-upload wizard, which is interactive by nature), a generic "workflow builder" UI — this is a display component, not a configuration tool.

---

## 2. Design

### 2.1 One component, driven entirely by data

```ts
type StepStatus = "completed" | "current" | "pending" | "skipped" | "blocked" | "error";

type Step = {
  id: string;
  label: string;              // primary text — a role, a stage name, a step name
  sublabel?: string;           // secondary text — a unit name, a person, a detail
  status: StepStatus;
  actor?: { id: string; name: string } | null;  // person associated with this step, if any
  timestamp?: string | null;   // when this step was completed/decided
  detail?: string | null;      // expandable text — a comment, a reason, extra context
  isActing?: boolean;          // shows an "Acting" badge next to actor, approval-chain specific
};

type StepperProps = {
  steps: Step[];
  orientation?: "horizontal" | "vertical" | "auto"; // "auto" = horizontal desktop, vertical mobile
  size?: "sm" | "md";
  showAvatars?: boolean;       // false where there's no person per step (e.g. onboarding checklist)
};
```

One component (`components/ui/Stepper.tsx`) consumes this shape regardless of which process it represents. Every integration point in §3 maps its own data into `Step[]` — the component itself has zero awareness of leave applications, documents, or org units.

### 2.2 Status visual language (applies everywhere the stepper is used)

| Status | Treatment |
|---|---|
| `completed` | Filled `primary-500` node, checkmark icon, connecting line to next step solid `primary-500`, actor + timestamp shown |
| `current` | Outlined `primary-500` node with a subtle pulse ring (respects reduced-motion — pulse becomes a static ring), "In progress" or context-specific label |
| `pending` | Muted gray node and line, no interaction, grayed label |
| `skipped` | Dashed node outline and dashed connecting line, small explanatory sublabel (never hidden — the reason a step is absent is itself information) |
| `blocked` | `destructive` colored node (not filled red solid — use `bg-red-50` fill with `border-red-400`, consistent with your status-color system), with a short reason, e.g. "No approver assigned" |
| `error` | Same red family as `blocked` but with an X icon instead of a dash — used specifically for rejection/failure outcomes, distinct from a structural blocker |

This table is the single definition; every integration below reuses it rather than redefining status colors locally.

### 2.3 Orientation and density

- `orientation="auto"` (default): horizontal with a connecting line on screens ≥768px, vertical stack below that. Both are the same component tree — orientation only changes flex-direction and connector placement, not the step markup.
- `size="sm"`: compact — smaller node, label only, no sublabel/timestamp shown inline (used in dense contexts like a table-embedded preview). `size="md"` (default): full detail.
- Long sequences (5+ steps) on narrow screens: vertical stack scrolls within its container rather than compressing nodes — never shrink nodes below a legible minimum to force a fit.

### 2.4 Expandable detail

Any step with a non-null `detail` (a comment, a rejection reason, extra context) is clickable/tappable to expand an inline panel directly below that node — accordion-style, not a separate dialog, since this is inline contextual information, not a distinct action.

---

## 3. Implementation — rollout across the system

For each surface, this spec defines: what sequence it represents, how its states map to `StepStatus`, and where it replaces existing plain-text/list display.

### 3.1 Leave application approval chain (primary use case)

**Surfaces:** Unit 15 tracking page (`/applications/[id]`), Unit 16 approver review page, Unit 18 cancellation-approval view.

**Mapping:**

| Approval-chain state | StepStatus |
|---|---|
| Decision recorded, approved | `completed` |
| Current pending stage | `current` |
| Not yet reached | `pending` |
| Self-approval skip (org-tree blueprint) | `skipped`, sublabel "Skipped (self-approval)" |
| Unit has no resolvable approver (org-tree blueprint) | `blocked`, sublabel "No approver assigned" |
| Decision recorded, rejected | `error`, detail = rejection comment |
| Decision recorded, correction required | `error` (same red family), detail = correction comment, sublabel "Correction required" |

`actor` = the resolved approver for that stage; `isActing` = true when resolved via an `ActingAssignment`. This replaces whatever plain list currently shows stage progression in Units 15/16/18.

### 3.2 Document version history (Unit 19)

**Surface:** the "Version history" dialog in `SupportingDocumentsPanel`.

**Mapping:** each version becomes a step — `completed` for superseded/removed versions (each shows who replaced/removed it and when, via `detail`), `current` for the active version. This is a genuine sequence (v1 → v2 → v3, replace or remove events over time), distinct from the document's single-value status badge (current/superseded/removed) shown elsewhere, which stays a badge.

### 3.3 Correction/resubmission history (Unit 17)

**Surface:** the "Changes since your decision" card on the approver review page, and the employee tracking page when an application has been resubmitted.

**Mapping:** each submission attempt is a step — original submission, correction requested, resubmitted, (repeat as needed), final decision. `detail` carries the diff summary (added/replaced/removed documents, changed fields) per Unit 17's existing diff service. Size `sm` in the compact card context, `md` on the full tracking page.

### 3.4 Leave cancellation flow (Unit 18)

**Surface:** cancellation status on the tracking page, when a cancellation request exists.

**Mapping:** Requested → (Supervisor/HOD stages from the original workflow snapshot) → Cancelled/restored, or Withdrawn immediately if the application was still pending. Reuses the same approval-chain stepper logic (§3.1) since cancellation approval walks a subset of the original chain — this is not a new component variant, just a different `Step[]` built from a different (shorter) chain.

### 3.5 Account onboarding (HR user-onboarding unit, if built)

**Surface:** an HR-facing "pending users" list/detail, showing where a newly created account is in its setup.

**Mapping:** Account created → Welcome email sent → (waiting) → Password set. This sequence has no `actor` per step (it's the same user throughout) — use `showAvatars={false}`. Useful for HR to see at a glance whether a user is stuck (temp password expired, no login yet) without reading raw timestamps.

### 3.6 HR org-unit setup checklist (org-tree blueprint, optional)

**Surface:** when HR creates a new unit (Department/Faculty/Team) via the org tree UI, a small stepper showing: Unit created → Approver assigned → (if applicable) Teams configured. Optional/lower priority — only build if the creation flow genuinely spans multiple sessions/steps in practice; if unit creation is a single form submit, this doesn't apply and should be skipped rather than forced in.

### 3.7 Explicitly NOT converted to stepper

| Surface | Why it stays as-is |
|---|---|
| Document current/superseded/removed badge (single value, not shown as history) | Single state, not a sequence — stays a `Badge` |
| Application overall status badge (Pending/Approved/Rejected/etc. shown in list/table rows) | Summary of the chain, not the chain itself — stays a `Badge` using `STATUS_STYLES`; the stepper is for the detail view, the badge is for the list view |
| Leave balance / entitlement display | Not a sequence at all |
| Notification list (UI/UX polish unit §3.6) | A feed, not an ordered process with stages |

---

## 4. Dependencies

No new packages. Built with existing Tailwind tokens, Lucide icons (`Check`, `X`, `Clock`, `AlertCircle` or similar for status icons), and Motion (already in the project) for the `current`-state pulse, respecting the existing `MotionConfig reducedMotion="user"` setup.

---

## 5. Verification checklist

**Component**
- [ ] Renders correctly for 2-step through 6+ step sequences without node compression below a legible size.
- [ ] `orientation="auto"` correctly switches between horizontal (≥768px) and vertical, same markup.
- [ ] All six `StepStatus` values render visually distinct from each other, using only the existing status/primary color tokens — no new colors introduced.
- [ ] Expandable `detail` panels open/close correctly and don't shift layout of sibling steps awkwardly.
- [ ] `current` pulse respects `prefers-reduced-motion` (static ring instead of animated pulse).
- [ ] `size="sm"` renders legibly in compact/embedded contexts (e.g. inside a card).

**Rollout — each surface**
- [ ] §3.1 Approval chain: correctly shows completed/current/pending/skipped/blocked/error across real fixture chains of varying length and branch (academic vs. administrative).
- [ ] §3.1 Vacant-unit blocked state matches the org-tree blueprint's `NoApproverAssignedError` condition exactly — if the backend reports a unit is blocked, the UI reflects it immediately, not just at submission time.
- [ ] §3.2 Document version history renders as a stepper distinct from the single-value document status badge elsewhere on the same panel.
- [ ] §3.3 Correction/resubmission history stepper matches Unit 17's existing diff data without needing new backend fields beyond what's already computed.
- [ ] §3.4 Cancellation stepper correctly shows a shortened chain for pending-withdrawal vs. the full original-chain subset for approved-leave cancellation.
- [ ] §3.5 (if built) onboarding stepper reflects real account state (temp password expired, email sent, password set) without a person-avatar per step.
- [ ] §3.7 surfaces remain badges, confirming no over-application of the stepper where a single-value status is more correct.

**Regression**
- [ ] No existing Unit 15-19 functionality changes — this is a display-layer replacement only; underlying data/endpoints are unchanged except where a surface needs a new field (e.g. `is_acting`, already covered by the org-tree blueprint's resolver).
- [ ] Removing the old plain-text/list stage display and replacing it with the stepper doesn't drop any information previously shown (comment text, timestamps, actor names all still present, just restyled).
