"use client";

import { useCallback, useEffect, useState } from "react";

import { getUnreadCount } from "@/lib/notifications/service";

/** Badge freshness: one tiny GET while the app is open (unit 08 §2.3). */
export const NOTIFICATION_POLL_INTERVAL_MS = 30_000;

/**
 * The navbar bell's unread count, fetched on mount and re-polled every 30
 * seconds. A failed poll keeps the last known count rather than clearing the
 * badge — a transient error should not make unread work disappear.
 */
export function useUnreadCount() {
  const [data, setData] = useState(0);

  const refetch = useCallback(
    () => getUnreadCount().then(setData).catch(() => {}),
    []
  );

  useEffect(() => {
    void refetch();
    const timer = setInterval(() => void refetch(), NOTIFICATION_POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [refetch]);

  return { data, refetch };
}
