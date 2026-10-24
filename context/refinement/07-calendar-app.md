# Unit — Calendar App


read `context/AGENTS.md` before starting

---

## 1. Goal

Give HR one place to configure everything institution-wide and date-related — financial years, public holidays, institutional events, the working-day pattern, and (optionally) academic term dates and blackout periods — and expose it as a read-only source every other module (Leave, Plans, Approvals) can query, rather than each one assuming calendar-day math or hardcoding a holiday list.

---

## 2. Access — confirmed

**Option A, confirmed:** this app's launcher card is visible to **HR and superuser only** — same `can_access_*` pattern already used for Leave Configuration. Regular employees and approvers never navigate to a standalone "Calendar" destination; they encounter this data *contextually*, inside the Leave app's date picker, balance/day-count calculations, and the Leave Plans reminder logic. This keeps the launcher itself uncluttered for roles with no configuration reason to be there, consistent with the principle driving this whole restructuring effort.

```python
def can_access_calendar(user) -> bool:
    return user.is_superuser or user.groups.filter(name="HR").exists()
```

All **write** endpoints (create/edit/delete financial years, holidays, events, working-day pattern, terms, blackout periods) are gated by this check. All **read** endpoints are open to any authenticated user, since every module needs to consume this data.

---

## 3. Design

### 3.1 What this app owns

| Concept | Purpose |
|---|---|
| **Financial Year** | Start/end dates for each financial year, used throughout Leave/Plans for balance periods and entitlement lookups |
| **Working-Day Pattern** | Which weekdays count as working days (e.g. Mon–Fri) — the missing piece that Unit 14's day-counting and notice-period calculations should read from, rather than assuming `end_date - start_date` |
| **Holidays** | Public/institutional holidays — recurring (same date every year) or one-off, with optional weekend-observed-shift handling |
| **Events** | Institutional calendar entries (graduation, orientation week) — informational, not directly consumed by leave-calculation logic, but useful context on the same calendar view |
| **Academic Terms** (optional) | Semester/term start-end dates, if eligibility or blackout rules ever need to reference them |
| **Blackout Periods** (optional) | Date ranges where certain leave types are flagged with a soft warning (not a hard block, consistent with the Leave Plans overlap-warning precedent) |

### 3.2 Three calendars now exist in this system — visual distinction is mandatory

This is the most important design constraint, flagged explicitly because it's easy to get wrong: there are now **three separate calendar concepts** in LUANAR-LMS, and wherever they might appear near each other, they must be unmistakably distinct, not just by a tooltip but by color/pattern at a glance:

| Calendar | Shows | Owning app | Visual treatment |
|---|---|---|---|
| This app's calendar | Holidays, events, non-working days | Calendar app | Solid filled day cells, HR's configured color per entry type |
| Team Plans calendar | Employees' *planned* (not yet applied) leave | Leave Plans | Dashed/outlined bars, per that spec's existing distinction |
| Team leave calendar | Employees' *actual* approved/pending leave | UI/UX Phase 2 | Solid bars, status-color coded |

Where the Leave app's date picker shows holidays (disabled/highlighted dates) inline, it reads this app's data but does **not** render a third competing visual style — holidays in a date picker are simply non-selectable/shaded dates, a different UI pattern entirely from the two leave-calendars above, so no new confusion is introduced there.

### 3.3 Landing page and 3-click budget

Single landing page, tabbed or sectioned (not separate sidebar items per concept, consistent with the "don't proliferate nav items" discipline already applied to Leave Plans' Team Plans page): **Financial Years**, **Holidays & Events**, **Working Days**, and optionally **Terms** / **Blackout Periods** as additional tabs if built.

| Flow | Clicks |
|---|---|
| View current financial year / holiday list | **0** (landing page) |
| Add a holiday | Tab (if not already there, 0) → "Add Holiday" (1) → fill form → Save (2) | **2** |
| Edit the working-day pattern | Working Days tab (1) → toggle days → Save (2) | **2** |
| Delete a holiday | Click its row (1) → Delete (2) → Confirm (3) | **3** |

### 3.4 Working-day pattern

```python
class WorkingDayPattern(models.Model):
    monday = models.BooleanField(default=True)
    tuesday = models.BooleanField(default=True)
    wednesday = models.BooleanField(default=True)
    thursday = models.BooleanField(default=True)
    friday = models.BooleanField(default=True)
    saturday = models.BooleanField(default=False)
    sunday = models.BooleanField(default=False)
```

Single row (institution-wide, not per-campus — flag if any campus genuinely needs a different working week; defaulting to one shared pattern for simplicity). Unit 14's day-counting and notice-period validation, and the Leave dashboard's duration display, should compute against this pattern plus the holiday list (§3.5) rather than raw calendar-day subtraction — **this is a real patch needed to the already-written Unit 14 spec**, flagged here since it was built before this app existed.

### 3.5 Holidays

```python
class Holiday(models.Model):
    name = models.CharField(max_length=200)
    date = models.DateField()  # for a one-off holiday; for recurring, this is the reference date
    is_recurring = models.BooleanField(default=True)  # repeats on the same month/day every year
    observed_shift = models.BooleanField(default=True)  # if it falls on a non-working day, shift to the nearest working day
    financial_year = models.ForeignKey("leave.FinancialYear", null=True, blank=True, on_delete=models.SET_NULL)  # null if institution-wide/not FY-scoped
```

```python
def get_holidays_for_range(start_date, end_date) -> list[Holiday]:
    """Resolves recurring holidays into actual dates within the range, applying observed_shift."""
```

### 3.6 Events

```python
class CalendarEvent(models.Model):
    title = models.CharField(max_length=200)
    start_date = models.DateField()
    end_date = models.DateField()
    description = models.TextField(blank=True)
    affects_leave_calculation = models.BooleanField(default=False)  # almost always False — see below
```

`affects_leave_calculation` exists so an event can be promoted to actually block/warn on leave dates (e.g. graduation week) without needing a separate blackout-period model if that turns out to be the simpler path — default `False` means purely informational, no effect on Leave/Plans logic.

### 3.7 API

| Method | Path | Access |
|---|---|---|
| GET | `/api/calendar/financial-years/` | Any authenticated user |
| POST/PATCH/DELETE | `/api/calendar/financial-years/` | HR/superuser |
| GET | `/api/calendar/holidays/?start=&end=` | Any authenticated user — returns resolved holiday dates in range |
| POST/PATCH/DELETE | `/api/calendar/holidays/` | HR/superuser |
| GET | `/api/calendar/working-days/` | Any authenticated user |
| PATCH | `/api/calendar/working-days/` | HR/superuser |
| GET | `/api/calendar/events/?start=&end=` | Any authenticated user |
| POST/PATCH/DELETE | `/api/calendar/events/` | HR/superuser |

### 3.8 Cross-module consumers

| Consumer | Reads |
|---|---|
| `leave` (Unit 14 validation, notice/duration calc) | `working-days/`, `holidays/` — **patches Unit 14's day-counting to exclude non-working days and holidays, not raw calendar subtraction** |
| `leave` (date picker UI) | `holidays/` — shades/disables those dates |
| `plans` (reminder scheduling) | `working-days/` if notice-day calculation should skip non-working days (confirm this — Leave Plans currently assumes calendar days) |

### 3.9 App Launcher integration

```ts
"calendar-app": { name: "Calendar", description: "Manage financial years, holidays, and institutional dates", icon: CalendarRange, route: "/calendar" },
```

`can_access_calendar` gates visibility, per §2.

---

## 4. Dependencies

**No new packages.** Plain Django models/views, plain React calendar grid (no charting/calendar library needed for an admin list+grid view this simple).

---

## 5. Verification checklist

**Access**
- [ ] Only HR/superuser see the "Calendar" launcher card.
- [ ] Any authenticated user can read holidays/working-days/events; only HR/superuser can write.

**Data correctness**
- [ ] Recurring holidays resolve correctly across year boundaries (e.g. querying Dec 20 – Jan 5 correctly returns both a recurring Dec 25 and Jan 1 holiday).
- [ ] `observed_shift` correctly moves a holiday landing on a non-working day to the nearest working day when enabled.
- [ ] Working-day pattern changes are reflected immediately in new day-count calculations (not retroactive to already-submitted applications, per the project's standing "config changes are forward-looking only" invariant).

**Integration**
- [ ] Unit 14's duration/notice calculation correctly excludes non-working days and holidays once patched to consume this app — flag clearly to whoever builds Unit 14 that this patch is required, not optional, since the original spec predates this app.
- [ ] The Leave app's date picker correctly shades/disables holiday dates.

**Visual distinction**
- [ ] This app's calendar, the Team Plans calendar, and the actual-leave Team calendar are visually distinguishable wherever they might appear in proximity — confirmed by a side-by-side review, not assumed.

**3-click rule**
- [ ] Viewing the landing page is 0 clicks; adding a holiday is 2; deleting one is 3, matching §3.3.

**Regression**
- [ ] No change to any already-submitted application's calculated duration/notice when working-day pattern or holidays are edited later.
