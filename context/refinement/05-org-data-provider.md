# Unit — External Organization Data Provider

read `context/AGENTS.md` before starting

---

## 1. Goal

Define one provider interface for everything LUANAR-LMS needs to know about staff, grades, and organizational structure — employees, their grades, the campus/faculty/department/team hierarchy, and who currently holds each approver-relevant position (HOD, Dean, Manager, Supervisor, Campus/Institutional Registrar) — backed by a **fixture implementation now**, swappable for a **real API integration later** with zero changes to any code that consumes it. This is the same swappable-provider pattern already used elsewhere in this project (storage backend, leave-type rules), applied here to the fact that staff/org data genuinely lives in a separate, already-existing university system, not in LUANAR-LMS's own database.

---

## 2. Open questions and recommendations

### 2.1 What does the external system actually return — and when will that be known?

Nobody can finalize the real API integration's request/response shapes until the external system's actual API (or export format, or database access method) is known. **Recommendation: the fixture provider's data shapes in §3.1 are the *target contract* LUANAR-LMS is building against** — whoever eventually builds the real integration implements the same `OrganizationDataProvider` interface, mapping the external system's actual format into these shapes. If the real system's data genuinely can't fit this shape later, the interface itself may need to change — but that's a future problem, not one to solve speculatively now. Flag if you already know anything concrete about the external system (REST API? direct database read? CSV export? a different protocol entirely) so the real implementation's design can start forming in parallel.

### 2.2 Where does the entitlement mapping (grade → days per leave type) live?

This is genuinely nuanced: **grade** is external data (owned by the other system), but **leave types** are entirely LUANAR-LMS's own concept (owned by the Leave Configuration app). The external system has no idea LUANAR-LMS's leave types exist, so it can't be the source of "Senior Lecturer grade gets 21 days of Annual Leave." **Recommendation: the entitlement mapping itself — `GradeLeaveEntitlement` (grade reference × leave type × financial year × days) — is configured and stored inside LUANAR-LMS**, in the **Leave Configuration app** (since that app already owns `LeaveType`, and this mapping is fundamentally "a rule about a leave type," just keyed by an externally-sourced grade identifier rather than a locally-owned one). The external provider only ever supplies *which grade an employee has* — never the entitlement number itself.

### 2.3 Syncing org structure vs. querying it live

Two ways to use the provider's org-structure data: (a) query it live, every time something needs it, or (b) sync it into LUANAR-LMS's own `OrgUnit` table (from the org-tree blueprint) periodically/on-demand, and query the local copy. **Recommendation: sync, not live query**, for the org structure specifically — because `OrgUnit` also carries LUANAR-LMS-specific data the external system doesn't have (`ActingAssignment`, the approval-chain resolver's internals), so `OrgUnit` needs to exist locally regardless. A sync service reads the provider's structure and role-holder data and creates/updates local `OrgUnit` rows accordingly (§3.4). Employee/grade lookups elsewhere (e.g. entitlement resolution, eligibility checks) can query the provider directly each time rather than syncing, since those are simpler point lookups, not a tree that other local data hangs off of.

---

## 3. Design

### 3.1 The interface

```python
# backend/directory/provider.py

@dataclass
class EmployeeRecord:
    id: str
    name: str
    email: str
    grade_id: str
    branch: Literal["academic", "administrative"]
    gender: Literal["male", "female"]
    home_unit_id: str  # the org unit (team or department) they belong to


@dataclass
class GradeRecord:
    id: str
    name: str  # e.g. "Senior Lecturer", "Administrative Officer II"


@dataclass
class OrgUnitRecord:
    id: str
    unit_type: Literal["institution", "campus", "faculty", "department_academic", "department_admin", "team"]
    name: str
    parent_id: str | None
    has_teams: bool  # only meaningful on department_admin, per the org-tree blueprint


@dataclass
class RoleHolder:
    org_unit_id: str
    role: Literal["hod", "dean", "manager", "supervisor", "campus_registrar", "institutional_registrar"]
    employee_id: str | None  # None means vacant — the provider can report a position as unfilled


class OrganizationDataProvider(ABC):
    @abstractmethod
    def get_employee(self, employee_id: str) -> EmployeeRecord | None: ...

    @abstractmethod
    def get_employees(self, *, branch: str | None = None, home_unit_id: str | None = None) -> list[EmployeeRecord]: ...

    @abstractmethod
    def get_grade(self, grade_id: str) -> GradeRecord | None: ...

    @abstractmethod
    def get_grades(self) -> list[GradeRecord]: ...

    @abstractmethod
    def get_org_units(self) -> list[OrgUnitRecord]: ...

    @abstractmethod
    def get_role_holders(self) -> list[RoleHolder]: ...
```

Every other module in this project consumes `OrganizationDataProvider`, never a specific implementation — the same discipline already established for the storage abstraction.

### 3.2 Settings-driven swap

```python
# settings.py
ORG_DATA_BACKEND = env("ORG_DATA_BACKEND", default="fixture")  # "fixture" | "api"
```

```python
# backend/directory/factory.py
def get_organization_provider() -> OrganizationDataProvider:
    if settings.ORG_DATA_BACKEND == "api":
        return ApiOrganizationDataProvider()  # built later, not part of this unit
    return FixtureOrganizationDataProvider()
```

### 3.3 Fixture implementation

```python
# backend/directory/fixtures/provider.py

class FixtureOrganizationDataProvider(OrganizationDataProvider):
    def __init__(self):
        self._data = load_fixture_data()  # reads backend/directory/fixtures/seed_data.json

    def get_employee(self, employee_id):
        return self._data["employees"].get(employee_id)
    # ... etc, simple dict lookups over the loaded fixture
```

**Seed data** (`backend/directory/fixtures/seed_data.json`): placeholder but structurally realistic — a small institution tree (one Institution, a few Campuses, a Faculty and a couple of Academic Departments under one campus, an Admin Department with and without teams, a handful of Employees spread across grades and branches, and Role Holders for each position including at least one intentionally vacant position to exercise the org-tree blueprint's vacancy handling). **Use placeholder names, not real LUANAR campus/faculty names** — nobody here has verified what those actually are, and getting them wrong in committed fixture data is worse than an obviously-generic placeholder; swap in real names once known, it's a one-file edit.

### 3.4 Org structure sync (`backend/org/services.py`, consuming the provider)

```python
def sync_org_structure_from_provider():
    provider = get_organization_provider()
    units_by_external_id = {}

    for unit_record in provider.get_org_units():
        unit, _ = OrgUnit.objects.update_or_create(
            external_id=unit_record.id,  # new field on OrgUnit — links back to the provider's identifier
            defaults={
                "unit_type": unit_record.unit_type,
                "name": unit_record.name,
                "has_teams": unit_record.has_teams,
                "parent": units_by_external_id.get(unit_record.parent_id),
            },
        )
        units_by_external_id[unit_record.id] = unit

    for role_holder in provider.get_role_holders():
        unit = units_by_external_id.get(role_holder.org_unit_id)
        employee = get_local_user_for_external_employee(role_holder.employee_id) if role_holder.employee_id else None
        unit.designated_approver = employee  # None if vacant — this is exactly what the org-tree blueprint already handles
        unit.save(update_fields=["designated_approver"])
```

This adds one field to `OrgUnit` beyond what the org-tree blueprint already defined: `external_id` (the provider's identifier for that unit, so repeated syncs update rather than duplicate). Run manually via a management command for now (`python manage.py sync_org_structure`); automate on a schedule once the real API exists and sync frequency actually matters.

**Employee identity reconciliation is the one genuinely unresolved mechanical detail:** `get_local_user_for_external_employee` needs to map an external employee ID to a local Django `User` — which assumes some existing linkage (e.g. a shared email address, or a `User.external_employee_id` field). This almost certainly already needs to exist for login/authentication to work at all (how does an employee log into LUANAR-LMS if their identity isn't already connected to the external system somehow) — flag if this linkage doesn't exist yet, since it's a prerequisite this unit assumes rather than builds.

### 3.5 Entitlement mapping (lives in Leave Configuration, per §2.2)

```python
# backend/leave_config/models.py — ADD this model (patches that spec)

class GradeLeaveEntitlement(models.Model):
    grade_id = models.CharField(max_length=100)  # external grade identifier, not a local FK
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE)
    financial_year = models.ForeignKey("leave.FinancialYear", on_delete=models.CASCADE)
    days_per_year = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["grade_id", "leave_type", "financial_year"], name="one_entitlement_per_grade_type_year")
        ]
```

```python
def get_entitlement(employee, leave_type, financial_year) -> int | None:
    provider = get_organization_provider()
    employee_record = provider.get_employee(employee.external_employee_id)
    if not employee_record:
        return None
    try:
        return GradeLeaveEntitlement.objects.get(
            grade_id=employee_record.grade_id, leave_type=leave_type, financial_year=financial_year
        ).days_per_year
    except GradeLeaveEntitlement.DoesNotExist:
        return None  # no entitlement configured for this grade/type/year — balance display shows nothing, not a zero
```

The Leave app's balance display calls `get_entitlement` per leave type instead of whatever it currently assumes — **this patches the Leave dashboard spec**, which needs its balance-fetching logic updated to call this instead of reading a flat field.

---

## 4. Implementation

### 4.1 New app

```bash
cd backend
python manage.py startapp directory
```

### 4.2 Files

```
backend/directory/
  provider.py          # the ABC + dataclasses (§3.1)
  factory.py            # get_organization_provider() (§3.2)
  fixtures/
    provider.py          # FixtureOrganizationDataProvider
    seed_data.json        # placeholder org/employee/grade/role data
  management/commands/
    sync_org_structure.py  # calls org.services.sync_org_structure_from_provider()
```

### 4.3 Patches to existing specs this unit requires

| Spec | Patch needed |
|---|---|
| Org-tree blueprint | `OrgUnit` gains `external_id`; `designated_approver` resolution during HR manual assignment becomes less relevant going forward — assignment is driven by the sync instead, though manual override may still be worth keeping for gaps the external data doesn't cover yet |
| Leave Configuration | Add `GradeLeaveEntitlement` model (§3.5), confirming the earlier correction that `LeaveType` itself carries no entitlement field |
| Leave dashboard | Balance section calls `get_entitlement` per leave type instead of its originally-assumed lookup |
| System Restructure | `hr-admin` module's scope shrinks — it's no longer building full employee-management CRUD, since that data is externally sourced; it becomes more about viewing/filtering staff (read-only against the provider) plus whatever LUANAR-LMS-specific admin actually belongs to HR (e.g. onboarding/temp-password flow, if that unit is built) |

### 4.4 Tests

- Fixture provider returns consistent, correctly-shaped data for every interface method.
- `sync_org_structure_from_provider` correctly creates units on first run and updates (not duplicates) on a second run with the same fixture data.
- A role holder with `employee_id=None` in fixture data results in `OrgUnit.designated_approver=None` — confirming the org-tree blueprint's vacancy-blocking behavior is correctly exercised by synced data, not just hand-created test data.
- `get_entitlement` returns `None` (not zero, not an exception) when no mapping exists for a given grade/type/year.
- Swapping `ORG_DATA_BACKEND` to a stub "api" value without a real implementation yet raises a clear, intentional error rather than silently falling back to fixtures — so nobody accidentally ships on fixture data in production without noticing.

---

## 5. Dependencies

**No new packages.** Plain Python ABCs/dataclasses, JSON fixture loading, existing Django patterns.

---

## 6. Verification checklist

- [ ] Every module that needs staff/grade/org data goes through `OrganizationDataProvider` — none reach into fixture data or a hypothetical future API directly.
- [ ] `sync_org_structure_from_provider` is idempotent — running it twice produces no duplicates.
- [ ] Vacant positions in fixture data correctly produce `designated_approver=None`, and the org-tree blueprint's existing submission-blocking behavior fires correctly against synced (not hand-created) data.
- [ ] `GradeLeaveEntitlement` correctly returns `None` for an unconfigured grade/type/year combination, and the Leave dashboard correctly omits that leave type's balance ring rather than showing a false zero.
- [ ] Employee identity reconciliation (§3.4) is resolved — confirm how a provider's external employee ID maps to a local `User` before building the sync, since this is a real prerequisite, not a detail to improvise during implementation.
- [ ] Switching `ORG_DATA_BACKEND` between values is a one-line settings change with no code changes required anywhere else in the codebase.
