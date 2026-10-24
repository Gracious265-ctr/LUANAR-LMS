"use client";

import { Check } from "lucide-react";
import { useRouter } from "next/navigation";

import { relativeTime } from "@/lib/notifications/format";
import type { Notification } from "@/lib/notifications/types";
import { cn } from "@/lib/utils";

/**
 * One notification in the popover.
 *
 * The row's main area does what a real click means: follow the link and mark
 * the notification read in the same action (§2.5). The separate tick on an
 * unread row is the "mark read without going there" affordance, which is why
 * it sits outside the row button rather than nested inside it.
 */
export function NotificationRow({
  notification,
  onMarkRead,
  onNavigate,
}: {
  notification: Notification;
  /** Optimistically clears the row and the badge before the server answers. */
  onMarkRead: (id: string) => void;
  /** Closes the popover once the row's link has been followed. */
  onNavigate: () => void;
}) {
  const router = useRouter();
  const { label, absolute } = relativeTime(notification.created_at);
  const unread = !notification.is_read;

  function handleOpen() {
    if (unread) onMarkRead(notification.id);
    router.push(notification.link);
    onNavigate();
  }

  return (
    <div className="border-b border-border-default last:border-b-0">
      <div className="flex items-start gap-1">
        <button
          type="button"
          onClick={handleOpen}
          className="flex min-w-0 flex-1 items-start gap-2 px-4 py-3 text-left transition-colors hover:bg-surface-hover focus-ring"
        >
          {/* The dot slot is always present so read and unread rows keep the
              same left edge; only an unread row fills it. */}
          <span className="mt-1.5 w-1.5 shrink-0 self-start">
            {unread && (
              <span
                className="block size-1.5 rounded-full bg-brand-primary"
                aria-hidden="true"
              />
            )}
          </span>
          <span className="min-w-0 flex-1">
            <span
              className={cn(
                "block break-words text-sm",
                unread
                  ? "font-semibold text-text-primary"
                  : "font-normal text-text-muted"
              )}
            >
              {notification.message}
            </span>
            <time
              dateTime={notification.created_at}
              title={absolute}
              className="mt-0.5 block text-xs text-text-muted"
            >
              {label}
            </time>
          </span>
        </button>

        {unread && (
          <button
            type="button"
            onClick={() => onMarkRead(notification.id)}
            aria-label={`Mark as read: ${notification.message}`}
            title="Mark as read"
            className="mr-2 mt-2.5 shrink-0 rounded-sm p-1.5 text-text-muted transition-colors hover:bg-surface-hover hover:text-text-primary focus-ring"
          >
            <Check className="h-3.5 w-3.5" aria-hidden="true" />
          </button>
        )}
      </div>
    </div>
  );
}
