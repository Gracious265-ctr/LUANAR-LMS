"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  type LeaveApplication,
  type LeaveApplicationFilters,
  getLeaveApplications,
} from "@/lib/leave-api";

export function useLeaveApplications(filters: LeaveApplicationFilters = {}) {
  const { status, excludeStatus } = filters;
  const [applications, setApplications] = useState<LeaveApplication[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // The row removed by `removeLocal`, held with its position so a failed
  // delete can put it back where it was (spec 3.5 rollback).
  const removedRef = useRef<
    { item: LeaveApplication; index: number } | null
  >(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await getLeaveApplications({ status, excludeStatus });
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
  }, [status, excludeStatus]);

  /**
   * Optimistically drop one application from the list without entering the
   * loading state, so a delete feels immediate instead of flashing skeletons.
   * Pair with `restoreLocal` when the request fails.
   */
  const removeLocal = useCallback(
    (id: string) => {
      const index = applications.findIndex((app) => app.id === id);
      if (index === -1) return;
      removedRef.current = { item: applications[index], index };
      setApplications(applications.filter((app) => app.id !== id));
    },
    [applications]
  );

  /** Put back the row `removeLocal` took out, at its original position. */
  const restoreLocal = useCallback(() => {
    const removed = removedRef.current;
    if (!removed) return;
    removedRef.current = null;
    setApplications((prev) =>
      prev.some((app) => app.id === removed.item.id)
        ? prev
        : [
            ...prev.slice(0, removed.index),
            removed.item,
            ...prev.slice(removed.index),
          ]
    );
  }, []);

  /**
   * Reload from the server. `silent` skips the loading flag, so callers that
   * just mutated something (e.g. a submission that already shows its own
   * confirmation) refresh in place instead of replacing the page with
   * skeletons.
   */
  const refetch = useCallback(
    (options?: { silent?: boolean }) => {
      if (!options?.silent) setLoading(true);
      getLeaveApplications({ status, excludeStatus })
        .then((data) => {
          setApplications(data.results);
          setError(null);
        })
        .catch((err: unknown) =>
          setError(err instanceof Error ? err.message : "Failed to load applications")
        )
        .finally(() => setLoading(false));
    },
    [status, excludeStatus]
  );

  return { applications, loading, error, refetch, removeLocal, restoreLocal };
}
