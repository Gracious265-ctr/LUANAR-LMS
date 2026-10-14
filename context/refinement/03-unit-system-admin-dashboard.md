# Unit — System Admin Dashboard (Django Admin Extension)

read `context/AGENTS.md` before starting

## 1. Goal

Extend Django's built-in admin site (not the Next.js frontend) into a system-operations dashboard, using Django admin's own default look throughout. Visibility is role-gated in three tiers: the superuser (the developer) sees full system stats, health, and infrastructure internals plus superuser management; HR sees only an application/usage subset relevant to their job; any other staff account sees plain, unmodified Django admin with no dashboard additions. All reusing `django.contrib.admin` rather than building a parallel admin UI from scratch.

### Assumptions (flag if wrong)

| # | Assumption |
|---|---|
| A1 | "The existing Django one" means `django.contrib.admin`, already available since Django is in the stack — this unit customizes and extends it, it does not replace it with a custom-built admin panel. |
| A2 | This is a **separate surface** from the Next.js employee/HR/approver dashboards — reached at its own URL (e.g. `/system-admin/`), used only by engineering/IT, not by HR or regular staff. It intentionally does not follow the LUANAR blue/Inter/21st.dev design system — Django admin's own styling is acceptable and expected here, lightly branded at most. |
| A3 | "Super users like the admin" means Django's built-in superuser concept (`is_superuser=True`, full admin access) — not a new permission tier. If you actually want a *new* elevated-but-not-full-superuser role, flag it; that's a bigger change than this spec covers. |
| A4 | Three-tier visibility, confirmed: (1) **Superuser** (the developer) sees everything — full stats, system health, task queue, database internals, superuser management. (2) **HR** (identified via a Django Group named `HR`, assigned to specific staff accounts) sees a limited, HR-relevant stat subset only (§2.2) — no system health, no database/task-queue internals, no superuser management. (3) **Any other staff account** sees the standard Django admin model list with zero stat cards and zero health panel — plain admin, no dashboard additions at all. |
| A5 | Django-Q2 (confirmed stack) is the background task runner; "monitor the system" includes task queue health, since that's the one moving part most likely to silently fail in production. |

### Out of scope

Replacing Django admin's visual theme with the LUANAR design system, real-time push updates (polling is sufficient), external uptime monitoring/alerting (PagerDuty-style — this is an in-app dashboard, not an ops alerting pipeline), log aggregation UI (this surfaces counts/health, not a full log viewer — point to actual server logs for that).

---

## 2. Design

### 2.1 Where this lives

- URL: `/system-admin/` (or keep Django's default `/admin/` and just customize it — your call; a separate path avoids any confusion with a future staff-facing admin area under the same prefix).
- Built via a custom `AdminSite` subclass (`class LuanarAdminSite(admin.AdminSite)`), registered in place of the default, so all existing and future `ModelAdmin` registrations (users, applications, workflows, documents, etc.) continue to work unchanged — this unit adds an `index_template` override and new custom views, it does not re-register every model.
- Protected at the view level: `AdminSite.has_permission()` overridden to require `is_staff`; the stats/monitoring dashboard view additionally requires `is_superuser`.

### 2.2 Dashboard landing page — stat cards

Replace Django admin's default app-list index with a custom template showing a grid of stat cards above the normal model list — but which cards render depends entirely on who's looking (A4). The template receives a role-filtered stats dict; it never renders a card the current user isn't entitled to, rather than rendering everything and hiding it with CSS.

| Card | Data source | Visible to |
|---|---|---|
| Leave applications — total, by status (pending/approved/rejected) | `LeaveApplication` aggregate, once Units 13+ exist | HR + Superuser |
| Applications submitted today / this week | Same, date-filtered | HR + Superuser |
| Pending approvals (system-wide) | `ApplicationStage` where `status=pending`, once Unit 16 exists | HR + Superuser |
| Total employees / active employees (last 30 days) | `User`/`EmployeeProfile`, `last_login` | HR + Superuser |
| Documents stored — count, total storage used | `SupportingDocument`/`SupportingDocumentVersion`, once Unit 19 exists | Superuser only — storage internals, not an HR concern |
| Background task queue — pending, failed (last 24h) | Django-Q2's `OrmQ`/`Success`/`Failure` tables | Superuser only |
| Database size | `pg_database_size()` via a raw query | Superuser only |
| Database connection count | `pg_stat_activity` count | Superuser only |
| Recent errors (last 24h) | Count only, from Django's logging (§2.4) | Superuser only |

The HR-visible set is deliberately scoped to **what HR needs to do their job** (monitor application volume and backlog, see staffing-level signals) — nothing about infrastructure health, storage internals, or background task plumbing, since none of that is actionable or meaningful to HR and would only add noise/confusion. A plain staff account (not superuser, not in the `HR` group) sees none of these cards at all — just Django's normal app-list index, unchanged from stock Django admin.

Cards that depend on models from Units 13-19 should **degrade gracefully** if those apps aren't installed/migrated yet (catch the lookup, show "Not yet available" rather than crashing the whole dashboard) — this unit should be buildable and useful even if run before those units land.

### 2.3 System health section (superuser only)

Below the stat cards, a simple health-check panel, each item a colored dot (green/amber/red) plus a one-line status. This panel never renders for HR or plain staff — it does not appear in their DOM at all, not merely hidden by CSS:

- **Database** — a trivial query succeeds within a threshold (e.g. `SELECT 1` under 200ms).
- **Background tasks (Django-Q2)** — last successful task run within an expected window; failed-task count in the last 24h.
- **Storage (Supabase)** — a lightweight connectivity check (e.g. a bucket-list call) succeeds.
- **Email (SMTP)** — last successful send timestamp if available, or a connectivity check on demand rather than on every page load (SMTP checks are slow — don't run this on every dashboard refresh; make it a manual "Test connection" button instead).

This reuses the same service functions application code already uses to talk to these systems (the storage abstraction from Unit 1, the Django-Q2 task runner) — it does not reimplement separate health-check clients.

### 2.4 Error/activity visibility (superuser only)

- A simple count of ERROR-level log records in the last 24 hours, sourced from a lightweight `SystemLogEntry` model populated by a custom logging handler (or, simpler: just surface Django-Q2's own `Failure` table count plus a count from whatever error-tracking you already have, if any — don't build a new log-storage pipeline if one basically exists via Django-Q2 failures and server logs already).
- A link out to wherever real logs live (server log file path, or an external service if one is later added) rather than trying to render full log contents in-app.

### 2.5 Superuser / staff account creation (superuser only)

Django admin already supports creating users and toggling `is_staff`/`is_superuser` via the built-in `UserAdmin`. This unit adds safety rails on top rather than reinventing creation:

- Keep the standard Django admin "Add user" flow for creating accounts.
- **Promoting an existing account to `is_superuser=True`** gets an extra confirmation step: a custom admin action (not just toggling the checkbox and saving) that requires typing the target username to confirm, and is audited (§2.6). This prevents an accidental checkbox-and-save superuser grant.
- **Creating a brand-new superuser directly** (the `createsuperuser` equivalent via the UI) is restricted to existing superusers only — enforced via `has_add_permission` on the custom admin action, not just relying on Django's default permission model, since a misconfigured staff account shouldn't be able to mint new superusers.
- Every superuser grant/revoke is logged to the audit trail (§2.6), separately from Django admin's own built-in `LogEntry` history, since that history is easy to miss and isn't surfaced anywhere prominent.

### 2.6 Audit trail for admin actions (superuser only)

- Reuse the audit mechanism already established in Units 16-19 (actor, action, target, timestamp) rather than inventing a second audit system — add `system.superuser_granted`, `system.superuser_revoked`, `system.staff_access_granted` as new event types in the same table/service.
- A small "Recent admin actions" panel on the dashboard, visible only to superusers, surfaces the last ~20 of these specifically (superuser/staff changes), separate from Django's generic `LogEntry` (which logs every model edit and would be too noisy here).

### 2.7 Look and branding — Django's own, confirmed

Use Django admin's own default styling throughout, for every tier — no custom design system, no LUANAR tokens/Inter/21st.dev applied here. The only branding touch is `admin_site.site_header`, `site_title`, and `index_title` showing "LUANAR Leave System — Admin" instead of Django's default "Django administration" text. No color overrides, no custom CSS beyond what's strictly needed to lay out the stat-card grid and health panel using Django admin's existing CSS classes/variables. This keeps the build small and avoids maintaining a second design system for a developer-facing tool.

---

## 3. Implementation

### 3.1 Custom AdminSite (`config/admin.py` or `system_admin/admin.py`)

```python
from django.contrib.admin import AdminSite
from django.urls import path

class LuanarAdminSite(AdminSite):
    site_header = "LUANAR Leave System — Admin"
    site_title = "LUANAR Admin"
    index_title = "System Dashboard"

    def has_permission(self, request):
        return request.user.is_active and request.user.is_staff

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            # superuser-only; enforced inside the view itself, not just has_permission
            path("health/", self.admin_view(health_check_view), name="system-health"),
            path("health/test-email/", self.admin_view(test_email_view), name="system-test-email"),
        ]
        return custom + urls

    def index(self, request, extra_context=None):
        extra_context = extra_context or {}
        tier = get_dashboard_tier(request.user)  # "superuser" | "hr" | "plain"
        extra_context["dashboard_tier"] = tier
        if tier in ("superuser", "hr"):
            extra_context["stats"] = gather_dashboard_stats(tier)  # see §3.2
        if tier == "superuser":
            extra_context["health"] = gather_health_status()        # see §3.3
            extra_context["recent_admin_actions"] = get_recent_admin_actions()
        return super().index(request, extra_context)

admin_site = LuanarAdminSite(name="luanar_admin")


def get_dashboard_tier(user) -> str:
    if user.is_superuser:
        return "superuser"
    if user.groups.filter(name="HR").exists():
        return "hr"
    return "plain"
```

Register existing `ModelAdmin`s on `admin_site` instead of the default `admin.site`, and point `urls.py` at `admin_site.urls`. The `plain` tier gets `extra_context` with no `stats`/`health` keys at all — the template checks for key presence, not a boolean flag, so there's no path where a plain staff account's template render ever touches stat-gathering code.

### 3.2 Stats service (`system_admin/services.py`)

```python
HR_VISIBLE_KEYS = {"applications", "users_total", "users_active_30d"}

def gather_dashboard_stats(tier: str) -> dict:
    """tier is 'hr' or 'superuser' — 'plain' never calls this at all."""
    stats = {}

    stats["users_total"] = User.objects.count()
    stats["users_active_30d"] = User.objects.filter(
        last_login__gte=timezone.now() - timedelta(days=30)
    ).count()

    stats["applications"] = _safe_stat(lambda: {
        "total": LeaveApplication.objects.count(),
        "pending": LeaveApplication.objects.filter(status="pending").count(),
        "approved": LeaveApplication.objects.filter(status="approved").count(),
        "rejected": LeaveApplication.objects.filter(status="rejected").count(),
        "today": LeaveApplication.objects.filter(created_at__date=timezone.now().date()).count(),
    })

    if tier == "hr":
        # HR gets exactly the keys above and nothing else — return early
        return {k: v for k, v in stats.items() if k in HR_VISIBLE_KEYS}

    # superuser only, from here down
    stats["documents"] = _safe_stat(lambda: {
        "count": SupportingDocumentVersion.objects.filter(status="current").count(),
        "storage_bytes": SupportingDocumentVersion.objects.filter(status="current").aggregate(
            total=Sum("size_bytes"))["total"] or 0,
    })

    stats["tasks"] = {
        "pending": OrmQ.objects.count(),
        "failed_24h": Failure.objects.filter(stopped__gte=timezone.now() - timedelta(hours=24)).count(),
        "succeeded_24h": Success.objects.filter(stopped__gte=timezone.now() - timedelta(hours=24)).count(),
    }

    stats["database"] = {
        "size": _db_size(),
        "connections": _db_connection_count(),
    }

    return stats


def _safe_stat(fn):
    """Return the stat, or a 'not available' marker if the underlying app/model isn't installed yet."""
    try:
        return fn()
    except Exception:
        return None  # template renders "Not yet available" for None
```

The tier check happens server-side, in the service function, not just in the template — a `plain` or `hr` request never has the superuser-only ORM queries (`OrmQ`, `Failure`, `pg_stat_activity`) executed on its behalf, not merely hidden from the rendered HTML.

`_safe_stat` is the mechanism that lets this unit ship before Units 13-19 land — each stat degrades independently rather than the whole dashboard breaking on a missing model.

### 3.3 Health checks (`system_admin/health.py`)

```python
def gather_health_status() -> dict:
    return {
        "database": _check_database(),
        "tasks": _check_task_runner(),
        "storage": _check_storage(),
    }

def _check_database() -> dict:
    start = time.monotonic()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        elapsed_ms = (time.monotonic() - start) * 1000
        return {"status": "ok" if elapsed_ms < 200 else "degraded", "latency_ms": round(elapsed_ms)}
    except Exception as e:
        return {"status": "down", "error": str(e)}

def _check_task_runner() -> dict:
    last_success = Success.objects.order_by("-stopped").first()
    if not last_success:
        return {"status": "unknown", "detail": "No completed tasks yet"}
    stale = timezone.now() - last_success.stopped > timedelta(hours=1)
    return {"status": "degraded" if stale else "ok", "last_run": last_success.stopped}

def _check_storage() -> dict:
    try:
        storage = get_document_storage()  # Unit 1/19's abstraction
        storage.ping()  # add a lightweight ping/exists-check method to the interface if missing
        return {"status": "ok"}
    except Exception as e:
        return {"status": "down", "error": str(e)}
```

SMTP is deliberately **not** auto-checked on every page load (§2.3) — add a separate `POST /system-admin/health/test-email/` endpoint triggered by a button, sending a test email to the requesting superuser's own address.

### 3.4 Superuser promotion safety (`system_admin/actions.py`)

```python
@admin.action(description="Grant superuser status (requires confirmation)")
def grant_superuser(modeladmin, request, queryset):
    if not request.user.is_superuser:
        raise PermissionDenied("Only superusers can grant superuser status.")
    if "confirm_username" not in request.POST:
        return render(request, "admin/confirm_superuser_grant.html", {"users": queryset})
    for user in queryset:
        if request.POST["confirm_username"] != user.username:
            continue  # or reject the whole batch — single-user action is simpler/safer, consider restricting to one at a time
        user.is_superuser = True
        user.save(update_fields=["is_superuser"])
        audit_log(actor=request.user, action="system.superuser_granted", target=user)
```

Register this as a custom admin action on the `User` admin (registered on `admin_site`), restricted to superusers via `has_permission` checks, rather than relying on the default checkbox-in-form flow for this specific elevation.

### 3.5 Templates

- `templates/admin/index.html` — override to conditionally render above Django's default app-list, using only Django admin's own CSS classes/variables, no custom design system (§2.7):
  - `{% if stats %}` — the stat-card grid (HR gets the HR-visible card set, superuser gets the full set, driven entirely by what `gather_dashboard_stats` returned, not by separate template-level role checks)
  - `{% if health %}` — the health panel (only present for superuser)
  - `{% if recent_admin_actions %}` — the audit panel (only present for superuser)
  - A `plain` tier request has none of these context keys, so none of these blocks render — the template falls through to Django's unmodified default app-list.
- `templates/admin/confirm_superuser_grant.html` — the confirmation step from §3.4.

### 3.6 Settings

```python
ADMIN_SITE_HEADER = "LUANAR Leave System — Admin"
SYSTEM_ADMIN_URL_PREFIX = "system-admin/"  # or reuse "admin/" — your call
```

### 3.7 Tests

- Non-staff user gets 403/redirect on `/system-admin/`.
- **Plain staff** (is_staff, not superuser, not in `HR` group): index renders with zero stat cards and zero health panel — context has no `stats`/`health`/`recent_admin_actions` keys at all, not just hidden ones.
- **HR** (in `HR` group, not superuser): sees exactly the HR-visible stat cards (`applications`, `users_total`, `users_active_30d`) and nothing else — assert the returned dict's keys match `HR_VISIBLE_KEYS` exactly, and that no superuser-only ORM query (`OrmQ`, `Failure`, `pg_stat_activity`) is executed for this tier (mock/assert not called).
- **Superuser**: sees the full stat set, health panel, and recent-admin-actions panel.
- `gather_dashboard_stats("hr")` never triggers the documents/tasks/database queries even if called directly — confirm via mock assertion, not just by checking the returned dict shape.
- `gather_dashboard_stats()` degrades gracefully (returns `None` for a stat) when the underlying model/app isn't present — simulate by mocking the model lookup to raise.
- `grant_superuser` action: rejects a non-superuser actor (including HR); requires username confirmation before applying; writes the correct audit entry; a user not matching the confirmation string is not elevated.
- Health checks: each returns a sane status dict even when the underlying system (DB/tasks/storage) is unreachable — no unhandled exception bubbles up and breaks the page.
- SMTP test-email endpoint only fires on explicit POST, never on a GET/page-load, and only for superusers.

---

## 4. Dependencies

**No new required packages** — built entirely on Django's built-in admin, the existing Django-Q2 tables, and your existing storage abstraction and audit service.

---

## 5. Verification checklist

**Access control**
- [ ] Non-staff users cannot reach `/system-admin/` at all.
- [ ] Plain staff (not HR, not superuser) see the standard unmodified Django admin index — no stat cards, no health panel, no admin-actions panel.
- [ ] HR-group staff see exactly the HR-visible stat cards (applications, users) — nothing about documents, storage, task queue, database, or system health.
- [ ] Superuser sees the full dashboard: all stat cards, health panel, and recent-admin-actions panel.
- [ ] Only superusers can grant superuser status to another account; the action is rejected for anyone else, including HR.
- [ ] Superuser-only ORM queries are never executed for HR or plain-tier requests (not just hidden in the template).

**Stats dashboard**
- [ ] All stat cards render correctly once Units 13-19 models exist, for both HR and superuser tiers.
- [ ] Stat cards for not-yet-installed apps show "Not yet available" rather than erroring, if this unit is built before those units land.
- [ ] Numbers match a manual spot-check against the actual database (e.g. `LeaveApplication.objects.count()` in a shell matches the card).

**Health checks**
- [ ] Database, task runner, and storage checks each correctly report ok/degraded/down under both normal and simulated-failure conditions.
- [ ] SMTP check only runs on explicit button press, never automatically.
- [ ] A down dependency (e.g. storage unreachable) doesn't crash the whole dashboard — only that panel shows the failure.

**Superuser management**
- [ ] Standard "Add user" flow still works unchanged.
- [ ] Promoting an existing user to superuser requires the confirmation step (typed username), not just a checkbox-and-save.
- [ ] Every grant/revoke writes an audit entry visible in the "Recent admin actions" panel, distinct from Django's built-in `LogEntry`.
- [ ] A staff (non-superuser) account cannot create or promote a superuser via any path, including direct form submission bypassing the UI.

**Regression**
- [ ] All existing `ModelAdmin` registrations (users, applications, etc. as they're built) continue to work unchanged under the new `AdminSite`.
- [ ] Django's own built-in audit (`LogEntry`) continues to function alongside the new system-specific audit events.
