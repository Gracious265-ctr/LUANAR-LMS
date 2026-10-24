import { apiErrorMessage } from "@/lib/utils";

import type { Notification } from "./types";

/**
 * Browser-side access to the in-app notification API.
 *
 * Every call goes through the app's own `/api/notifications/*` proxies, which
 * forward to Django with the session cookie — the same shape Plans and
 * Approvals use, so no bearer token is handled in the browser.
 */

async function parse<T>(res: Response, fallback: string): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(apiErrorMessage(body) || fallback);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

/** The popover's recent window (newest first, capped server-side at 15). */
export async function listNotifications(): Promise<Notification[]> {
  const res = await fetch("/api/notifications/", { credentials: "include" });
  const data = await parse<Notification[]>(
    res,
    "Failed to load your notifications"
  );
  return Array.isArray(data) ? data : [];
}

/** The navbar badge's number. */
export async function getUnreadCount(): Promise<number> {
  const res = await fetch("/api/notifications/unread-count/", {
    credentials: "include",
  });
  const data = await parse<{ count: number }>(
    res,
    "Failed to load your notification count"
  );
  return data?.count ?? 0;
}

/** Marks one of the caller's own notifications read. */
export async function markRead(id: string): Promise<void> {
  const res = await fetch(`/api/notifications/${id}/mark-read/`, {
    method: "POST",
    credentials: "include",
  });
  await parse<void>(res, "Failed to mark the notification read");
}

/** Clears the caller's badge and every unread row. */
export async function markAllRead(): Promise<void> {
  const res = await fetch("/api/notifications/mark-all-read/", {
    method: "POST",
    credentials: "include",
  });
  await parse<void>(res, "Failed to mark your notifications read");
}
