"use client";

import { useCallback, useEffect, useState } from "react";

import {
  type LeaveApplication,
  getLeaveApplication,
} from "@/lib/leave-api";

export function useLeaveApplication(id: string | null) {
  const [application, setApplication] = useState<LeaveApplication | null>(null);
  const [loading, setLoading] = useState(() => Boolean(id));
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    const fetchId = id;
    let cancelled = false;
    async function load() {
      try {
        const data = await getLeaveApplication(fetchId);
        if (cancelled) return;
        setApplication(data);
        setError(null);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Failed to load application");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [id]);

  const refetch = useCallback(() => {
    if (!id) return;
    setLoading(true);
    getLeaveApplication(id)
      .then((data) => {
        setApplication(data);
        setError(null);
      })
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : "Failed to load application")
      )
      .finally(() => setLoading(false));
  }, [id]);

  return { application, loading, error, refetch, setApplication };
}