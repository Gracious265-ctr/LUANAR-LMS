# Unit — Leave Plans App

read `./AGENTS.md` before starting.
---

## 1. Goal

Let an employee set up a **Leave Plan** for a financial year — a leave type and intended date range, saved ahead of time with nothing submitted. As the planned start date approaches (based on a notice-period configured per leave type), the system emails the employee a reminder with a link that opens a pre-filled **draft** leave application in the existing Leave app, ready to review and submit. Separately, employees can see a team leave calendar of plans (not just actual approved leave), and unit heads (HOD, Dean, Manager, Campus Registrar) can see it scoped to their wider unit.

---

## 2. Open questions and recommendations

You explicitly asked me to flag unclear areas and recommend improvements — here they are, with the default I've built the rest of this spec around. Confirm or correct before building.

### 2.1 Registrar/unit-head scoping — generalized, not just HOD + Registrar

You named HOD (department) and Registrar (campus/area) specifically. **Recommendation: generalize this to every unit-head role in the org tree**, not just those two — Dean (faculty-wide) and Manager (admin-department-wide) get the exact same capability for free, using the same mechanism, since they're structurally identical (each oversees everyone under their unit in the org tree). This costs nothing extra to build — it's the same scoping query parametrized by "the viewer's own unit" rather than hardcoded per role — and it would be an odd, hard-to-explain gap if a Dean could see their faculty's actual leave *approvals* but not plans while an HOD could see plans.

One sub-question I can't resolve for you: **does the Institutional Registrar get institution-wide plan visibility**, given they sit outside the approval chain entirely but may still be a legitimate "I want to see what's coming up institution-wide" viewer? I've defaulted to **yes** (any unit head, walking up the same org tree used for approvals, sees everyone under their unit — Institutional Registrar's unit is the Institution itself, so they see everyone) — but confirm this is actually wanted, since it's a meaningfully broad visibility grant.

### 2.2 Sidebar — one page with a scope filter, not separate nav items per role

Literally following your description, an HOD would need extra sidebar items beyond "My Plans / Create / My Team's Plans" to see their whole department. **Recommendation: don't add role-specific sidebar items.** Keep the sidebar identical for every role — **My Plans, Create a Plan, Team Plans** — and make "Team Plans" itself scope-aware: a regular employee sees only their own team's calendar with no filter control; an HOD/Dean/Manager/Campus Registrar sees the same page with a scope dropdown ("My Team" / "Whole Department", or "My Faculty" / "This Department" for a Dean, etc.) defaulting to their own immediate unit. This keeps the sidebar consistent across every role (easier to build, easier to explain, matches the module-scoping discipline already used everywhere else) rather than growing a different sidebar per role. I've built the rest of this spec around this version — flag if you actually want literal separate nav items instead.

### 2.3 Manually applying early, not just waiting for the email

Your description only mentions the email-triggered path. **Recommendation: also let the employee click "Apply Now" on any of their own plans at any time**, not only once the system-triggered reminder fires. Forcing someone to wait for an email even when they're ready now would be bad UX and is easy to avoid — the email becomes a *nudge*, not the only path to action. I've built this in as the default; flag if you specifically want the email to be the sole trigger.

### 2.4 What happens if a plan is never acted on

Your description doesn't say what happens if the leave date arrives and the employee never clicked through. **Recommendation:** mark the plan `missed` once its start date passes with no conversion, and surface it clearly in "My Plans" (not silently dropped) — plus send one follow-up reminder partway through the notice window rather than a single email, so a missed/ignored email doesn't mean a missed leave date. Flag if you'd rather keep this simpler (single email, no follow-up, no missed-state tracking).

### 2.5 "Financial year" — confirmed

Confirmed: `FinancialYear` is a real model, created by HR (likely part of Units 2-11's parallel-track work). `LeavePlan.financial_year` is a direct FK to that existing model, no stand-in needed. Since Units 2-11 are still being built in parallel and connected at Unit 20 per the project's established pattern, this unit's `LeavePlan` migration should declare the FK against whatever the real `FinancialYear` model's app label turns out to be — if that app isn't merged in yet when this unit is built, follow the same swappable-provider/fixture approach already used for every other Unit 13-19 dependency on the parallel track, rather than inventing a parallel stand-in model specific to Plans.

### 2.6 Which leave types can even be planned

Not every leave type makes sense to plan ahead (sick leave, for instance, is rarely planned months in advance). **Recommendation:** add a `plannable: bool` field to `LeaveType` (defaults to `True` for types like Annual Leave, `False` for ones like Sick Leave) so the "Create a Plan" form only offers leave types that make sense to pre-schedule. Flag if every leave type should be plannable with no restriction.

### 2.7 Multiple plans, overlaps

Your description doesn't restrict how many plans someone can have. **Recommendation:** allow multiple plans per employee per financial year (someone might plan two separate leave blocks), with a **soft warning** (not a hard block) if a new plan's dates overlap an existing plan or an already-submitted application of theirs — since a plan isn't binding, blocking it outright would be overreach for something that's just a personal reminder tool.

### 2.8 The email link's security model

Your description implies a clickable email link that lands the user on a pre-filled draft. **Recommendation: this does not need a signed/magic token.** It's not a passwordless-login link — it's a plain deep link (`/plans/{plan_id}`) into an already-authenticated app. If the recipient isn't logged in, standard auth middleware redirects them to login first, then back to the link (the normal "redirect after login" pattern already used everywhere else in the app) — then ownership is checked the same way every other personal resource in this system is checked (`plan.employee == request.user`). No new security mechanism needed; flag if you had something more elaborate in mind.

---

## 3. Design

### 3.1 Data model shape

```
LeavePlan
  employee          FK -> User
  leave_type        FK -> LeaveType
  financial_year    FK -> FinancialYear (assumption 2.5)
  planned_start_date  Date
  planned_end_date    Date
  notes             Text, optional
  status            "upcoming" | "notified" | "missed" | "converted" | "cancelled"
  notified_at       DateTime, nullable
  follow_up_sent_at DateTime, nullable   (2.4)
  converted_application  FK -> LeaveApplication, nullable
  created_at / updated_at
```

```
LeaveType  (the registry model — Unit 06 moved it to `leave_config` and folded the
            old effective-dated LeaveRule into it, so the second field this unit
            originally added no longer exists as a separate number)
  plannable    Bool, default True                 (2.6)
  notice_days  Int, nullable                      ← days of advance notice this
                                                    type requires. The Leave
                                                    app's submission check
                                                    (Unit 14) and this plan's
                                                    reminder read the same
                                                    number: the reminder fires
                                                    when today >=
                                                    planned_start_date -
                                                    notice_days. Null means no
                                                    minimum and no reminder.
                                                    (Written when this unit
                                                    shipped as
                                                    `plan_notice_days`; Unit 06
                                                    retired the duplicate —
                                                    see
                                                    `context/refinement/06-leave-configuration-app.md`
                                                    §1.2.)
```

```
LeaveApplication  (existing model — add one field)
  source_plan        FK -> LeavePlan, nullable   ← traceability only,
                                                     set when a draft is
                                                     created from a plan
```

### 3.2 The core lifecycle

```
Employee creates a Plan (status: upcoming)
        │
        ▼
Scheduled daily check: today >= (planned_start_date - notice_days)?
        │
        ├── No  → stays "upcoming", nothing happens yet
        │
        └── Yes → email sent, status: "notified"
                  (if a follow-up window passes with no action: one
                   more reminder email, per 2.4 — status stays "notified")
                        │
                        ├── Employee clicks the email link, OR clicks
                        │   "Apply Now" manually (2.3) at any time,
                        │   from "upcoming" OR "notified" status
                        │        │
                        │        ▼
                        │   Draft LeaveApplication created, pre-filled
                        │   from the plan, source_plan set
                        │        │
                        │        ▼
                        │   Redirect to /leave/applications/{id}/edit
                        │   (the EXISTING Leave app's draft editor —
                        │    Plans app does not own this screen)
                        │        │
                        │        ▼
                        │   status: "converted" (set the moment the
                        │   draft is created, not when it's submitted —
                        │   the plan's job is done once it's handed off)
                        │
                        └── planned_start_date passes with no action
                                 │
                                 ▼
                            status: "missed" (2.4) — stays visible in
                            My Plans, not deleted, not hidden
```

The employee can also cancel/delete a plan at any time before it converts (status: "cancelled").

### 3.3 Creating a plan

Form fields: leave type (filtered to `plannable=True`), financial year (likely auto-defaulted to the current one), planned start date, planned end date, optional notes. **No document upload here** — documents belong to the eventual application, not the plan, since the plan isn't submitted and has no approval requirement to satisfy.

Soft overlap warning (2.7): on save, check for date overlap against the employee's other active plans and their own existing applications; if found, show a non-blocking inline warning ("This overlaps with your planned leave from Nov 3–7") but still allow saving.

### 3.4 My Plans (this app's dashboard/landing page)

Lands here when entering the Plans app from the launcher — zero additional clicks. Shows all the employee's own plans, grouped or sorted by status: upcoming first (soonest start date first), then notified (these are the ones needing attention — visually distinct, similar treatment to the Leave app's "Needs Your Attention" pattern), then a collapsed/lower-priority section for converted and missed/cancelled plans (history, not action items).

Each plan card: leave type, date range, status `Badge`, and an **"Apply Now"** button (2.3) on any upcoming/notified plan — one click, straight to draft creation + redirect, matching the Leave app's existing 2-click "new application" budget exactly (Apply Now → lands on pre-filled draft → Submit = 2 clicks).

A `missed` plan card shows a clear "Leave date has passed" state with no Apply Now button (the planned dates are no longer valid — recommend instead showing "Create a new plan" or "Apply for different dates" as the action, which goes to "Create a Plan" pre-filled with the same leave type).

### 3.5 Create a Plan page

A short, single-page form (not multi-step — this is a lighter-weight action than a full leave application): leave type, financial year, start/end dates, optional notes, Save button. One click to reach it from the sidebar, one click to save = **2 clicks total**, matching the Leave app's own "new application" flow weight.

### 3.6 Team Plans — the calendar

Per §2.2's recommendation, one page (`/plans/team`), scope-aware:

- **Regular employee:** calendar shows plans belonging to members of their own home unit (team or department, per the org-tree `home_unit` concept) — no scope selector shown, since there's nothing to choose between.
- **Unit head (HOD, Dean, Manager, Campus Registrar, Institutional Registrar per §2.1):** the same calendar, plus a scope dropdown defaulting to their own immediate unit, letting them widen to everything under their unit in the org tree (e.g. an HOD's default is their own department; a Dean's default is their own faculty, with an option to narrow to one department under it if useful, or stay at faculty-wide).

**Calendar visual:** a month grid, similar structure to the team-leave-calendar feature already specced in the UI/UX Phase 2 unit — but this one shows **plans**, not actual approved/pending leave. Use a visually distinct treatment from that other calendar (e.g. a dashed/outlined bar rather than solid, or a different icon) so a user who sees both calendars never confuses "someone definitely has approved leave here" with "someone is merely planning to." Each entry: employee name/avatar, leave type color-coded.

**Clicking a date:** opens an overlay `Dialog` (reusing the existing Dialog conventions, including the scrollbar-corner fix already applied to overlays) listing every plan that touches that date — employee, leave type, full date range, status. This is purely informational; no actions live in this overlay (you can't apply on someone else's behalf, obviously, and even for your own plan, the action belongs on My Plans, not buried in a team calendar overlay).

One click to reach Team Plans from the sidebar, one click on a date to see detail = **2 clicks**, well within budget.

### 3.7 The email

Subject: "Time to plan your upcoming leave" (avoid alarming/urgent-sounding language, same principle used for the earlier HR-onboarding email). Body: leave type, planned dates, a single clear button/link — "Review and apply" — pointing at `/plans/{id}` (deep link, per §2.8). If the follow-up reminder (2.4) fires, use slightly different, still calm copy ("Your planned leave is coming up — don't forget to apply").

---

## 4. Implementation

### 4.1 Backend app

```bash
cd backend
python manage.py startapp plans
```

### 4.2 Models (`backend/plans/models.py`)

```python
class LeavePlanStatus(models.TextChoices):
    UPCOMING = "upcoming"
    NOTIFIED = "notified"
    MISSED = "missed"
    CONVERTED = "converted"
    CANCELLED = "cancelled"


class LeavePlan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name="leave_plans")
    leave_type = models.ForeignKey("leave.LeaveType", on_delete=models.PROTECT)
    financial_year = models.ForeignKey("leave.FinancialYear", on_delete=models.PROTECT)  # assumption 2.5
    planned_start_date = models.DateField()
    planned_end_date = models.DateField()
    notes = models.TextField(blank=True)
    status = models.CharField(choices=LeavePlanStatus.choices, default=LeavePlanStatus.UPCOMING)
    notified_at = models.DateTimeField(null=True, blank=True)
    follow_up_sent_at = models.DateTimeField(null=True, blank=True)
    converted_application = models.ForeignKey(
        "leave.LeaveApplication", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

Migration on `leave.LeaveType`: add `plannable` (bool, default True) and `plan_notice_days` (int, null=True). Migration on `leave.LeaveApplication`: add `source_plan` (FK, null=True).

*(Superseded by Unit 06: the model now lives in `leave_config` and the reminder reads its single `notice_days` field, which the Leave app's submission validation also uses — the `plan_notice_days` column was dropped when the two numbers were folded into one.)*

### 4.3 Services (`backend/plans/services.py`)

```python
def create_plan(employee, leave_type, financial_year, start_date, end_date, notes="") -> LeavePlan:
    if not leave_type.plannable:
        raise ValueError("This leave type cannot be planned in advance.")
    plan = LeavePlan.objects.create(
        employee=employee, leave_type=leave_type, financial_year=financial_year,
        planned_start_date=start_date, planned_end_date=end_date, notes=notes,
    )
    overlap = _check_overlap(employee, start_date, end_date, exclude=plan.id)  # soft warning only, §2.7
    return plan, overlap


def convert_plan_to_draft(plan: LeavePlan) -> "LeaveApplication":
    if plan.status == LeavePlanStatus.CONVERTED:
        return plan.converted_application  # idempotent — clicking Apply Now twice doesn't create two drafts
    application = leave.services.create_draft_application(
        employee=plan.employee,
        leave_type=plan.leave_type,
        start_date=plan.planned_start_date,
        end_date=plan.planned_end_date,
        source_plan=plan,
    )  # reuses the EXISTING Unit 13 draft-creation path — do not duplicate that logic here
    plan.status = LeavePlanStatus.CONVERTED
    plan.converted_application = application
    plan.save(update_fields=["status", "converted_application"])
    return application


def resolve_scope_units(user) -> list["OrgUnit"]:
    """Per §2.1/§2.2: returns the org units whose members' plans this user can see
    on the Team Plans calendar. A regular employee gets just their own home unit.
    A unit head gets their own unit plus every descendant unit in the org tree."""
    home_unit = user.profile.home_unit
    if not _is_unit_head(user, home_unit):
        return [home_unit]
    return _unit_and_all_descendants(home_unit)  # walks the same OrgUnit tree as the approval chain
```

### 4.4 Scheduled task (`backend/plans/tasks.py`)

```python
def check_and_notify_plans():
    """Run daily via Django-Q2 schedule."""
    today = timezone.now().date()

    due = LeavePlan.objects.filter(
        status=LeavePlanStatus.UPCOMING,
        leave_type__notice_days__isnull=False,
    ).annotate(
        notify_date=ExpressionWrapper(
            F("planned_start_date") - F("leave_type__notice_days") * timedelta(days=1),
            output_field=DateField(),
        )
    ).filter(notify_date__lte=today)

    for plan in due:
        async_task("plans.tasks.send_plan_reminder_email", plan.id)
        plan.status = LeavePlanStatus.NOTIFIED
        plan.notified_at = timezone.now()
        plan.save(update_fields=["status", "notified_at"])

    # follow-up reminder (§2.4) — one extra nudge partway through, never notified twice total
    FOLLOW_UP_AFTER_DAYS = 5  # configurable in settings
    stale_notified = LeavePlan.objects.filter(
        status=LeavePlanStatus.NOTIFIED,
        follow_up_sent_at__isnull=True,
        notified_at__lte=timezone.now() - timedelta(days=FOLLOW_UP_AFTER_DAYS),
        planned_start_date__gt=today,
    )
    for plan in stale_notified:
        async_task("plans.tasks.send_plan_followup_email", plan.id)
        plan.follow_up_sent_at = timezone.now()
        plan.save(update_fields=["follow_up_sent_at"])

    # missed plans (§2.4)
    LeavePlan.objects.filter(
        status__in=[LeavePlanStatus.UPCOMING, LeavePlanStatus.NOTIFIED],
        planned_start_date__lt=today,
    ).update(status=LeavePlanStatus.MISSED)
```

Register with Django-Q2's scheduler (`Schedule.objects.create(func="plans.tasks.check_and_notify_plans", schedule_type=Schedule.DAILY)`), same pattern as any other recurring job in this project.

### 4.5 API endpoints (`backend/plans/views.py`, `urls.py`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/plans/` | This employee's own plans (My Plans) |
| POST | `/api/plans/` | Create a plan |
| GET | `/api/plans/{id}/` | One plan's detail (used by the emailed deep link, auth + ownership checked) |
| DELETE | `/api/plans/{id}/` | Cancel a plan (only while upcoming/notified) |
| POST | `/api/plans/{id}/apply/` | Apply Now — calls `convert_plan_to_draft`, returns the new application's ID for the frontend to redirect to |
| GET | `/api/plans/team/?scope_unit_id={id}&month=2026-11` | Team Plans calendar data, scoped per `resolve_scope_units` |
| GET | `/api/plans/scope-options/` | For unit heads only — returns the list of units they're allowed to widen the scope dropdown to (§3.6) |

### 4.6 Frontend

```
frontend/app/(dashboard)/plans/
  page.tsx                 // My Plans — this app's landing page
  new/page.tsx              // Create a Plan
  team/page.tsx              // Team Plans calendar
  [id]/page.tsx              // deep-link target from the email — resolves and
                              // immediately redirects to either the Apply flow
                              // or shows the plan if not yet actionable
  layout.tsx                 // module-scoped shell: "← All Apps" + My Plans /
                              // Create a Plan / Team Plans nav, per §2.2

frontend/components/plans/
  PlanCard.tsx
  CreatePlanForm.tsx
  TeamPlansCalendar.tsx
  PlanDetailOverlay.tsx       // the Dialog shown on calendar date click
  ScopeSelector.tsx           // dropdown shown only for unit heads
```

Sidebar nav array (consolidate into one shared config, per the earlier Leave sidebar fix's recommendation — don't hardcode per page):

```ts
export const PLANS_NAV_ITEMS = [
  { label: "My Plans", href: "/plans", icon: CalendarCheck },
  { label: "Create a Plan", href: "/plans/new", icon: Plus },
  { label: "Team Plans", href: "/plans/team", icon: Users },
];
```

### 4.7 App Launcher integration

Add to the frontend's `APPS_REGISTRY` (from the System Restructure unit):

```ts
plans: { name: "Leave Plans", description: "Plan your upcoming leave ahead of time", icon: CalendarClock, route: "/plans" },
```

Add `can_access_plans(user)` (true for every employee — this app has no restricted-role gate, unlike HR Administration) and a badge helper to `backend/launcher/services.py`:

```python
def _plans_badge(user) -> dict | None:
    count = LeavePlan.objects.filter(employee=user, status="notified").count()
    return {"count": count, "label": "ready to apply", "tone": "amber"} if count else None
```

---

## 5. Dependencies

**No new packages.** Reuses the existing Django-Q2 scheduler, existing email infrastructure, existing Dialog/Badge/Card components, and the existing org-tree model for scoping.

---

## 6. Verification checklist

**Lifecycle**
- [ ] A plan created today with a far-future start date stays `upcoming` and sends no email until the configured notice window.
- [ ] The scheduled task correctly transitions `upcoming` → `notified` at exactly the right day, and sends the email.
- [ ] A follow-up email sends once, and only once, after the configured delay, if still unactioned.
- [ ] A plan whose date passes with no action becomes `missed`, stays visible in My Plans, and offers a sensible next action rather than disappearing.
- [ ] Clicking Apply Now (manually or via email) creates exactly one draft application, sets `source_plan`, and is idempotent (clicking twice doesn't create a second draft).
- [ ] The resulting draft lands the user on the existing Leave app's edit page with leave type and dates pre-filled correctly.

**Scoping and access**
- [ ] A regular employee's Team Plans calendar shows only their own home unit's members.
- [ ] An HOD's default view is their own department; widening the scope shows everyone under it in the org tree.
- [ ] The same mechanism correctly scopes a Dean (faculty-wide) and a Manager (admin-department-wide) without any role-specific code — confirm this by testing at least one of each role type.
- [ ] A plan belonging to someone outside the viewer's resolved scope never appears on their calendar.
- [ ] My Plans only ever shows the logged-in employee's own plans — verified across two different employee accounts.

**Forms and UX**
- [ ] Only `plannable=True` leave types appear in the Create a Plan form.
- [ ] Creating an overlapping plan shows a warning but still saves successfully (soft warning, not a hard block).
- [ ] Every flow matches its intended click count: My Plans is 0 clicks (landing page), Create a Plan is 2 clicks, Apply Now is 2 clicks total, Team Plans + date detail is 2 clicks.
- [ ] The calendar's plan bars are visually distinct from the separate "actual approved/pending leave" team calendar from the UI/UX Phase 2 unit, so the two are never confused.

**Launcher integration**
- [ ] "Leave Plans" appears as a card on the App Launcher for every employee.
- [ ] The badge count on that card matches the number of `notified` plans for that user.

**Regression**
- [ ] No changes to the existing Leave app's draft/application logic beyond the new optional `source_plan` field and the one new `create_draft_application` call site.
- [ ] No approval-chain or workflow code was touched — this unit never creates an `ApplicationStage` or `ApprovalDecision` directly.
