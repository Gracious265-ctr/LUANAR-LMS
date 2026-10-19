"use client";

import { useCallback, useEffect, useState } from "react";

import { listPlans } from "@/lib/plans/service";
import type { LeavePlan } from "@/lib/plans/types";

/**
 * The caller's own plans (My Plans).
 *
 * Mirrors `useLeaveDashboard`: a settled first paint (loading → data), a
 * `cancelled` guard so a fast navigation does not set state on an unmounted
 * tree, and `refetch` so the list can be re-read after a cancel without a full
 * reload.
 */
export function usePlans() {
  const [data, setData] = useState<LeavePlan[] | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setIsLoading(true);
    try {
      const result = await listPlans();
      setData(result);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load your plans");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function initial() {
      try {
        const result = await listPlans();
        if (cancelled) return;
        setData(result);
        setError(null);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Failed to load your plans");
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }
    initial();
    return () => {
      cancelled = true;
    };
  }, []);

  return { data, isLoading, error, refetch: load };
}
