"use client";

import { CalendarRange, ChevronRight } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { formatPeriod } from "@/lib/plans/format";
import { fetchPlans } from "@/lib/plans/service";
import type { PlanListResponse, PlanScope } from "@/lib/plans/types";
import { Card } from "@/components/ui/card";
import { ErrorState, EmptyState } from "@/components/ui/states";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { PlanStatusBadge } from "./badges";

interface ScopeTab {
  value: PlanScope;
  label: string;
}

/**
 * The scopes this switcher offers.
 *
 * `team` and `department` are rendered always: the API answers 403 with an
 * explanation when the caller has no team or no department, and that message
 * is more useful than a hidden tab. `all` is HR-only and lives in the
 * workspace switcher, which is the one that knows the caller's capabilities.
 */
function scopeTabs(isHR: boolean): ScopeTab[] {
  const tabs: ScopeTab[] = [
    { value: "mine", label: "My plans" },
    { value: "team", label: "My team" },
    { value: "department", label: "My department" },
  ];
  if (isHR) tabs.push({ value: "all", label: "All plans" });
  return tabs;
}

export function PlansList({
  initialScope = "mine",
  headerless = false,
  showScopeTabs = true,
}: {
  initialScope?: PlanScope;
  headerless?: boolean;
  /**
   * Set false when the parent already owns a scope switcher. Two stacked
   * scope tab bars that drive the same fetch would fight each other.
   */
  showScopeTabs?: boolean;
}) {
  const tabs = scopeTabs(false);
  const [scope, setScope] = useState<PlanScope>(initialScope);
  const [data, setData] = useState<PlanListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [forbidden, setForbidden] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    fetchPlans(scope)
      .then((result) => {
        if (cancelled) return;
        if (result.ok) {
          setData(result.data);
          setError("");
          setForbidden("");
        } else if (result.kind === "forbidden") {
          setForbidden(result.message);
          setData(null);
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
  }, [scope, reloadKey]);

  function retry() {
    setError("");
    setForbidden("");
    setLoading(true);
    setReloadKey((value) => value + 1);
  }

  return (
    <div className="space-y-6">
      {!headerless && (
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-text-primary">
            Leave day plans
          </h1>
          <p className="text-sm text-text-secondary">
            Blocks of leave you intend to take, and what your team has already
            planned.
          </p>
        </div>
      )}

      {showScopeTabs && (
        <Tabs
          value={scope}
          className="contents"
          onValueChange={(next) => {
            setLoading(true);
            setScope(next as PlanScope);
          }}
        >
          <TabsList variant="segmented" aria-label="Plan scope">
            {tabs.map((tab) => (
              <TabsTrigger key={tab.value} variant="segmented" value={tab.value}>
                {tab.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      )}

      {forbidden ? (
        <ScopeUnavailable message={forbidden} />
      ) : error ? (
        <ErrorState message={error} onRetry={retry} />
      ) : loading ? (
        <SkeletonRows count={5} />
      ) : !data || data.results.length === 0 ? (
        <Card>
          <EmptyState
            title={`No ${scopeLabel(scope).toLowerCase()} plans yet`}
            description={
              scope === "mine"
                ? "Build a plan to see it here."
                : "Plans appear here once they are approved."
            }
          />
        </Card>
      ) : (
        <PlansTable rows={data.results} scope={scope} />
      )}
    </div>
  );
}

function scopeLabel(scope: PlanScope): string {
  switch (scope) {
    case "team":
      return "My team";
    case "department":
      return "My department";
    case "all":
      return "All";
    default:
      return "My";
  }
}

/** A scope the caller is not placed in reads as an empty panel, not an error. */
function ScopeUnavailable({ message }: { message: string }) {
  return (
    <Card className="text-center">
      <CalendarRange className="mx-auto h-8 w-8 text-text-muted" aria-hidden="true" />
      <p className="mt-3 text-sm text-text-secondary">{message}</p>
    </Card>
  );
}

function PlansTable({
  rows,
  scope,
}: {
  rows: PlanListResponse["results"];
  scope: PlanScope;
}) {
  const showEmployee = scope !== "mine";

  return (
    <>
      <Card className="hidden overflow-hidden md:block">
        <Table>
          <TableHeader>
            <TableRow>
              {showEmployee && <TableHead>Employee</TableHead>}
              <TableHead>Period</TableHead>
              <TableHead>Blocks</TableHead>
              <TableHead>Working days</TableHead>
              <TableHead>Financial year</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-8 px-2" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.id} className="relative">
                {showEmployee && (
                  <TableCell className="font-medium text-text-primary">
                    {row.employee_name}
                  </TableCell>
                )}
                <TableCell className="font-medium text-text-primary">
                  <Link
                    href={`/dashboard/plans/${row.id}`}
                    className="after:absolute after:inset-0 after:content-['']"
                  >
                    {formatPeriod(row.period_start, row.period_end)}
                  </Link>
                </TableCell>
                <TableCell className="text-text-secondary">
                  {row.block_count}
                </TableCell>
                <TableCell className="text-text-secondary">
                  {row.working_days}
                </TableCell>
                <TableCell className="text-text-secondary">
                  {row.financial_year_label || "—"}
                </TableCell>
                <TableCell>
                  <PlanStatusBadge status={row.status} />
                </TableCell>
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
                href={`/dashboard/plans/${row.id}`}
                className="flex items-center justify-between gap-3"
              >
                <div className="min-w-0">
                  {showEmployee && (
                    <p className="truncate text-sm text-text-secondary">
                      {row.employee_name}
                    </p>
                  )}
                  <p className="truncate font-medium text-text-primary">
                    {formatPeriod(row.period_start, row.period_end)}
                  </p>
                  <p className="mt-1 text-xs text-text-muted">
                    {row.block_count} {row.block_count === 1 ? "block" : "blocks"} ·{" "}
                    {row.working_days} working days
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

function SkeletonRows({ count }: { count: number }) {
  return (
    <div className="space-y-3" aria-busy="true" aria-live="polite">
      {Array.from({ length: count }).map((_, index) => (
        <div
          key={index}
          className="h-14 animate-pulse rounded-xl border border-border-default bg-surface-card"
        />
      ))}
    </div>
  );
}
