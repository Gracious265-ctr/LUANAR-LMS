# Unit 22 — Email Notifications

> Read `context/AGENTS.md` before starting. Session command:
> `DJANGO_SETTINGS_MODULE=config.settings.test TEST_DB_NAME=test_luanar_leave_22 uv run manage.py test notifications workflows users leave --keepdb --parallel auto` (from `backend/`), plus `npm test` from `frontend/`.
> This unit only specs the **notification/email system**. It does NOT build balance deduction or approved-document generation (Unit 23), audit aggregation (Unit 24), or workflow routing (Unit 21). It depends on the event seams Units 14–19 already provide (they are currently no-ops).
> **Sessions:** can run in its own worktree parallel to Unit 19/20 sessions; it does not touch `workflows/` decision logic, only the `emit_*` hooks.

## Goal

Connect system events to email via **Google SMTP for development**, replaceable
with LUANAR institutional SMTP through configuration. A real leave application,
approval decision, cancellation, delegation or reassignment triggers a
queryable, templated email to the right people, with delivery failures logged
and visible to HR.

## Design

### Current state (what hooks exist today)

- `notifications/` app is an **empty shell** (`models.py`, `views.py`, `tests.py` placeholders); it is installed in `INSTALLED_APPS`.
- `config/settings/base.py`: `EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"` (console for dev). `Q_CLUSTER` uses the Postgres ORM broker (`"orm": "default"`), workers 4, timeout 60s. `users/tasks.py::ping` is the template for a django-q2 task (`async_task("users.tasks.ping")`).
- Event seams (currently fire-and-forget no-ops, typed + documented for this unit):
  - `leave_application_submitted` signal (`leave/signals.py`) fired on commit by `submission.submit_application`.
  - `workflows/events.py::emit_approval_event(ApprovalEvent)` — kinds `decision_recorded`, `stage_assigned`, `application_finalised`; dispatched by `workflows/approval.py::decide`.
  - `leave/cancellations/events.py::emit(CancellationEvent)` — names `cancellation.requested`, `.withdrawn`, `.stage_approved`, `.approved`, `.rejected`; dispatched by the cancellation services. `CancellationRequest.employee_notification_state` exists for read-back (see §4).
  - `workflows/services.py` delegation approve/reject/cancel and `reassign_application` (`services.py:402`) have **no** event seam yet — the notification service must be called by these paths (or a new typed event added; prefer adding a small `DelegationEvent`/`ReassignmentEvent` in `workflows/events.py` following the existing shape).

### Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Dev email backend | Google SMTP via env vars (host `smtp.gmail.com`, port `587`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`), enforced with a `SEND_EMAILS`-style guard so tests stay hermetic | User decision — matches build plan Unit 22 |
| Replaceability | All SMTP settings from env; swap backend/host/user/password to institutional SMTP via `.env` without code change | Build plan requirement |
| Test backend | `.test` settings keep console/locmem backend; no real SMTP in tests | Existing `config/settings/test.py` convention |
| Delivery mechanism | `notifications.services.send_notification` persists a `Notification` row then enqueues a django-q2 task (`notifications.tasks.deliver_notification`) | Queryable record + async delivery via existing ORM broker (no Redis — architecture decision) |
| Failure handling | Task catches send exceptions, flips `status=failed`, records `error` + `attempts`; a periodic/scheduled re-attempt or HR-visible failure list is optional (see §5) | "Delivery failure logging + HR notification" from build plan |
| Templates | Reusable plain-text (and minimal HTML) builders in `notifications/templates.py` keyed by event name | Configurable sender + reusable templates from build plan |
| Sender | `DEFAULT_FROM_EMAIL` from env, default `"LUANAR Leave <noreply@luanar.ac.mw>"` | Configurable sender |

### Recipients per event (derived from existing payloads)

| Event / seam | Recipients |
|---|---|
| Submission | workflow members (`workflow_provider.get_workflow_member_user_ids`) + employee (to self: reference assigned) |
| `stage_assigned` | the assigned approver for that stage |
| `decision_recorded` (approve/reject/return) | employee + next assigned approver (if any) |
| `application_finalised` | employee |
| Cancellation requested/approved/rejected/withdrawn/stage_approved | employee + cancellation workflow approvers (from the event `recipient_user_ids`) |
| Delegation approved/rejected/cancelled | the approver (and delegate when known) |
| Reassignment | the new `to_approver` + employee |

Every `event.payload` already carries enough for subject+body; the notification
service merges `payload` into templates and never re-queries business logic.

## Implementation

### 1. `Notification` model — `backend/notifications/models.py`

```python
class Notification(models.Model):
    class Channel(models.TextChoices):
        EMAIL = "email", "Email"

    class Status(models.TextChoices):
        ENQUEUED = "enqueued", "Enqueued"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    event_type = models.CharField(max_length=60)      # e.g. "approval.stage_assigned"
    recipient = models.ForeignKey("users.User", on_delete=models.CASCADE, related_name="notifications")
    channel = models.CharField(max_length=10, choices=Channel.choices, default=Channel.EMAIL)
    email_to = models.EmailField()
    subject = models.CharField(max_length=255)
    body = models.TextField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ENQUEUED)
    attempts = models.PositiveSmallIntegerField(default=0)
    error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    # correlation for queries/audit
    application_id = models.UUIDField(null=True, blank=True)
    target_object_id = models.UUIDField(null=True, blank=True)  # flexible correlator

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"])]
```

Migration `0001_initial` in `notifications`.

### 2. Service — `backend/notifications/services.py`

```python
def send_notification(*, event_type, recipients, subject, body,
                      application_id=None, target_object_id=None,
                      send_sync_callbacks=()):
```

- `recipients` = list of users; skip users with no email or not active (`User.objects.filter(pk__in=ids).exclude(email="")`).
- Creates one `Notification` row per recipient (status `ENQUEUED`), then enqueues delivery through django-q2:

```python
async_task("notifications.tasks.deliver_notification", notification_id)
```

- Returns the created rows. In tests, callers run the task synchronously (or patch `async_task`) — do not send real email.

### 3. Task — `backend/notifications/tasks.py`

```python
def deliver_notification(notification_id: int):
```

- `select_for_update` the row, `attempts += 1`.
- `send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [email_to], fail_silently=False)`.
- On success: `status=SENT`, `sent_at=now`. On exception: `status=FAILED`, `error=str(exc)`.
- Reuse the established django-q2 pattern (`users/tasks.py`).

### 4. Event subscribers — hook the seams

- `backend/notifications/subscribers.py`: `on_application_submitted(sender, application, **_)` connected to `leave_application_submitted` (in `notifications/apps.py::ready`).
- `emit_approval_event` (`workflows/events.py`) — replace the no-op with a call that maps `ApprovalEvent.kind` → `send_notification(...)` (keep the dataclass contract unchanged; the function may stay a thin dispatcher).
- `leave/cancellations/events.py::emit` — same pattern; also honor `CancellationRequest.employee_notification_state` transitions via `set_notification_state` (already defined).
- Add `DelegationEvent` / `ReassignmentEvent` to `workflows/events.py` and call them from delegation approve/reject/cancel and `reassign_application` — mirror `ApprovalEvent` shape (`frozen dataclass`, `emit_*` dispatcher). Wire subscribers for delegation/reassignment emails. Keep **unit 21 decisions intact**: reassignment already writes the spine.

`apps.py::ready` connects receivers to `leave_application_submitted` and to a lightweight dispatcher resolved via settings (`NOTIFICATION_DISPATCHER` dotted path defaulting to "on") so tests can disable it deterministically.

### 5. HR visibility for failures

Optional depth 1 (recorded but not blocking): a small `NotificationAdmin` + `GET /api/notifications?status=failed` view (IsAuthenticated + HR-only permission) listing failed deliveries. If time-boxed, keep just the admin (Django admin already lists `notifications.Notification`); document the API as a TODO for Unit 24's audit surface. A scheduled retry (`django_q.schedule`) is out of scope — note it in the tracker.

### 6. Settings — `backend/config/settings/base.py`

- Email via env with Google SMTP defaults (email must **never** be sent from `.test` runs):

```python
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="LUANAR Leave <noreply@luanar.ac.mw>")
```

- `.env.example` additions: `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`.
- `.test` settings keep console/locmem backend (existing `config/settings/test.py` / add `EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"` if not present).

### 7. Tests

- `backend/notifications/tests.py`: `send_notification` persists rows and enqueues (patch `notifications.tasks.async_task`); task marks SENT on success and FAILED with error on exception; `deliver_notification` is idempotent-ish on rerun; subscribers: submission sends the submission email to workflow members, approval decisions send decision/stage emails, final approval notifies employee, cancellation emails flow, delegation/reassignment events send. Use `django.test` `override_settings(EMAIL_BACKEND="locmem")` and capture `outbox`.
- Real "Google SMTP dev default" is an **env/runtime** behaviour — tested by configuration-read tests (`EMAIL_HOST == "smtp.gmail.com"` when env unset) rather than sending network mail.

## Dependencies

- No new packages (django-q2 already installed with `async_task`; `send_mail` is stdlib Django). Google SMTP credentials are runtime env, not code.
- Not listed in `Dependencies` of the build plan as a package; if `django-q2`'s `Scheduler` or a retry helper needs a bump, note it in the tracker.

## Verification checklist

- `TEST_DB_NAME=test_luanar_leave_22 DJANGO_SETTINGS_MODULE=config.settings.test uv run manage.py test notifications workflows users leave --keepdb --parallel auto` green.
- Notification model/admin accessible in Django admin; `GET /api/notifications/?status=failed` (if built) returns HR-filtered failed rows.
- Manual dev (Google SMTP credentials in `.env`): submit an application → approver receives "new application assigned" email; approve first stage → next approver + employee notified; final approve → employee notified; rejection/correction/resubmission emails fire; cancellation request + decision emails fire; delegation approve sends; reassignment notifies the new approver.
- Frontend unaffected unless optional failure-list UI is added — if so, `npm test`, `tsc`, `eslint`, `npm run build` green.
- `manage.py check` clean; `makemigrations` yields only `notifications` migrations.