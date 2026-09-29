"use client";

import { Loader2, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { formatDate } from "@/lib/plans/format";
import { BLOCK_STATUS_META, PLAN_STATUS_META } from "@/lib/plans/labels";
import { fetchAdminPlans } from "@/lib/plans/service";
import type { BlockStatus, PlanRow, PlanStatus } from "@/lib/plans/types";
import { cn } from "@/lib/utils";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/states";
import { PlanStatusBadge } from "./plan-status-badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card } from "@/components/ui/card";

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
          <Select
            value={status}
            onValueChange={(next) => {
              setStatus(next as PlanStatus | "");
              setPage(1);
            }}
          >
            <SelectTrigger id="plan-status-filter" aria-label="Plan status">
              <SelectValue placeholder="All statuses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">All statuses</SelectItem>
              {PLAN_STATUSES.map((value) => (
                <SelectItem key={value} value={value}>
                  {PLAN_STATUS_META[value].label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <label
            htmlFor="block-status-filter"
            className="mb-1 block text-xs font-medium text-text-secondary"
          >
            Block status
          </label>
          <Select
            value={blockStatus}
            onValueChange={(next) => {
              setBlockStatus(next as BlockStatus | "");
              setPage(1);
            }}
          >
            <SelectTrigger id="block-status-filter" aria-label="Block status">
              <SelectValue placeholder="Any block" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">Any block</SelectItem>
              {BLOCK_STATUSES.map((value) => (
                <SelectItem key={value} value={value}>
                  {BLOCK_STATUS_META[value].label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Button
          type="button"
          onClick={() => setReloadKey((n) => n + 1)}
          aria-label="Refresh"
          variant="ghost"
          size="icon"
          className="h-auto w-auto p-2"
        >
          <RefreshCw className="size-4" />
        </Button>
      </div>

      <Card className="overflow-hidden">
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
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Employee</TableHead>
                <TableHead>Period</TableHead>
                <TableHead>Financial year</TableHead>
                <TableHead>Days</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.results.map((plan) => (
                <TableRow
                  key={plan.id}
                >
                  <TableCell>
                    <Link
                      href={`/dashboard/plans/${plan.id}`}
                      className="font-medium text-brand-primary hover:text-brand-primary-hover"
                    >
                      {plan.employee_name}
                    </Link>
                  </TableCell>
                  <TableCell className="text-text-secondary">
                    {formatDate(plan.period_start)} → {formatDate(plan.period_end)}
                  </TableCell>
                  <TableCell className="text-text-secondary">
                    {plan.financial_year_label || "—"}
                  </TableCell>
                  <TableCell className="text-text-secondary">
                    {plan.working_days}
                  </TableCell>
                  <TableCell>
                    <PlanStatusBadge status={plan.status} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
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
      </Card>

      <p className={cn("text-sm text-text-secondary")}>
        In draft or submitted — the chain has yet to act. Approved plans with a
        reserved block within the confirmation window need confirmation before
        the window closes.
      </p>
    </div>
  );
}