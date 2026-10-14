"use client";

<<<<<<< HEAD
import { useEffect, useState } from "react";

import Link from "next/link";
import {
  ArrowLeft,
  ArrowRight,
  ClipboardList,
  RefreshCw,
  Search,
  TriangleAlert,
} from "lucide-react";

import { cn } from "@/lib/utils";

import {
  formatDateRange,
  formatDateTime,
} from "@/lib/approvals/format";
import { useApprovalsList } from "@/lib/approvals/hooks";
import type { ApprovalListItem } from "@/lib/approvals/types";

import { StatusBadge } from "../tracking/StatusBadge";
import { Tabs } from "../ui/tabs";
import { ActionBadge } from "./primitives";

const PAGE_SIZE = 20;

export function ApprovalsList() {
  const [tab, setTab] = useState<"pending" | "decided">("pending");
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [page, setPage] = useState(1);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(query.trim());
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  function changeTab(next: "pending" | "decided") {
=======
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
>>>>>>> feature/plans-teams
    setTab(next);
    setPage(1);
  }

<<<<<<< HEAD
  const { state, refetch } = useApprovalsList({
    tab,
    q: debouncedQuery,
    page,
    pageSize: PAGE_SIZE,
  });

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-text-primary">Approvals</h1>
        <p className="text-sm text-text-secondary">
          Applications waiting for your decision.
        </p>
      </header>

      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <Tabs
          label="Approval queue tabs"
          tabs={[
            { value: "pending", label: "Pending" },
            { value: "decided", label: "Decided" },
          ]}
          value={tab}
          onChange={changeTab}
        />
        <div className="relative sm:w-72">
          <Search
            className="pointer-events-none absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-text-muted"
=======
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
>>>>>>> feature/plans-teams
            aria-hidden="true"
          />
          <input
            type="search"
<<<<<<< HEAD
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search by reference or employee"
            aria-label="Search approvals"
            className="w-full rounded-lg border border-border-default bg-surface-card py-2 pr-3 pl-9 text-sm text-text-primary placeholder:text-text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary"
=======
            value={qInput}
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder="Reference or employee name…"
            aria-label="Search approvals"
            className="w-full rounded-md border border-input-border bg-input-background py-2 pl-9 pr-3 text-sm text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
>>>>>>> feature/plans-teams
          />
        </div>
      </div>

<<<<<<< HEAD
      <div aria-busy={state.status === "loading"}>
        {state.status === "loading" && <ListSkeleton />}

        {state.status === "error" && (
          <ErrorState message={state.message} onRetry={refetch} />
        )}

        {state.status === "ok" && state.data.results.length === 0 && (
          <EmptyState
            searching={Boolean(debouncedQuery)}
            tab={tab}
            onClear={() => {
              setQuery("");
              setDebouncedQuery("");
            }}
          />
        )}

        {state.status === "ok" && state.data.results.length > 0 && (
          <>
            <div className="overflow-hidden rounded-xl border border-border-default bg-surface-card shadow-subtle">
              <table className="hidden w-full text-left text-sm md:table">
                <thead>
                  <tr className="border-b border-border-default text-xs tracking-wide text-text-secondary uppercase">
                    <th scope="col" className="px-4 py-3 font-medium">
                      Reference
                    </th>
                    <th scope="col" className="px-4 py-3 font-medium">
                      Employee
                    </th>
                    <th scope="col" className="px-4 py-3 font-medium">
                      Department
                    </th>
                    <th scope="col" className="px-4 py-3 font-medium">
                      Leave period
                    </th>
                    <th scope="col" className="px-4 py-3 font-medium">
                      Days
                    </th>
                    <th scope="col" className="px-4 py-3 font-medium">
                      Submitted
                    </th>
                    <th scope="col" className="px-4 py-3 font-medium">
                      Status
                    </th>
                    {tab === "decided" && (
                      <th scope="col" className="px-4 py-3 font-medium">
                        Your decision
                      </th>
                    )}
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-default">
                  {state.data.results.map((item) => (
                    <ListRow key={item.id} item={item} tab={tab} />
                  ))}
                </tbody>
              </table>

              <ul className="divide-y divide-border-default md:hidden">
                {state.data.results.map((item) => (
                  <MobileRow key={item.id} item={item} tab={tab} />
                ))}
              </ul>
            </div>

            <div className="flex flex-col items-center justify-between gap-3 sm:flex-row">
              <p className="text-sm text-text-muted">
                Showing {firstIndex(page, state.data.count)}–
                {lastIndex(page, state.data.count)} of {state.data.count}
              </p>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={!state.data.previous}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-border-default px-3 py-2 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <ArrowLeft className="h-4 w-4" aria-hidden="true" />
                  Previous
                </button>
                <button
                  type="button"
                  onClick={() => setPage((p) => p + 1)}
                  disabled={!state.data.next}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-border-default px-3 py-2 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Next
                  <ArrowRight className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>
            </div>
          </>
        )}
      </div>
=======
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
>>>>>>> feature/plans-teams
    </div>
  );
}

<<<<<<< HEAD
function firstIndex(page: number, count: number): number {
  if (count === 0) return 0;
  return (page - 1) * PAGE_SIZE + 1;
}

function lastIndex(page: number, count: number): number {
  return Math.min(page * PAGE_SIZE, count);
}

function ListRow({
  item,
  tab,
}: {
  item: ApprovalListItem;
  tab: "pending" | "decided";
}) {
  return (
    <tr className="transition-colors hover:bg-surface-hover">
      <td className="px-4 py-3 font-medium">
        <Link
          href={`/approvals/${item.id}`}
          className="text-brand-primary transition-colors hover:text-brand-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary rounded"
        >
          {item.reference}
        </Link>
      </td>
      <td className="px-4 py-3 text-text-primary">{item.employee_name}</td>
      <td className="px-4 py-3 text-text-secondary">{item.department}</td>
      <td className="px-4 py-3 text-text-secondary">
        {formatDateRange(item.start_date, item.end_date)}
      </td>
      <td className="px-4 py-3 text-text-secondary">{item.working_days}</td>
      <td className="px-4 py-3 text-text-secondary">
        {formatDateTime(item.submitted_at)}
      </td>
      <td className="px-4 py-3">
        <StatusBadge status={item.status} />
      </td>
      {tab === "decided" && (
        <td className="px-4 py-3">
          {item.my_decision ? (
            <div className="flex flex-col items-start gap-1">
              <ActionBadge action={item.my_decision.action} />
              <time dateTime={item.my_decision.decided_at} className="text-xs text-text-muted">
                {formatDateTime(item.my_decision.decided_at)}
              </time>
            </div>
          ) : (
            <span className="text-sm text-text-muted">—</span>
          )}
        </td>
      )}
    </tr>
  );
}

function MobileRow({
  item,
  tab,
}: {
  item: ApprovalListItem;
  tab: "pending" | "decided";
}) {
  return (
    <li>
      <Link
        href={`/approvals/${item.id}`}
        className="block px-4 py-4 transition-colors hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary"
      >
        <div className="flex items-center justify-between gap-3">
          <span className="font-medium text-text-primary">{item.reference}</span>
          <StatusBadge status={item.status} />
        </div>
        <p className="mt-1 truncate text-sm text-text-secondary">
          {item.employee_name}
        </p>
        <p className="mt-0.5 text-xs text-text-muted">
          {item.leave_type} · {formatDateRange(item.start_date, item.end_date)} ·{" "}
          {item.working_days} days
        </p>
        {tab === "decided" && item.my_decision && (
          <div className="mt-2 flex items-center gap-2">
            <ActionBadge action={item.my_decision.action} />
            <span className="text-xs text-text-muted">
              {formatDateTime(item.my_decision.decided_at)}
            </span>
          </div>
        )}
=======
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
>>>>>>> feature/plans-teams
      </Link>
    </li>
  );
}

<<<<<<< HEAD
function ListSkeleton() {
  return (
    <div className="space-y-3" aria-hidden="true">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="h-16 animate-pulse rounded-xl bg-surface-muted" />
=======
function SkeletonRows({ count }: { count: number }) {
  return (
    <div className="space-y-3" aria-busy="true" aria-live="polite">
      {Array.from({ length: count }).map((_, index) => (
        <div
          key={index}
          className="h-14 animate-pulse rounded-xl border border-border-default bg-surface-card"
        />
>>>>>>> feature/plans-teams
      ))}
    </div>
  );
}
<<<<<<< HEAD

function EmptyState({
  searching,
  tab,
  onClear,
}: {
  searching: boolean;
  tab: "pending" | "decided";
  onClear: () => void;
}) {
  return (
    <div className="rounded-xl border border-border-default bg-surface-card p-10 text-center shadow-subtle">
      <ClipboardList
        className="mx-auto h-10 w-10 text-text-muted"
        aria-hidden="true"
      />
      <h2 className="mt-4 text-base font-semibold text-text-primary">
        {searching
          ? "No results found"
          : tab === "pending"
            ? "Nothing waiting for you right now"
            : "No decisions yet"}
      </h2>
      <p className="mx-auto mt-1 max-w-sm text-sm text-text-secondary">
        {searching
          ? "Try adjusting your search or switching tabs."
          : tab === "pending"
            ? "Applications that need your approval will appear here."
            : "Your decisions will appear here."}
      </p>
      {searching && (
        <button
          type="button"
          onClick={onClear}
          className="mt-5 inline-flex items-center gap-1.5 rounded-lg border border-border-default px-4 py-2 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary"
        >
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          Clear search
        </button>
      )}
    </div>
  );
}

function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div className="rounded-xl border border-border-default bg-surface-card p-10 text-center shadow-subtle">
      <TriangleAlert
        className="mx-auto h-10 w-10 text-status-rejected"
        aria-hidden="true"
      />
      <h2 className="mt-4 text-base font-semibold text-text-primary">
        Could not load approvals
      </h2>
      <p className="mx-auto mt-1 max-w-sm text-sm text-text-secondary">
        {message}
      </p>
      <button
        type="button"
        onClick={onRetry}
        className={cn(
          "mt-5 inline-flex items-center gap-1.5 rounded-lg bg-brand-primary px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-brand-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
        )}
      >
        <RefreshCw className="h-4 w-4" aria-hidden="true" />
        Try again
      </button>
    </div>
  );
}
=======
>>>>>>> feature/plans-teams
