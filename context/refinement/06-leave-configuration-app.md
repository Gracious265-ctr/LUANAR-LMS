# Unit — Leave Configuration App

*Unit number left open. New module (7th app on the launcher) — adds `backend/leave_config/` and `frontend/app/(dashboard)/leave-config/`. This is the one place `LeaveType` and all its rules are created and edited; every other module (Leave, Approvals/org-tree chain resolution, Plans) reads from here and never defines its own copy of a rule.*

---

## 1. Open questions — resolved

You asked me to flag anything unclear. All six are now confirmed; the decisions below are final, not defaults pending review.

### 1.1 Where does `LeaveType` actually live — CONFIRMED: this app owns it

**Confirmed: `leave_config` is the true owner of the `LeaveType` model** — the app that lets you *create* a leave type also *owns* the data, the same way `org` owns `OrgUnit` and `approvals` owns `ApplicationStage`. `leave.LeaveApplication`, `plans.LeavePlan`, and the org-tree's chain-resolution code all FK into `leave_config.LeaveType` and only ever *read* its rule fields — never duplicate or redefine a rule elsewhere.

**If `LeaveType` already exists in a different app** (possible, from the parallel Units 2-11 track), this still needs the same careful **state-only migration** used in the System Restructure unit's `workflows` → `org`/`approvals` split — move the table, don't drop and recreate it, since real data may already reference it. Check for this before running the migration in §4.2.

### 1.2 "Notice" — CONFIRMED: one field, reused by two consumers

**Confirmed, as recommended.** One field, `notice_days`, means "how much advance notice does this leave type require" — Unit 14's submission validation uses it to reject applications submitted too close to the start date, and the Plans app's reminder scheduler fires exactly when that same notice window opens. The Leave Plans spec's `plan_notice_days` field is retired and replaced with a direct read of `LeaveType.notice_days` — update that spec to match if it hasn't been already.

### 1.3 Entitlement — CORRECTED: this app does NOT own it, entitlement is grade-based

**Correction, not a confirmation of the original recommendation.** Entitlement is not a flat number per leave type set here. It's **grade-based**: an employee's assigned grade determines how many days of each leave type they get per financial year, and that mapping is configured in the **Staff Members app**, not this one.

This means `LeaveType` in this app has **no `default_days_per_year` field at all** — remove it entirely from §4.2's model (done below). The entitlement mapping (grade × leave type × financial year → days) lives on whatever model the Staff Members app defines — likely something like `GradeLeaveEntitlement(grade, leave_type, financial_year, days_per_year)`. This app's `LeaveType` is referenced *from* that model via FK, the same read-only relationship every other module has with `LeaveType` — `leave_config` still owns the leave type itself (name, eligibility, documents, max duration, notice, plannability, escalation), it just never owns *how many days of it someone gets*.

**This is a new dependency this spec didn't previously account for:** the Leave app's balance display, and anywhere else "how many days does this employee have" is computed, must now query the Staff Members app's entitlement mapping (filtered by the employee's grade and the current financial year), not read a number off `LeaveType` directly. Flag this clearly for whoever builds the Leave dashboard — that spec currently assumes a simpler lookup than this.

**Open sub-question:** is the "Staff Members app" the same module as **HR Administration** from the System Restructure spec (which already named "Employee management, grades" as part of its scope), just under a different working name — or is it a genuinely separate, dedicated module deserving its own launcher card? This changes where the entitlement model and its admin screens actually live. Worth settling before that app gets specced.

### 1.4 Eligibility — CONFIRMED: three dimensions

**Confirmed: three eligibility dimensions, each independently optional (unset = no restriction on that dimension):**
- **Branch scope** — Academic / Administrative / Both (e.g. a "Sabbatical" type might be academic-only)
- **Eligible grades** — a multi-select against the existing employee-grade model (Units 2-11); empty = all grades eligible
- **Eligible gender** — Any / Male / Female (needed for leave types like maternity or paternity leave); defaults to "Any"

An employee is eligible for a leave type only if they pass **all three** checks (branch, grade, and gender each independently either unrestricted or matching). This is ordinary leave-policy configuration, not personal data handling — the gender field here is a business rule on the leave type, not a record of anything about a specific person beyond what the employee model (from Units 2-11) already holds for standard HR purposes.

### 1.5 Deactivating, not deleting — CONFIRMED

**Confirmed, as recommended.** Leave types are never hard-deleted once any application or plan references them. `is_active` controls visibility to new applications/plans; all historical data stays intact and fully viewable regardless of a type's active state.

### 1.6 `requires_institutional_registrar_approval` lives here too — CONFIRMED

**Confirmed.** This app is where HR sets it, alongside every other leave-type rule — the chain-resolution algorithm in `approvals` only ever reads it.

---

## 2. Goal

Give HR one dedicated app for creating and managing leave types and every rule attached to them — eligibility, document requirements, maximum duration, notice period, entitlement, plannability, and institutional-registrar escalation — so every other module (Leave, Approvals, Plans) reads these rules from one authoritative source instead of each guessing or duplicating them.

### Assumptions

| # | Assumption |
|---|---|
| A1 | Access is HR-only — same `HR` Django group already defined for the System Admin Dashboard's HR tier and the launcher's `hr-admin` access check. Superusers can also reach it (they can reach everything), but no other role sees this app's card on the launcher. |
| A2 | This unit does not touch anything about how balances are *consumed/deducted* (that's existing Unit 14/18 logic) — it only defines the entitlement *number* a balance calculation reads from. |
| A3 | Existing applications/plans referencing a leave type are never affected by later rule changes to that type — rule edits are forward-looking only, applied to new applications/plans from that point on, never retroactive. |

---

## 3. Design

### 3.1 Pages and 3-click budget

| Flow | Click 1 | Click 2 | Click 3 | Total |
|---|---|---|---|---|
| **View all leave types** | *(lands here — this is the app's landing page)* | — | — | **0 clicks** |
| **Create a new leave type** | Press "Create Leave Type" → form | *(fill form)* Press "Save" | — | **2 clicks** |
| **Edit an existing type's rules** | Click its row in the list → edit form (pre-filled) | *(edit fields)* Press "Save" | — | **2 clicks** |
| **Deactivate a leave type** | Click its row → detail/edit view | Press "Deactivate" → confirm dialog opens | Confirm | **3 clicks** |

Deactivation gets the full 3-click budget deliberately — it's a consequential action (it affects whether employees can select this type going forward) and deserves the explicit confirm step, same reasoning already used for the Leave app's cancellation flow.

### 3.2 Landing page — Leave Types list

A single table, no separate "dashboard" with stat cards — this is a configuration app, not something HR checks daily, so keep it simple: a list, a create button, done. Columns: name, branch scope, max duration, notice period, requires documents (icon), active/inactive `Badge`, last updated. (No entitlement/days column — that number doesn't exist on this model; see §1.3.) Inactive types are shown grayed/muted in the same list (filterable via a simple toggle at the top — "Show inactive"), not hidden on a separate page, keeping the sidebar to two items (§3.5).

Empty state (brand-new system, no leave types configured yet): `EmptyState` with "No leave types configured yet" and a "Create Leave Type" action — this matters because every other module (Leave, Plans) is non-functional until at least one leave type exists, so this empty state should be unmissable.

### 3.3 Create / Edit form

One form, reused for both create and edit (edit just pre-fills it). Sections:

- **Basics:** name, short code, color (restricted to a small defined palette of existing status-safe tokens — don't let HR pick arbitrary hex values that could clash with the status-color system used everywhere else), description (shown to employees as help text when selecting this type on the application form).
- **Eligibility:** branch scope (Academic / Administrative / Both), eligible grades (multi-select, empty = all), eligible gender (Any / Male / Female, default Any).
- **Rules:** requires supporting document (toggle), maximum duration in days (number, blank = no max), notice period in days (number, blank = no minimum — per §1.2, this single field drives both submission validation and the Plans reminder timing).
- **Planning:** plannable (toggle — controls whether this type appears in the Leave Plans app's "Create a Plan" form).

No entitlement/day-count field appears on this form at all — per §1.3, that's configured per grade in the Staff Members app, not here.
- **Approval:** requires Institutional Registrar approval (toggle, per §1.6) — show this only when branch scope is Administrative or Both, since it's meaningless for a purely Academic-scoped type per the org-tree blueprint's rule that academic chains never reach the Institutional Registrar regardless of this flag.

Inline validation (per the Phase-2 UI/UX conventions): required fields, numeric fields reject negative values, max duration (if set) must be a positive number, no cross-field validation needed beyond that.

### 3.4 Deactivate flow

From the edit view, a "Deactivate" button (secondary/outline styling, not primary — this isn't the main action of the page) opens a confirm `Dialog`: "Deactivate {name}? Employees will no longer be able to select this leave type for new applications or plans. Existing applications and plans are not affected." Confirming sets `is_active=False`. A deactivated type can be reactivated the same way (button becomes "Reactivate").

### 3.5 Sidebar

Two items only, per the minimal-scope discipline used everywhere else:

```ts
export const LEAVE_CONFIG_NAV_ITEMS = [
  { label: "Leave Types", href: "/leave-config", icon: ListChecks },
  { label: "Create Leave Type", href: "/leave-config/new", icon: Plus },
];
```

Plus the standard "← All Apps" link at the top, per the module-scoped shell pattern.

---

## 4. Implementation

### 4.1 Backend app

```bash
cd backend
python manage.py startapp leave_config
```

### 4.2 Model (`backend/leave_config/models.py`)

```python
class BranchScope(models.TextChoices):
    ACADEMIC = "academic"
    ADMINISTRATIVE = "administrative"
    BOTH = "both"


class GenderEligibility(models.TextChoices):
    ANY = "any"
    MALE = "male"
    FEMALE = "female"


class LeaveType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, blank=True)
    color = models.CharField(max_length=20, choices=ALLOWED_COLOR_CHOICES)  # §3.3 — restricted palette
    description = models.TextField(blank=True)

    branch_scope = models.CharField(choices=BranchScope.choices, default=BranchScope.BOTH)
    eligible_grades = models.ManyToManyField("employees.Grade", blank=True)  # empty = all grades
    eligible_gender = models.CharField(choices=GenderEligibility.choices, default=GenderEligibility.ANY)

    requires_supporting_document = models.BooleanField(default=False)
    max_duration_days = models.PositiveIntegerField(null=True, blank=True)
    notice_days = models.PositiveIntegerField(null=True, blank=True)  # §1.2 — single consolidated field

    # NOTE: no entitlement/day-count field here — per §1.3, how many days
    # an employee gets of this type is grade-based and lives entirely in
    # the Staff Members app's entitlement mapping, not on LeaveType itself.

    plannable = models.BooleanField(default=False)  # read by the Leave Plans app
    requires_institutional_registrar_approval = models.BooleanField(default=False)  # read by approvals' chain resolver

    is_active = models.BooleanField(default=True)  # §1.5
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

If `LeaveType` already exists elsewhere (§1.1), this becomes a state-only move migration instead of a fresh `CreateModel` — test against a staging data copy first, same caution as the earlier `workflows` split.

### 4.3 Services (`backend/leave_config/services.py`)

```python
def can_access_leave_config(user) -> bool:
    return user.is_superuser or user.groups.filter(name="HR").exists()

def deactivate_leave_type(leave_type: LeaveType, actor) -> None:
    leave_type.is_active = False
    leave_type.save(update_fields=["is_active"])
    audit_log(actor=actor, action="leave_type.deactivated", target=leave_type)

def reactivate_leave_type(leave_type: LeaveType, actor) -> None:
    leave_type.is_active = True
    leave_type.save(update_fields=["is_active"])
    audit_log(actor=actor, action="leave_type.reactivated", target=leave_type)
```

Every other module calls these **read-only** helpers rather than querying `LeaveType` fields directly inline, so the rule logic stays centralized:

```python
def is_eligible(leave_type: LeaveType, employee) -> bool:
    if leave_type.branch_scope != BranchScope.BOTH and leave_type.branch_scope != employee.branch:
        return False
    if leave_type.eligible_grades.exists() and employee.grade not in leave_type.eligible_grades.all():
        return False
    if leave_type.eligible_gender != GenderEligibility.ANY and leave_type.eligible_gender != employee.gender:
        return False
    return True

def validate_notice(leave_type: LeaveType, start_date) -> bool:
    if leave_type.notice_days is None:
        return True
    return (start_date - timezone.now().date()).days >= leave_type.notice_days
```

Unit 14's submission validator and the Plans scheduler both call `validate_notice`/read `notice_days` from here — neither reimplements the calculation.

### 4.4 API endpoints (`backend/leave_config/views.py`, `urls.py`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/leave-config/types/` | List (HR sees all incl. inactive via `?include_inactive=true`; every other module's dropdowns call this with `?active_only=true`) |
| POST | `/api/leave-config/types/` | Create |
| GET | `/api/leave-config/types/{id}/` | Detail |
| PATCH | `/api/leave-config/types/{id}/` | Update rules |
| POST | `/api/leave-config/types/{id}/deactivate/` | Deactivate (confirm-gated on the frontend) |
| POST | `/api/leave-config/types/{id}/reactivate/` | Reactivate |

All write endpoints gated by `can_access_leave_config`; the plain GET/list is readable by any authenticated user (every module needs to read leave-type data — e.g. the Leave app's application form needs the list to populate its dropdown), but only HR/superuser can create or modify.

### 4.5 Frontend

```
frontend/app/(dashboard)/leave-config/
  page.tsx            // Leave Types list — landing page
  new/page.tsx         // Create form
  [id]/page.tsx         // Edit form (same form component as new/, pre-filled)
  layout.tsx            // module-scoped shell, LEAVE_CONFIG_NAV_ITEMS

frontend/components/leave-config/
  LeaveTypeTable.tsx
  LeaveTypeForm.tsx       // shared between create and edit
  DeactivateDialog.tsx
```

### 4.6 App Launcher integration

```ts
"leave-config": { name: "Leave Configuration", description: "Manage leave types and their rules", icon: SlidersHorizontal, route: "/leave-config" },
```

`can_access_leave_config(user)` (§4.3) gates its visibility — same pattern as every other launcher entry, no badge needed (this isn't an urgency-driven app).

### 4.7 Cross-module read points (so nobody reimplements a rule)

| Consumer | Reads |
|---|---|
| `leave` (application form + Unit 14 validation) | `is_eligible`, `requires_supporting_document`, `max_duration_days`, `validate_notice` |
| `leave` (balance display) | Does **not** read anything from `leave_config` for entitlement — queries the Staff Members app's grade-based entitlement mapping instead (per §1.3) |
| `plans` (Create a Plan form + reminder scheduler) | `plannable` (filters the dropdown), `notice_days` (drives reminder timing, per §1.2 — replaces `plan_notice_days` in that spec) |
| `approvals` (chain resolution) | `requires_institutional_registrar_approval` |

---

## 5. Dependencies

**No new packages.** Plain Django/DRF model, services, and views; plain React form on the frontend reusing existing shared components (`Table`, `Dialog`, `EmptyState`, `Badge`, inline-validated `Input`/`Select`).

---

## 6. Verification checklist

**Core CRUD**
- [ ] HR can create a leave type with every rule field set correctly.
- [ ] Editing an existing type's rules does not alter any already-submitted application or plan's validation outcome retroactively.
- [ ] Deactivating hides the type from new application/plan dropdowns but leaves historical references fully intact and viewable.
- [ ] Reactivating restores it to the active dropdowns.

**Access**
- [ ] Only HR/superuser can create, edit, deactivate, or reactivate — verified with a non-HR employee account getting a 403 on write endpoints.
- [ ] Any authenticated user can read the active leave-types list (needed for the Leave app's own dropdowns).
- [ ] The "Leave Configuration" card appears on the launcher only for HR/superuser.

**Rule correctness**
- [ ] `is_eligible` correctly filters by branch scope, eligible grades, and eligible gender — treating an empty grade list and a gender value of "Any" as unrestricted on those dimensions respectively.
- [ ] `LeaveType` has no entitlement/day-count field — confirm nothing in this app's model, form, or list view references days-per-year; that number comes entirely from the Staff Members app's grade-based entitlement mapping.
- [ ] `validate_notice` correctly allows/rejects based on `notice_days`, including the `None` = "no minimum" case.
- [ ] The Plans app's reminder correctly fires using `LeaveType.notice_days` (confirm the Plans spec's `plan_notice_days` field was removed/aliased per §1.2, not left as a duplicate, divergent number).
- [ ] `requires_institutional_registrar_approval` is correctly read by the approvals chain resolver and has no effect on Academic-branch chains, matching the org-tree blueprint's hard ceiling rule.

**3-click rule**
- [ ] Viewing the list is 0 clicks (landing page).
- [ ] Creating a leave type is 2 clicks.
- [ ] Editing an existing type's rules is 2 clicks.
- [ ] Deactivating is exactly 3 clicks (row → Deactivate → Confirm), no more.

**Regression**
- [ ] If `LeaveType` existed elsewhere before this unit, the migration preserved all existing data with zero loss (verified against a staging copy first).
- [ ] No other module (`leave`, `plans`, `approvals`) contains its own duplicate copy of a leave-type rule after this unit — every rule check goes through `leave_config.services`.
