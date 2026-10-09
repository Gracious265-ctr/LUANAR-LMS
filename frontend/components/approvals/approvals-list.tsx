"use client";

import { CheckCircle2, ChevronRight, Inbox, RefreshCw, Search, SearchX } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { formatDate, formatDateTime } from "@/lib/approvals/format";
import { fetchApprovals } from "@/lib/approvals/service";
import type {
  ApprovalListResponse,
  ApprovalTab,
} from "@/lib/approvals/types";
import { cn } from "@/lib/utils";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Pagination } from "@/components/ui/pagination";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/states";
import { Avatar } from "@/components/ui/Avatar";

import { ActionBadge, StatusBadge } from "./badges";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card } from "@/components/ui/card";

function useDebounced(value: string, delay = 300): string {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

export function ApprovalsList({ headerless = false }: { headerless?: boolean }) {
  const [tab, setTab] = useState<ApprovalTab>("pending");
  const [qInput, setQInput] = useState("");
  const q = useDebounced(qInput);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<ApprovalListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    fetchApprovals(tab, q, page)
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
        if (!cancelled) setError("Failed to load approvals.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [tab, q, page, reloadKey]);

  function switchTab(next: ApprovalTab) {
    if (next === tab) return;
    setTab(next);
    setPage(1);
  }

  function retry() {
    setError("");
    setLoading(true);
    setReloadKey((value) => value + 1);
  }

  function onSearchChange(value: string) {
    setQInput(value);
    setPage(1);
  }

  /** The "Clear filters" action on the no-results empty state. */
  function clearSearch() {
    setQInput("");
    setPage(1);
  }

  return (
    <div className={cn("space-y-6", !headerless && "mx-auto max-w-5xl")}>
      {!headerless && (
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-text-primary">Approvals</h1>
          <p className="text-sm text-text-secondary">
            Applications waiting for your decision.
          </p>
        </div>
      )}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Tabs
          value={tab}
          className="contents"
          onValueChange={(next) => switchTab(next as ApprovalTab)}
        >
          <TabsList variant="segmented" aria-label="Approvals list">
            <TabsTrigger variant="segmented" value="pending">
              Pending my decision
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

        <div className="relative w-full sm:w-72">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted"
            aria-hidden="true"
          />
          <input
            type="search"
            value={qInput}
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder="Reference or employee name…"
            aria-label="Search approvals"
            className="w-full rounded-md border border-input-border bg-input-background py-2 pl-9 pr-3 text-sm text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
          />
        </div>
      </div>

      {error ? (
        <Card className="text-center">
          <p className="text-sm text-status-rejected">{error}</p>
          <Button type="button" onClick={retry} variant="primary" className="mt-4">
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Retry
          </Button>
        </Card>
      ) : loading ? (
        <SkeletonRows count={6} />
      ) : !data || data.results.length === 0 ? (
        <Card>
          {q ? (
            <EmptyState
              icon={<SearchX className="h-10 w-10" />}
              title={`No results for "${q}"`}
              description="Check the reference number or employee name and try again."
              action={
                <Button type="button" variant="secondary" onClick={clearSearch}>
                  Clear filters
                </Button>
              }
            />
          ) : tab === "pending" ? (
            <EmptyState
              icon={<CheckCircle2 className="h-10 w-10" />}
              title="Nothing pending your review"
              description="New applications will appear here as they are submitted."
            />
          ) : (
            <EmptyState
              icon={<Inbox className="h-10 w-10" />}
              title="You have not decided on any applications yet"
              description="Applications you have decided on will appear here."
            />
          )}
        </Card>
      ) : (
        <>
          <ApprovalTable rows={data.results} tab={tab} />
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

function ApprovalTable({
  rows,
  tab,
}: {
  rows: ApprovalListResponse["results"];
  tab: ApprovalTab;
}) {
  return (
    <>
      <Card className="hidden overflow-hidden md:block">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Reference</TableHead>
              <TableHead>Employee</TableHead>
              <TableHead>Leave type</TableHead>
              <TableHead>Dates</TableHead>
              <TableHead>Days</TableHead>
              <TableHead>Submitted</TableHead>
              {tab === "decided" && <TableHead>Your decision</TableHead>}
              <TableHead>Status</TableHead>
              <TableHead className="w-8 px-2" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <ApprovalTableRow key={row.id} row={row} tab={tab} desktop />
            ))}
          </TableBody>
        </Table>
      </Card>

      <ul className="space-y-3 md:hidden">
        {rows.map((row) => (
          <ApprovalTableRow key={row.id} row={row} tab={tab} />
        ))}
      </ul>
    </>
  );
}

function ApprovalTableRow({
  row,
  tab,
  desktop,
}: {
  row: ApprovalListResponse["results"][number];
  tab: ApprovalTab;
  desktop?: boolean;
}) {
  const decision = row.my_decision;

  if (desktop) {
    return (
      <TableRow className="relative">
        <TableCell className="font-medium text-text-primary">
          <Link
            href={`/dashboard/approvals/${row.id}`}
            className="after:absolute after:inset-0 after:content-['']"
          >
            {row.reference}
          </Link>
        </TableCell>
        <TableCell>
          <div className="flex items-center gap-2">
            <Avatar
              name={row.employee_name}
              userId={row.employee_name}
              size="sm"
            />
            <div className="min-w-0">
              <span className="font-medium text-text-primary">
                {row.employee_name}
              </span>
              <span className="mt-0.5 block text-xs text-text-muted">
                {row.team || "—"}
              </span>
            </div>
          </div>
        </TableCell>
        <TableCell className="text-text-secondary">
          {row.leave_type.name || "—"}
        </TableCell>
        <TableCell className="text-text-secondary">
          {formatDate(row.start_date) || "—"} → {formatDate(row.end_date) || "—"}
        </TableCell>
        <TableCell className="text-text-secondary">{row.working_days}</TableCell>
        <TableCell className="text-text-secondary">
          {formatDateTime(row.submitted_at) || "—"}
        </TableCell>
        {tab === "decided" && (
          <TableCell>
            {decision ? (
              <>
                <ActionBadge action={decision.action} />
                <span className="mt-0.5 block text-xs text-text-muted">
                  {decision.decided_at ? formatDateTime(decision.decided_at) : ""}
                </span>
              </>
            ) : (
              <span className="text-text-muted">—</span>
            )}
          </TableCell>
        )}
        <TableCell>
          <StatusBadge status={row.status} />
        </TableCell>
        <TableCell className="px-2">
          <ChevronRight className="h-4 w-4 text-text-muted" aria-hidden="true" />
        </TableCell>
      </TableRow>
    );
  }

  return (
    <li className="rounded-xl border border-border-default bg-surface-card p-4 shadow-subtle">
      <Link
        href={`/dashboard/approvals/${row.id}`}
        className="flex items-center justify-between gap-3"
      >
        <div className="min-w-0">
          <p className="truncate font-medium text-text-primary">{row.reference}</p>
          <p className="truncate text-sm text-text-secondary">{row.employee_name}</p>
          <p className="mt-1 text-xs text-text-muted">
            {row.leave_type.name || "—"} · {formatDate(row.start_date) || "—"} →{" "}
            {formatDate(row.end_date) || "—"}
          </p>
          {tab === "decided" && decision && (
            <p className="mt-1">
              <ActionBadge action={decision.action} />
            </p>
          )}
        </div>
        <div className="flex shrink-0 flex-col items-end gap-2">
          <StatusBadge status={row.status} />
          <ChevronRight className="h-4 w-4 text-text-muted" aria-hidden="true" />
        </div>
      </Link>
    </li>
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
