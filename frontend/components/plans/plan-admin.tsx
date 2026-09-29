"use client";

import { Loader2, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { formatDate } from "@/lib/plans/format";
import { BLOCK_STATUS_META, PLAN_STATUS_META } from "@/lib/plans/labels";
import { fetchAdminPlans } from "@/lib/plans/service";
import type { BlockStatus, PlanRow, PlanStatus } from "@/lib/plans/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/states";
import { PlanStatusBadge } from "./plan-status-badge";

const PLAN_STATUSES = Object.keys(PLAN_STATUS_META) as PlanStatus[];
const BLOCK_STATUSES = Object.keys(BLOCK_STATUS_META) as BlockStatus[];

export function PlanAdminView() {
  const [status, setStatus] = useState<PlanStatus | "">("");
  const [blockStatus, setBlockStatus] = useState<BlockStatus | "">("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<{
    results: PlanRow[];
    count: number;
    next: string | null;
    previous: string | null;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    fetchAdminPlans({
      status: status || undefined,
      blockStatus: blockStatus || undefined,
      page,
    })
      .then((result) => {
        if (cancelled) return;
        if (result.ok) {
          setData(result.data);
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
  }, [status, blockStatus, page, reloadKey]);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold tracking-tight text-text-primary">All plans</h2>
        <p className="text-text-secondary">
          Every leave day plan across the organisation.
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <div>
          <label
            htmlFor="plan-status-filter"
            className="mb-1 block text-xs font-medium text-text-secondary"
          >
            Plan status
          </label>
          <select
            id="plan-status-filter"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value as PlanStatus | "");
              setPage(1);
            }}
            className="rounded-md border border-input-border bg-input-background px-3 py-2 text-sm text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
          >
            <option value="">All statuses</option>
            {PLAN_STATUSES.map((value) => (
              <option key={value} value={value}>
                {PLAN_STATUS_META[value].label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label
            htmlFor="block-status-filter"
            className="mb-1 block text-xs font-medium text-text-secondary"
          >
            Block status
          </label>
          <select
            id="block-status-filter"
            value={blockStatus}
            onChange={(e) => {
              setBlockStatus(e.target.value as BlockStatus | "");
              setPage(1);
            }}
            className="rounded-md border border-input-border bg-input-background px-3 py-2 text-sm text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
          >
            <option value="">Any block</option>
            {BLOCK_STATUSES.map((value) => (
              <option key={value} value={value}>
                {BLOCK_STATUS_META[value].label}
              </option>
            ))}
          </select>
        </div>
        <button
          type="button"
          onClick={() => setReloadKey((n) => n + 1)}
          className="rounded-md p-2 text-text-muted transition-colors hover:bg-surface-hover hover:text-text-primary"
          aria-label="Refresh"
        >
          <RefreshCw className="size-4" />
        </button>
      </div>

      <div className="overflow-hidden rounded-xl border border-border-default bg-surface-card shadow-subtle">
        {loading ? (
          <div className="flex justify-center py-10">
            <Loader2 className="size-5 animate-spin text-text-muted" />
          </div>
        ) : error ? (
          <p className="px-5 py-4 text-status-rejected">{error}</p>
        ) : !data || data.results.length === 0 ? (
          <EmptyState
            title="No plans match"
            description="Adjust the filters, or wait for employees to create their plans."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border-default text-xs text-text-muted">
                  <th className="px-4 py-3 font-medium">Employee</th>
                  <th className="px-4 py-3 font-medium">Period</th>
                  <th className="px-4 py-3 font-medium">Financial year</th>
                  <th className="px-4 py-3 font-medium">Days</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-default">
                {data.results.map((plan) => (
                  <tr
                    key={plan.id}
                    className="transition-colors hover:bg-surface-hover"
                  >
                    <td className="px-4 py-3">
                      <Link
                        href={`/dashboard/plans/${plan.id}`}
                        className="font-medium text-brand-primary hover:text-brand-primary-hover"
                      >
                        {plan.employee_name}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-text-secondary">
                      {formatDate(plan.period_start)} → {formatDate(plan.period_end)}
                    </td>
                    <td className="px-4 py-3 text-text-secondary">
                      {plan.financial_year_label || "—"}
                    </td>
                    <td className="px-4 py-3 text-text-secondary">
                      {plan.working_days}
                    </td>
                    <td className="px-4 py-3">
                      <PlanStatusBadge status={plan.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data && data.results.length > 0 && (
          <div className="flex items-center justify-between gap-3 border-t border-border-default px-4 py-3">
            <p className="text-xs text-text-muted">
              {data.count} {data.count === 1 ? "plan" : "plans"}
            </p>
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                disabled={page <= 1 || !data.previous}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                Previous
              </Button>
              <Button
                variant="secondary"
                size="sm"
                disabled={!data.next}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </div>

      <p className={cn("text-sm text-text-secondary")}>
        In draft or submitted — the chain has yet to act. Approved plans with a
        reserved block within the confirmation window need confirmation before
        the window closes.
      </p>
    </div>
  );
}