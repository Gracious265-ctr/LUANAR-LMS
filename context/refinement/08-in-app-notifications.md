# Unit — In-App Notifications

read `context/AGENTS.md` before starting

---

## 1. Goal

A bell icon in the top bar, visible on every page regardless of which module the user is in, showing an unread count. Clicking it opens a popover (not a page navigation) listing recent notifications, each linking to the relevant page, with the ability to mark one or all as read.

---

## 2. Design

### 2.1 What generates a notification

Every module that already has a "no-op event hook" placeholder (Units 16–19, Leave Plans, Leave Configuration, the org-tree blueprint) gets a **real** implementation here: instead of doing nothing, the hook creates a `Notification` row. This is the first unit that turns those hooks into something a user actually sees, ahead of/alongside the separate email-sending work.

| Source | Event | Recipient |
|---|---|---|
| Approvals | A stage becomes assigned to you (new pending item) | The newly-assigned approver |
| Approvals | Your submitted application was approved | The employee |
| Approvals | Your submitted application was rejected | The employee |
| Approvals | Your submitted application needs correction | The employee |
| Leave Plans | A plan reminder fires (mirrors the email, per the Plans spec) | The plan's employee |
| Leave Plans | A plan's follow-up reminder fires | The plan's employee |
| Organization | An acting assignment covering you starts | The acting employee |
| Documents | A required document is still missing close to submission (if/when that check exists as a standing reminder, not just inline form validation) | The employee |

This table is extensible — any future module can call the same `create_notification()` service rather than inventing its own mechanism. Not every module needs a notification; add one only where a user genuinely benefits from being told something happened without having to go look.

### 2.2 Data model

```
Notification
  recipient       FK -> User
  event_type      CharField  (e.g. "approval.assigned", "application.approved")
  message         CharField  (short, human-readable, e.g. "Your leave application was approved")
  link            CharField  (relative path to navigate to, e.g. "/leave/applications/abc123")
  is_read         Bool, default False
  created_at      DateTime
```

No per-notification "dismiss" distinct from "read" — read and visible-but-acknowledged are the same state here, kept simple. Notifications are not deleted; they age out of the popover's default view (§2.4) but remain queryable.

### 2.3 Navbar icon and badge

- A bell icon (Lucide `Bell`) in the top bar, present on every page across every module — lives in the shared app shell, not per-module.
- Unread count as a small badge on the icon (a filled circle with the number, or just a dot if the count is large — cap the displayed number at 9+ rather than showing an unbounded number).
- No badge at all when the unread count is 0 — same "absence over zero" principle used everywhere else in this project.
- Polling: refetch the unread count every ~30 seconds while the app is open, so the badge stays reasonably current without needing real-time infrastructure (websockets) for something this low-stakes.

### 2.4 The popover

- **Positioning — important, do not confuse with the Dialog component:** this must render as a small panel anchored directly below/beside the bell icon (top-right corner of the screen, since the bell lives in the top bar), not centered on the screen with a dark overlay behind it. It is a popover/dropdown, not a modal. If the project's existing Dialog component is reused here without changing its positioning behavior, it will render incorrectly (centered, with an overlay) — use a genuine anchored-popover primitive (e.g. Radix Popover, not Radix Dialog) even if its visual styling (rounded-xl, shadow-lg, fade+scale entrance) matches Dialog's conventions. Styling conventions are shared; positioning behavior is not.
- Opens on click, anchored to the bell icon — a popover/dropdown panel, not a page navigation. This keeps it reachable from anywhere in 1 click, from any module, at any time. No background overlay/dimming behind it, unlike a Dialog — the rest of the page stays fully visible and interactive while it's open.
- Shows the most recent ~15 notifications, newest first, unread ones visually distinct (bolder text, a small unread-indicator dot) from already-read ones, which appear muted.
- Each row: short message, relative timestamp (reusing the `relativeTime` helper and hover-for-absolute pattern from the earlier UI/UX Phase 2 unit), and is clickable — clicking navigates to `link` **and** marks that notification read in the same action, matching how a real user actually behaves (they clicked it because they want to see it, not because they want to separately mark it read first).
- Header row: "Notifications" title plus a "Mark all read" action, visible only when there's at least one unread notification.
- Empty state (no notifications at all, or none in the recent window): the existing `EmptyState` component, small/compact variant appropriate for a popover — "You're all caught up," no action button needed here (there's nothing to do).
- Closing: clicking outside the popover, pressing Escape, or navigating away all close it — standard popover behavior, no special handling needed.

### 2.5 Click budget

| Flow | Clicks |
|---|---|
| Open the popover | **1**, from anywhere |
| View a notification's linked page | **2** total (open popover, click notification — marks read as part of the same click, not an extra step) |
| Mark one notification read without navigating | **2** total (open popover, click a small inline mark-read affordance on the row, separate from clicking the row's main text/link area) |
| Mark all as read | **2** total (open popover, click "Mark all read") |

All comfortably within budget — this is in fact one of the fastest-to-reach features in the whole system by design, since it's meant to be a quick glance, not a destination.

---

## 3. Implementation

### 3.1 Backend model (`backend/notifications/models.py`)

```python
class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    event_type = models.CharField(max_length=100)
    message = models.CharField(max_length=255)
    link = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["recipient", "is_read", "-created_at"])]
```

### 3.2 Service (`backend/notifications/services.py`)

```python
def create_notification(recipient, event_type: str, message: str, link: str) -> Notification:
    return Notification.objects.create(
        recipient=recipient, event_type=event_type, message=message, link=link
    )

def get_recent_notifications(user, limit=15) -> list[Notification]:
    return Notification.objects.filter(recipient=user).order_by("-created_at")[:limit]

def get_unread_count(user) -> int:
    return Notification.objects.filter(recipient=user, is_read=False).count()

def mark_read(notification_id: str, user) -> None:
    Notification.objects.filter(id=notification_id, recipient=user).update(is_read=True)

def mark_all_read(user) -> None:
    Notification.objects.filter(recipient=user, is_read=False).update(is_read=True)
```

### 3.3 Wiring the existing no-op hooks

Each module's existing no-op event hook (from Units 16–19, Leave Plans, etc.) gets one line added, calling `create_notification` with that event's appropriate message/link:

```python
# example: inside approvals' decision-recording service, where a no-op hook currently sits
def on_application_decided(application, decision):
    ...  # existing state-transition logic, unchanged
    if decision.outcome == "approved":
        create_notification(
            recipient=application.employee,
            event_type="application.approved",
            message=f"Your {application.leave_type.name} application was approved",
            link=f"/leave/applications/{application.id}",
        )
    elif decision.outcome == "rejected":
        create_notification(
            recipient=application.employee,
            event_type="application.rejected",
            message=f"Your {application.leave_type.name} application was rejected",
            link=f"/leave/applications/{application.id}",
        )
    # ... correction_required follows the same shape
```

This is a small, additive patch to each already-built module — never a rewrite of its existing logic, just one new call where a no-op currently sits.

### 3.4 API (`backend/notifications/views.py`, `urls.py`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/notifications/?unread_only=true` | Recent notifications (§2.4's list) |
| GET | `/api/notifications/unread-count/` | Just the count, for the badge polling |
| POST | `/api/notifications/{id}/mark-read/` | Mark one read |
| POST | `/api/notifications/mark-all-read/` | Mark all read |

All scoped to `recipient=request.user` — never another user's notifications, enforced the same way as every other personal-data endpoint in this project.

### 3.5 Frontend (`frontend/components/notifications/`)

```
frontend/components/notifications/
  NotificationBell.tsx       // the navbar icon + badge, lives in the shared app shell
  NotificationPopover.tsx     // the dropdown panel itself
  NotificationRow.tsx
```

```tsx
// NotificationBell.tsx — lives in the shared top bar, not per-module
export function NotificationBell() {
  const { data: unreadCount } = useUnreadCount(); // polls every 30s
  const [open, setOpen] = useState(false);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button className="relative rounded-full p-2 hover:bg-muted transition-colors" aria-label="Notifications">
          <Bell className="h-5 w-5" />
          {unreadCount > 0 && (
            <span className="absolute -top-0.5 -right-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-medium text-white">
              {unreadCount > 9 ? "9+" : unreadCount}
            </span>
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 rounded-xl p-0 shadow-lg">
        <NotificationPopoverContent onNavigate={() => setOpen(false)} />
      </PopoverContent>
    </Popover>
  );
}
```

Use the project's existing Popover primitive if one already exists; otherwise add Radix's `@radix-ui/react-popover` (distinct from whatever Dialog is built on) and build the minimal anchored popover following the same token conventions (rounded-xl, shadow-lg, fade+scale entrance) already used for Dialog — **matching Dialog's look, not its centered/overlay positioning behavior**. `align="end"` in the example above is what keeps it right-aligned under the bell icon rather than stretching across the screen; do not remove it.

`NotificationRow` click handler calls `mark-read` and navigates in one action:

```tsx
function handleClick(notification: Notification) {
  if (!notification.is_read) markRead(notification.id); // fire and forget, optimistic
  router.push(notification.link);
  onNavigate(); // closes the popover
}
```

### 3.6 Settings

```python
NOTIFICATION_POLL_INTERVAL_SECONDS = 30  # frontend reads this via a config endpoint, or hardcodes it — either is fine at this scale
```

### 3.7 Tests

- `create_notification` correctly creates a row with the right recipient/message/link.
- `get_unread_count` and `get_recent_notifications` are correctly scoped per-user — one user never sees another's notifications.
- `mark_read` only affects the specified notification and only for its actual recipient (a user cannot mark someone else's notification read by guessing an ID).
- `mark_all_read` affects only the requesting user's unread notifications.
- Each wired hook (§3.3) actually creates the correct notification on the corresponding real event (approval decided, plan reminder fired, etc.) — test at least one per source module.
- Frontend: badge shows no element at all when count is 0, shows "9+" correctly when count exceeds 9, popover empty state renders when there are no notifications, clicking a row both navigates and marks it read.

---

## 4. Dependencies

**No new packages** if a Popover/Dialog primitive already exists in the project (likely, via 21st.dev/Radix). If not, add the Radix popover primitive the same way Dialog was originally added.

---

## 5. Verification checklist

**Core functionality**
- [ ] Bell icon with correct unread badge appears on every page, across every module.
- [ ] Badge shows nothing at 0, the correct number at 1–9, "9+" beyond that.
- [ ] Clicking the bell opens the popover from anywhere in 1 click.
- [ ] Clicking a notification navigates to its link and marks it read in one action.
- [ ] "Mark all read" clears the badge and visually updates every row in the popover without needing to reopen it.
- [ ] Empty state renders correctly when there are no notifications.

**Scoping and security**
- [ ] A user only ever sees their own notifications — verified across two different accounts.
- [ ] `mark-read` cannot be used to mark another user's notification as read by ID guessing.

**Integration**
- [ ] Every event listed in §2.1's table actually produces a notification when triggered for real (not just in isolated unit tests) — verified end to end for at least Approvals and Leave Plans.
- [ ] Wiring a hook never altered the underlying module's existing business logic — only added the one new notification call.

**3-click rule**
- [ ] Every flow in §2.5 matches its stated click count.

**Regression**
- [ ] No existing Unit 13-19 or later-module functionality changed beyond the additive hook wiring.
