"use client";

import { ChevronRight, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { formatDate, formatPeriod } from "@/lib/plans/format";
import { fetchPlanApprovals } from "@/lib/plans/service";
import type { PlanApprovalListResponse, PlanTab } from "@/lib/plans/types";
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
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { ActionBadge, PlanStatusBadge } from "./badges";

/**
 * The approver desk for plans.
 *
 * A plan reaches this queue whenever the caller's name is in the live stage's
 * eligibility snapshot, which is a set: the pending count is the number of
 * plans they could act on today, not the number of plans naming one person.
 */
export function PlanApprovalsList({ headerless = false }: { headerless?: boolean }) {
  const [tab, setTab] = useState<PlanTab>("pending");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<PlanApprovalListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    fetchPlanApprovals(tab, page)
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
  }, [tab, page, reloadKey]);

  function retry() {
    setError("");
    setLoading(true);
    setReloadKey((value) => value + 1);
  }

  return (
    <div className="space-y-6">
      {!headerless && (
        <div>
          <h2 className="text-lg font-semibold tracking-tight text-text-primary">
            Plans awaiting your decision
          </h2>
          <p className="text-sm text-text-secondary">
            A plan is yours to decide on while you are in the snapshot of its
            current step.
          </p>
        </div>
      )}

      <Tabs
        value={tab}
        className="contents"
        onValueChange={(next) => {
          setLoading(true);
          setPage(1);
          setTab(next as PlanTab);
        }}
      >
        <TabsList variant="segmented" aria-label="Plan approvals list">
          <TabsTrigger variant="segmented" value="pending">
            Awaiting my decision
            {data && tab === "pending" && (
              <span className="inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-brand-primary px-1 text-[10px] font-semibold text-white">
                {data.count}
              </span>
            )}
          </TabsTrigger>
          <TabsTrigger variant="segmented" value="decided">
            Decided by me
          </TabsTrigger>
        </TabsList>
      </Tabs>

      {error ? (
        <ErrorState message={error} onRetry={retry} />
      ) : loading ? (
        <div className="space-y-3" aria-busy="true" aria-label="Loading plans">
          {Array.from({ length: 4 }).map((_, index) => (
            <div
              key={index}
              className="h-14 animate-pulse rounded-xl border border-border-default bg-surface-card"
            />
          ))}
        </div>
      ) : !data || data.results.length === 0 ? (
        <Card>
          <EmptyState
            icon={<RefreshCw className="h-8 w-8 text-text-muted" aria-hidden="true" />}
            title={
              tab === "pending"
                ? "No plans are waiting for you"
                : "You have not decided on any plans yet"
            }
            description={
              tab === "pending"
                ? "Plans appear here as soon as the step before yours is done."
                : "Plans you have decided on will appear here."
            }
          />
        </Card>
      ) : (
        <>
          <ApprovalsTable rows={data.results} tab={tab} />
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

function ApprovalsTable({
  rows,
  tab,
}: {
  rows: PlanApprovalListResponse["results"];
  tab: PlanTab;
}) {
  return (
    <>
      <Card className="hidden overflow-hidden md:block">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Employee</TableHead>
              <TableHead>Plan period</TableHead>
              <TableHead>Steps</TableHead>
              <TableHead>Status</TableHead>
              {tab === "decided" && <TableHead>Your decision</TableHead>}
              <TableHead className="w-8 px-2" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.id} className="relative">
                <TableCell className="font-medium text-text-primary">
                  <Link
                    href={`/dashboard/plans/approvals/${row.id}`}
                    className="after:absolute after:inset-0 after:content-['']"
                  >
                    {row.employee_name}
                  </Link>
                  <span className="mt-0.5 block text-xs text-text-muted">
                    {row.team_name || row.department || "—"}
                  </span>
                </TableCell>
                <TableCell className="text-text-secondary">
                  {formatPeriod(row.period_start, row.period_end)}
                </TableCell>
                <TableCell className="text-text-secondary">
                  {row.stage_role_label || "—"}
                  {row.stage_candidate_count > 1 && (
                    <span className="mt-0.5 block text-xs text-text-muted">
                      {row.stage_candidate_count} can act
                    </span>
                  )}
                </TableCell>
                <TableCell>
                  <PlanStatusBadge status={row.status} />
                </TableCell>
                {tab === "decided" && (
                  <TableCell>
                    {row.my_decision ? (
                      <>
                        <ActionBadge action={row.my_decision.action} />
                        <span className="mt-0.5 block text-xs text-text-muted">
                          {row.my_decision.decided_at
                            ? formatDate(row.my_decision.decided_at)
                            : ""}
                        </span>
                      </>
                    ) : (
                      <span className="text-text-muted">—</span>
                    )}
                  </TableCell>
                )}
                <TableCell className="px-2">
                  <ChevronRight className="h-4 w-4 text-text-muted" aria-hidden="true" />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

      <ul className="space-y-3 md:hidden">
        {rows.map((row) => (
          <li key={row.id}>
            <Card interactive>
              <Link
                href={`/dashboard/plans/approvals/${row.id}`}
                className="flex items-center justify-between gap-3"
              >
                <div className="min-w-0">
                  <p className="truncate font-medium text-text-primary">
                    {row.employee_name}
                  </p>
                  <p className="mt-1 text-xs text-text-muted">
                    {formatPeriod(row.period_start, row.period_end)} ·{" "}
                    {row.stage_role_label || "—"}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <PlanStatusBadge status={row.status} />
                  <ChevronRight className="h-4 w-4 text-text-muted" aria-hidden="true" />
                </div>
              </Link>
            </Card>
          </li>
        ))}
      </ul>
    </>
  );
}
