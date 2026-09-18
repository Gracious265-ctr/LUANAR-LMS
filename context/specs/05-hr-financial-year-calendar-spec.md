# Unit 5 — HR Financial Year and Calendar Configuration

## Goal

Create the HR financial-year and public-holiday configuration experience
(build-plan §4, Unit 5):

- Configure the **active financial year** (start and end dates).
- Configure **future financial-year periods**.
- Configure **public holidays** — the configuration boundary for the later
  leave-date/working-day validation units.
- Provide the service boundary the leave-validation units consume: the system
  must use the configured financial year when validating leave applications.

The unit delivers the *configuration* and the *backend resolution boundary* only.
Leave-application validation, working-day calculation, and holiday-aware day
counting are later units (build-plan Units 13–14) and are out of scope here.

## Assumptions made (flag if wrong)

- **Domain home:** financial years and public holidays live in the `leave` app,
  beside `GradeEntitlement`/`LeaveType`/`LeaveRule`. They are the same family of
  HR-configured leave data, so a new app is not justified. Matches
  architecture.md's storage model ("Financial-year configuration |
  Database", "Public-holiday references/configuration | Database") and the
  build-plan §10 "configurable rather than hard-coded" list.
- **Active financial year is an explicit flag, not inferred from today's date.**
  The build plan lists "Active financial year" as a distinct config item and
  "future financial-year periods" as separately schedulable, so HR explicitly
  marks which configured period is active. *Exactly one* financial year is
  active at a time; activating a period (including a future one) deactivates
  the previously active period. New periods are created inactive.
- **Financial years must not overlap**, but need not be contiguous. The
  "leave cannot cross a financial-year boundary" protected rule only requires
  that any date belongs to at most one configured period, so non-overlap is the
  enforced invariant (mirrors Unit 3's overlapping-band rejection); requiring
  contiguous July–June blocks is LUANAR-specific data, not an invariant, and is
  left to the data HR enters.
- **Public holidays are single-date, named entries.** No recurrence rules
  (e.g. "every July 6") — HR enters each date, which is the explicit,
  unambiguous representation. A given date is a holiday at most once
  (`date` unique). Past and future dates are both allowed.
- **No external holiday integration in this unit.** architecture.md keeps the
  public-holiday data source and fallback TBD, build-plan §9 says "Do not
  implement public-holiday integration before leave-date validation requires
  it", and good-firewall rules forbid inventing integrations. Unit 5 builds the
  configuration **boundary** (model + HR CRUD + a `public_holidays_between`
  service) that a later unit's working-day calculation can consume; no calendar
  API/sync is added.
- **No financial-year/holiday seed data.** LUANAR's financial-year dates and
  public holidays are organization-specific and are not documented anywhere in
  the project, so seeding invented dates would violate the "do not invent
  organization-specific data" rule. Unlike Units 3–4 (whose defaults were
  documented in project-overview), Unit 5 starts empty and HR creates the first
  period/holidays.
- **No hard delete.** Consistent with Units 2–4, financial years and holidays
  are configuration that historical records may reference later, so `DELETE` is
  not exposed.
- **Editable configuration, not immutable history.** No leave applications
  exist yet, so financial-year and holiday rows are full CRUD (via HR endpoints)
  for now. Historical-integrity rules become the concern of the units that
  consume these values.

## Visible result

An HR financial-year/calendar configuration page.

## Dependencies

- Unit 2 (HR role, `IsHRRole`, seed infra, frontend proxy conventions).
- Unit 3 (HR-only viewset/serializer structure, overlap validation pattern,
  resolution service pattern).
- Unit 4 (effective-dated `current`/`upcoming` status handling, split
  server-safe/client lib pattern, frontend table/form conventions).

## API contract

All endpoints require a valid JWT and the `hr` role (`IsHRRole`), mirroring
Units 3–4. Namespaces are `/api/v1/financial-years/` and
`/api/v1/public-holidays/`.

### Financial years (`FinancialYear`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/financial-years/` | List financial years (paginated, newest `start_date` first) |
| POST | `/api/v1/financial-years/` | Create a financial year |
| GET | `/api/v1/financial-years/{id}/` | Retrieve one financial year |
| PATCH | `/api/v1/financial-years/{id}/` | Partially update one financial year |

Response object (snake_case, DRF conventions):

```json
{
  "id": 1,
  "start_date": "2026-07-01",
  "end_date": "2027-06-30",
  "is_active": true
}
```

Validation:

- `start_date` and `end_date` required.
- `end_date >= start_date`.
- `start_date`/`end_date` range must **not overlap** any existing financial
  year (excluding the row being updated), mirroring Unit 3's range-overlap
  guard.
- Setting `is_active = true` deactivates any other financial year (exactly one
  active at a time).

### Public holidays (`PublicHoliday`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/public-holidays/` | List public holidays (paginated, by `date`; `year=YYYY` filter) |
| POST | `/api/v1/public-holidays/` | Create a public holiday |
| GET | `/api/v1/public-holidays/{id}/` | Retrieve one public holiday |
| PATCH | `/api/v1/public-holidays/{id}/` | Partially update one public holiday |

Response object:

```json
{
  "id": 1,
  "name": "Independence Day",
  "date": "2026-07-06"
}
```

Validation:

- `name` required, non-blank.
- `date` required and unique (no second holiday on the same date).
- Errors follow Unit 1 conventions: `{"detail": "..."}` for single errors,
  `{"field": ["..."]}` for validation.

## Implementation

Work in the following order; verify each backend step before frontend work begins.

### 1. Models

- `leave/models.py`:
  - `FinancialYear`: `start_date` (DateField), `end_date` (DateField),
    `is_active` (BooleanField, default False). `Meta.ordering =
    ["-start_date"]`; DB `CheckConstraint` `start_date <= end_date`.
  - `PublicHoliday`: `name` (CharField max_length 200), `date` (DateField,
    unique). `Meta.ordering = ["date"]`. DB `UniqueConstraint` on `date`.
- Migration `0003_financialyear_publicholiday` (created via
  `makemigrations leave`).

### 2. Services (resolution boundary)

- `leave/services.py`: extend with:
  - `financial_year_for_date(d) -> FinancialYear | None` — the configured
    period containing date `d` (non-overlap makes this unique; supports future
    periods). This is what "the system uses the configured financial year when
    validating leave applications" resolves to.
  - `active_financial_year() -> FinancialYear | None` — the row flagged
    `is_active`.
  - `public_holidays_between(start, end) -> QuerySet` — holidays on dates in
    `[start, end]` ordered by date; the boundary a later working-day calculation
    consumes.

### 3. Admin

- `leave/admin.py`: register `FinancialYear` (list_display start/end/is_active
  with a colored active badge equivalent, list_filter on `is_active`, ordering
  by `-start_date`) and `PublicHoliday` (list_display name/date, search on
  name, list_filter on date year). Add an admin form guard that rejects
  overlapping financial-year ranges and duplicate holiday dates using the same
  service/queryset logic as the serializers; `has_delete_permission=False` to
  honor no-hard-delete.

### 4. Serializers

- `leave/serializers.py`:
  - `FinancialYearSerializer` (start/end/is_active; validates `end_date >=
    start_date`, non-overlap with other periods excluding self, and on
    `is_active = true` deactivates other active periods atomically).
  - `PublicHolidaySerializer` (name/date; validates name non-blank and date
    uniqueness excluding self).

### 5. Views

- `leave/views.py`: `FinancialYearViewSet` and `PublicHolidayViewSet`
  (list/create/retrieve/patch only, HR-only `IsHRRole`, no delete), mirroring
  `LeaveTypeViewSet`. `PublicHolidayViewSet` supports `year=YYYY` list filter.

### 6. URLs

- `leave/urls.py`: register `financial-years` (basename `financial-year`) and
  `public-holidays` (basename `public-holiday`) routers alongside the existing
  routers.

### 7. Seed

- No financial-year or public-holiday seeding (see assumptions). Existing
  `seed_dev_users` behavior is unchanged.

### 8. Frontend

- `lib/financial-years.ts` (server-safe; imported only by server pages): TS
  types (`FinancialYear`, `FinancialYearInput`, `PublicHoliday`,
  `PublicHolidayInput`, list responses) and read helpers `listFinancialYears`,
  `getFinancialYear`, `listPublicHolidays` (with `year` param), `getPublicHoliday`,
  plus a `financialYearStatus(year)` helper (Active/Upcoming pill).
- `lib/financial-years-client.ts` (client-safe): `createFinancialYear`,
  `updateFinancialYear`, `createPublicHoliday`, `updatePublicHoliday` posting to
  the route-handler proxies — split from the server module exactly as
  `leave-rules.ts`/`leave-rules-client.ts`, so the client forms never pull
  `next/headers` into the bundle.
- Route-handler proxies (mirror Units 2–4):
  - `app/api/hr/financial-years/route.ts` — POST.
  - `app/api/hr/financial-years/[id]/route.ts` — PATCH.
  - `app/api/hr/public-holidays/route.ts` — POST.
  - `app/api/hr/public-holidays/[id]/route.ts` — PATCH.
- Components under `components/hr/`:
  - `financial-year-table.tsx` (start/end, Active/Upcoming pill, edit link) and
    `financial-year-form.tsx` (client create/edit form with start/end date and
    "make active" checkbox).
  - `public-holiday-table.tsx` (name, date, edit link, empty state) and
    `public-holiday-form.tsx` (client create/edit form with name + date).
- Pages under `app/(dashboard)/dashboard/hr-admin/calendar/` — a single visible
  configuration page with two sections:
  - `page.tsx`: "Financial years" card (table + "New financial year" button,
    explaining that exactly one is active and future periods are scheduled by
    activating) and "Public holidays" card (table with a year filter select,
    "New holiday" button).
  - `financial-years/new/page.tsx`, `financial-years/[id]/edit/page.tsx`.
  - `holidays/new/page.tsx`, `holidays/[id]/edit/page.tsx`.
- Add a sidebar item ("Calendar", lucide `CalendarDays`) and an HR index card,
  reusing existing dashboard shell patterns.
- All pages guard with `getCurrentUser()` → redirect `/login` and
  `user.role !== "hr"` → redirect `/dashboard`, matching existing pages.

### 9. Tests (`leave/tests.py`)

- Service: `financial_year_for_date` resolves the containing period (current and
  future periods), returns `None` for a date outside every period;
  `active_financial_year` returns the flagged row; `public_holidays_between`
  returns only in-range holidays ordered by date.
- API: 401 unauthenticated; 403 for non-HR; HR CRUD for both resources;
  validation failures (missing start/end date for a year, `end_date < start_date`,
  overlapping year rejected even when future-dated, duplicate holiday date,
  blank holiday name); activating one year deactivates the other; `year=` holiday
  filter; `DELETE` → 405.
- No seed test (nothing new is seeded).

### 10. Docs

- Add `context/specs/05-hr-financial-year-calendar-spec.md` (this file).
- Update `context/progress-tracker.md` (Unit 5 complete; note the
  public-holiday integration boundary is configuration-only, external source
  still TBD).
- Update root `README.md` API table with the `/api/v1/financial-years/` and
  `/api/v1/public-holidays/` endpoints.

## Verification

- `uv run manage.py test` green (existing 99 + new financial-year/holiday tests).
- `npm test` green, `npm run lint` and `npm run build` green.
- `npm run dev` against a seeded backend: HR sees the calendar page, creates a
  financial year and marks it active, adds holidays; activating a second year
  deactivates the first; non-HR 403s; overlapping year and duplicate holiday
  dates are rejected in the UI with backend errors shown.