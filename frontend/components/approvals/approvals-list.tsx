"use client";

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
    setTab(next);
    setPage(1);
  }

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
            aria-hidden="true"
          />
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search by reference or employee"
            aria-label="Search approvals"
            className="w-full rounded-lg border border-border-default bg-surface-card py-2 pr-3 pl-9 text-sm text-text-primary placeholder:text-text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary"
          />
        </div>
      </div>

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
    </div>
  );
}

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
      </Link>
    </li>
  );
}

function ListSkeleton() {
  return (
    <div className="space-y-3" aria-hidden="true">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="h-16 animate-pulse rounded-xl bg-surface-muted" />
      ))}
    </div>
  );
}

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