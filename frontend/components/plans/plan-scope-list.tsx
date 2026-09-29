"use client";

import { Loader2, RefreshCw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { planScopeTitle, fetchMyPlans } from "@/lib/plans/service";
import type { PlanRow } from "@/lib/plans/types";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/states";

import { PlanCard } from "./plan-card";

export function PlanScopeList({ scope }: { scope: "team" | "department" }) {
  const [plans, setPlans] = useState<PlanRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    fetchMyPlans(scope)
      .then((result) => {
        if (cancelled) return;
        if (result.ok) {
          setPlans(result.data.results);
          setError("");
        } else {
          setError(result.message);
        }
      })
      .catch(() => {
        if (!cancelled) setError("Failed to load plans.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [scope, reloadKey]);

  const title = useMemo(() => planScopeTitle(scope), [scope]);

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold tracking-tight text-text-primary">{title}</h2>
            <p className="text-text-secondary">
              {scope === "team"
                ? "Approved plans from colleagues in your department and grade."
                : "Approved plans from across your department."}
            </p>
          </div>
          <Button
            type="button"
            onClick={() => setReloadKey((n) => n + 1)}
            aria-label="Refresh"
            variant="ghost"
            size="icon"
            className="h-auto w-auto p-1"
          >
            <RefreshCw className="size-4" />
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-10">
          <Loader2 className="size-5 animate-spin text-text-muted" />
        </div>
      ) : error ? (
        <EmptyState
          title="Could not load plans"
          description={error}
          action={
            <Button variant="secondary" onClick={() => setReloadKey((n) => n + 1)}>
              Try again
            </Button>
          }
        />
      ) : plans.length === 0 ? (
        <EmptyState
          title="No plans to show"
          description="No approved plans match this view yet."
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {plans.map((plan) => (
            <PlanCard key={plan.id} plan={plan} showEmployee />
          ))}
        </div>
      )}
    </div>
  );
}