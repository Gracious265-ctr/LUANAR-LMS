"use client";

import { useCallback, useEffect, useState } from "react";

import {
  type LeaveApplication,
  getLeaveApplications,
} from "@/lib/leave-api";

export function useLeaveApplications(statusFilter?: string) {
  const [applications, setApplications] = useState<LeaveApplication[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await getLeaveApplications(statusFilter);
        if (cancelled) return;
        setApplications(data.results);
        setError(null);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Failed to load applications");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [statusFilter]);

  const refetch = useCallback(() => {
    setLoading(true);
    getLeaveApplications(statusFilter)
      .then((data) => {
        setApplications(data.results);
        setError(null);
      })
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : "Failed to load applications")
      )
      .finally(() => setLoading(false));
  }, [statusFilter]);

  return { applications, loading, error, refetch };
}