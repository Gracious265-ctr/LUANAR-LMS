"use client";

import { useCallback, useEffect, useState } from "react";
import { CheckCheck } from "lucide-react";

import {
  listNotifications,
  markAllRead,
  markRead,
} from "@/lib/notifications/service";
import type { Notification } from "@/lib/notifications/types";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState, ErrorState } from "@/components/ui/states";

import { NotificationRow } from "./NotificationRow";

/**
 * The popover's body (unit 08 §2.4).
 *
 * The list is fetched fresh each time the content mounts — the content only
 * exists while the popover is open, so opening is the natural refresh point.
 * Read actions update the rows optimistically and poke the badge's refetch
 * immediately, so both the rows and the bell agree without reopening.
 */
export function NotificationPopoverContent({
  onNavigate,
  onCountChanged,
}: {
  onNavigate: () => void;
  /** The badge polls on its own, but a read action should land immediately. */
  onCountChanged: () => void;
}) {
  const [items, setItems] = useState<Notification[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    setItems(null);
    try {
      setItems(await listNotifications());
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load your notifications"
      );
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const unreadCount = items?.filter((n) => !n.is_read).length ?? 0;

  const handleMarkRead = useCallback(
    (id: string) => {
      setItems(
        (prev) =>
          prev?.map((n) => (n.id === id ? { ...n, is_read: true } : n)) ?? prev
      );
      markRead(id)
        .then(onCountChanged)
        .catch(() => {
          // Optimistic: the next open re-reads the server's truth.
        });
    },
    [onCountChanged]
  );

  const handleMarkAllRead = useCallback(() => {
    setItems((prev) => prev?.map((n) => ({ ...n, is_read: true })) ?? prev);
    markAllRead()
      .then(onCountChanged)
      .catch(() => {
        // Optimistic: the next open re-reads the server's truth.
      });
  }, [onCountChanged]);

  return (
    <div className="flex max-h-[24rem] flex-col">
      {/* The header (title + "Mark all read") only exists while something is
          unread — with nothing to act on there is nothing to offer (§2.4). */}
      {unreadCount > 0 && (
        <div className="flex items-center justify-between gap-3 border-b border-border-default px-4 py-3">
          <h2 className="text-sm font-semibold text-text-primary">
            Notifications
          </h2>
          <button
            type="button"
            onClick={handleMarkAllRead}
            className="shrink-0 text-xs font-medium text-brand-primary transition-colors hover:underline focus-ring"
          >
            Mark all read
          </button>
        </div>
      )}

      {error ? (
        <ErrorState
          title="Couldn't load notifications"
          message={error}
          onRetry={() => void load()}
          className="rounded-none border-0 p-6 shadow-none"
        />
      ) : items === null ? (
        <div className="space-y-3 p-4" role="status">
          <span className="sr-only">Loading notifications</span>
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-3/4" />
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          icon={<CheckCheck className="h-8 w-8 text-text-muted" />}
          title="You're all caught up"
          className="py-8"
        />
      ) : (
        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
          {items.map((notification) => (
            <NotificationRow
              key={notification.id}
              notification={notification}
              onMarkRead={handleMarkRead}
              onNavigate={onNavigate}
            />
          ))}
        </div>
      )}
    </div>
  );
}
