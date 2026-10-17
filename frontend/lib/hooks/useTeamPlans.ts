"use client";

import { useCallback, useEffect, useState } from "react";

import { getScopeOptions, getTeamPlans } from "@/lib/plans/service";
import type { PlanScope, TeamPlansResponse } from "@/lib/plans/types";

const monthIso = (d: Date = new Date()) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;

/**
 * The Team Plans calendar's data and selectors (spec 3.6).
 *
 * A regular employee's scope list is a single entry (their own unit), so the
 * scope dropdown renders only when the list actually widens — a unit head's.
 * `month` is a `YYYY-MM` string the backend parses; the hook keeps it in
 * `YYYY-MM` so paging a month never round-trips through a `Date`.
 *
 * The calendar request is gated on a resolved scope. A person with no scope at
 * all — most visibly the bootstrap superuser, who belongs to no team and holds
 * no assignment — has nothing to view, and the backend answers a scoped request
 * with a 404 by design. Firing one anyway would turn "you have no team yet" into
 * a spurious error, so the hook waits for the scope list and requests nothing
 * when it comes back empty. `scopesLoaded` lets the caller tell "still loading"
 * apart from "no team to show".
 *
 * `isLoading` is flipped on by the two things that trigger a read — picking a
 * scope and paging a month — and off once the request settles, so the effect
 * itself never sets state synchronously (the same shape `usePlans` uses).
 */
export function useTeamPlans() {
  const [scopes, setScopes] = useState<PlanScope[]>([]);
  const [scope, setScope] = useState<string | null>(null);
  const [scopesLoaded, setScopesLoaded] = useState(false);
  const [month, setMonth] = useState<string>(() => monthIso());
  const [data, setData] = useState<TeamPlansResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getScopeOptions()
      .then((options) => {
        if (cancelled) return;
        setScopes(options);
        setScope((current) => current ?? options[0]?.id ?? null);
        // Nothing to view: stop loading here rather than in the calendar
        // effect, which returns early when there is no scope.
        if (options.length === 0) setIsLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Failed to load scopes");
        setIsLoading(false);
      })
      .finally(() => {
        if (!cancelled) setScopesLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function run() {
      if (!scopesLoaded || !scope) return;
      try {
        const result = await getTeamPlans({ scope, month });
        if (cancelled) return;
        setData(result);
        setError(null);
      } catch (err) {
        if (cancelled) return;
        setError(
          err instanceof Error ? err.message : "Failed to load the team calendar"
        );
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }
    run();
    return () => {
      cancelled = true;
    };
  }, [scope, month, scopesLoaded]);

  const load = useCallback(async () => {
    if (!scopesLoaded || !scope) return;
    setIsLoading(true);
    try {
      const result = await getTeamPlans({ scope, month });
      setData(result);
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load the team calendar"
      );
    } finally {
      setIsLoading(false);
    }
  }, [scope, month, scopesLoaded]);

  const changeScope = useCallback((next: string | null) => {
    setIsLoading(true);
    setScope(next);
  }, []);

  const shiftMonth = useCallback((delta: number) => {
    setIsLoading(true);
    setMonth((current) => {
      const [y, m] = current.split("-").map(Number);
      const next = new Date(y, m - 1 + delta, 1);
      return `${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, "0")}`;
    });
  }, []);

  return {
    scopes,
    scope,
    setScope: changeScope,
    scopesLoaded,
    month,
    shiftMonth,
    data,
    isLoading,
    error,
    refetch: load,
  };
}
