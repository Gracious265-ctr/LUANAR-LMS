"use client";

import { ChevronRight } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { formatPeriod, formatWorkingDays } from "@/lib/plans/format";
import { BLOCK_STATUS_META, PLAN_STATUS_META } from "@/lib/plans/labels";
import { fetchAdminPlans } from "@/lib/plans/service";
import type {
  AdminListResponse,
  BlockStatus,
  PlanStatus,
} from "@/lib/plans/types";
import { Card } from "@/components/ui/card";
import { ErrorState, EmptyState } from "@/components/ui/states";
import { Pagination } from "@/components/ui/pagination";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Field } from "@/components/ui/input";

import { BlockStatusBadge, PlanStatusBadge } from "./badges";

const ANY = "any";

/** Every block status, so the filter cannot drift from the label map. */
const BLOCK_STATUSES = Object.keys(BLOCK_STATUS_META) as BlockStatus[];

/**
 * HR's read-only sweep of every plan.
 *
 * Both filters are optional and independent: status narrows the plan, block
 * status narrows the blocks inside a plan of any status, which is how an HR
 * officer finds reserved blocks nobody confirmed.
 */
export function PlansAdminTable() {
  const [status, setStatus] = useState<PlanStatus | typeof ANY>(ANY);
  const [blockStatus, setBlockStatus] = useState<BlockStatus | typeof ANY>(ANY);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<AdminListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    fetchAdminPlans({
      status: status === ANY ? undefined : status,
      blockStatus: blockStatus === ANY ? undefined : blockStatus,
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
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [status, blockStatus, page, reloadKey]);

  function retry() {
    setError("");
    setLoading(true);
    setReloadKey((value) => value + 1);
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <Field label="Plan status" htmlFor="plan-status-filter" className="w-48">
          <Select
            value={status}
            onValueChange={(next) => {
              setPage(1);
              setStatus(next as PlanStatus | typeof ANY);
            }}
          >
            <SelectTrigger id="plan-status-filter">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ANY}>Any status</SelectItem>
              {(Object.keys(PLAN_STATUS_META) as PlanStatus[]).map((key) => (
                <SelectItem key={key} value={key}>
                  {PLAN_STATUS_META[key].label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
        <Field label="Block status" htmlFor="block-status-filter" className="w-48">
          <Select
            value={blockStatus}
            onValueChange={(next) => {
              setPage(1);
              setBlockStatus(next as BlockStatus | typeof ANY);
            }}
          >
            <SelectTrigger id="block-status-filter">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ANY}>Any block status</SelectItem>
              {BLOCK_STATUSES.map((key) => (
                <SelectItem key={key} value={key}>
                  {BLOCK_STATUS_META[key].label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
      </div>

      {error ? (
        <ErrorState message={error} onRetry={retry} />
      ) : loading ? (
        <div
          className="h-40 animate-pulse rounded-xl border border-border-default bg-surface-card"
          aria-busy="true"
          aria-label="Loading plans"
        />
      ) : !data || data.results.length === 0 ? (
        <Card>
          <EmptyState
            title="No plans match these filters"
            description="Widen the filters to see more plans."
          />
        </Card>
      ) : (
        <>
          <Card className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Employee</TableHead>
                  <TableHead>Period</TableHead>
                  <TableHead>Blocks</TableHead>
                  <TableHead>Working days</TableHead>
                  <TableHead>Plan status</TableHead>
                  <TableHead>Block statuses</TableHead>
                  <TableHead className="w-8 px-2" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.results.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell>
                      <Link
                        href={`/dashboard/plans/${row.id}`}
                        className="font-medium text-text-primary hover:underline"
                      >
                        {row.employee_name}
                      </Link>
                    </TableCell>
                    <TableCell className="text-text-secondary">
                      {formatPeriod(row.period_start, row.period_end)}
                    </TableCell>
                    <TableCell className="text-text-secondary">
                      {row.block_count}
                    </TableCell>
                    <TableCell className="text-text-secondary">
                      {formatWorkingDays(row.working_days)}
                    </TableCell>
                    <TableCell>
                      <PlanStatusBadge status={row.status} />
                    </TableCell>
                    <TableCell>
                      <span className="flex flex-wrap gap-1">
                        {row.blocks.map((block) => (
                          <BlockStatusBadge key={block.id} status={block.status} />
                        ))}
                      </span>
                    </TableCell>
                    <TableCell className="px-2">
                      <Link
                        href={`/dashboard/plans/${row.id}`}
                        aria-label={`Open plan for ${row.employee_name}`}
                      >
                        <ChevronRight
                          className="h-4 w-4 text-text-muted"
                          aria-hidden="true"
                        />
                      </Link>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Card>
          <Pagination
            page={page}
            hasPrevious={Boolean(data.previous) || page > 1}
            hasNext={Boolean(data.next)}
            onPrevious={() => setPage((current) => Math.max(1, current - 1))}
            onNext={() => setPage((current) => current + 1)}
          />
        </>
      )}
    </div>
  );
}
