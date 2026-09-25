"use client";

import { ChevronRight, RefreshCw, Search, SlidersHorizontal } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { formatDate, formatDateTime } from "@/lib/approvals/format";
import { fetchApprovals } from "@/lib/approvals/service";
import type {
  ApprovalListResponse,
  ApprovalTab,
} from "@/lib/approvals/types";
import { cn } from "@/lib/utils";

import { ActionBadge, StatusBadge } from "./badges";

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

  return (
    <div className={cn("space-y-6", !headerless && "mx-auto max-w-5xl")}>
      {!headerless && (
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Approvals</h1>
          <p className="text-sm text-text-secondary">
            Applications waiting for your decision.
          </p>
        </div>
      )}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div
          role="tablist"
          aria-label="Approvals list"
          className="inline-flex rounded-lg border border-border-default bg-surface-card p-1"
        >
          <button
            role="tab"
            aria-selected={tab === "pending"}
            onClick={() => switchTab("pending")}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
              tab === "pending"
                ? "bg-brand-primary-subtle text-brand-primary"
                : "text-text-secondary hover:text-text-primary"
            )}
          >
            Pending my decision
            {data && tab === "pending" && (
              <span className="inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-brand-primary px-1 text-[10px] font-semibold text-white">
                {data.count}
              </span>
            )}
          </button>
          <button
            role="tab"
            aria-selected={tab === "decided"}
            onClick={() => switchTab("decided")}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
              tab === "decided"
                ? "bg-brand-primary-subtle text-brand-primary"
                : "text-text-secondary hover:text-text-primary"
            )}
          >
            Decided by me
          </button>
        </div>

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
        <div className="rounded-xl border border-border-default bg-surface-card p-6 text-center shadow-subtle">
          <p className="text-sm text-status-rejected">{error}</p>
          <button
            type="button"
            onClick={retry}
            className="mt-4 inline-flex items-center gap-2 rounded-md bg-button-primary px-4 py-2 text-sm font-medium text-button-primary-foreground hover:bg-button-primary-hover"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Retry
          </button>
        </div>
      ) : loading ? (
        <SkeletonRows count={6} />
      ) : !data || data.results.length === 0 ? (
        <div className="rounded-xl border border-border-default bg-surface-card p-10 text-center shadow-subtle">
          <SlidersHorizontal
            className="mx-auto h-8 w-8 text-text-muted"
            aria-hidden="true"
          />
          <p className="mt-3 text-sm font-medium text-text-primary">
            {tab === "pending"
              ? (q ? "No applications match your search." : "No applications are waiting for your decision.")
              : (q ? "No applications match your search." : "You have not decided on any applications yet.")}
          </p>
          <p className="mt-1 text-sm text-text-secondary">
            {tab === "pending"
              ? "New applications will appear here as they are submitted."
              : "Applications you have decided on will appear here."}
          </p>
        </div>
      ) : (
        <>
          <Table rows={data.results} tab={tab} />
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

function Table({
  rows,
  tab,
}: {
  rows: ApprovalListResponse["results"];
  tab: ApprovalTab;
}) {
  return (
    <>
      <div className="hidden overflow-hidden rounded-xl border border-border-default bg-surface-card shadow-subtle md:block">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-border-default text-xs uppercase tracking-wide text-text-muted">
              <th className="px-4 py-3 font-medium">Reference</th>
              <th className="px-4 py-3 font-medium">Employee</th>
              <th className="px-4 py-3 font-medium">Leave type</th>
              <th className="px-4 py-3 font-medium">Dates</th>
              <th className="px-4 py-3 font-medium">Days</th>
              <th className="px-4 py-3 font-medium">Submitted</th>
              {tab === "decided" && (
                <th className="px-4 py-3 font-medium">Your decision</th>
              )}
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="w-8 px-2 py-3" />
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <TableRow key={row.id} row={row} tab={tab} desktop />
            ))}
          </tbody>
        </table>
      </div>

      <ul className="space-y-3 md:hidden">
        {rows.map((row) => (
          <TableRow key={row.id} row={row} tab={tab} />
        ))}
      </ul>
    </>
  );
}

function TableRow({
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
      <tr className="relative border-b border-border-default last:border-b-0 transition-colors hover:bg-surface-hover">
        <td className="px-4 py-3 font-medium text-text-primary">
          <Link
            href={`/dashboard/approvals/${row.id}`}
            className="after:absolute after:inset-0 after:content-['']"
          >
            {row.reference}
          </Link>
        </td>
        <td className="px-4 py-3">
          <span className="font-medium text-text-primary">{row.employee_name}</span>
          <span className="mt-0.5 block text-xs text-text-muted">
            {row.department || "—"}
          </span>
        </td>
        <td className="px-4 py-3 text-text-secondary">
          {row.leave_type.name || "—"}
        </td>
        <td className="px-4 py-3 text-text-secondary">
          {formatDate(row.start_date) || "—"} → {formatDate(row.end_date) || "—"}
        </td>
        <td className="px-4 py-3 text-text-secondary">{row.working_days}</td>
        <td className="px-4 py-3 text-text-secondary">
          {formatDateTime(row.submitted_at) || "—"}
        </td>
        {tab === "decided" && (
          <td className="px-4 py-3">
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
          </td>
        )}
        <td className="px-4 py-3">
          <StatusBadge status={row.status} />
        </td>
        <td className="px-2 py-3">
          <ChevronRight className="h-4 w-4 text-text-muted" aria-hidden="true" />
        </td>
      </tr>
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

function Pagination({
  page,
  hasPrevious,
  hasNext,
  onPrevious,
  onNext,
}: {
  page: number;
  hasPrevious: boolean;
  hasNext: boolean;
  onPrevious: () => void;
  onNext: () => void;
}) {
  return (
    <nav aria-label="Pagination" className="flex items-center justify-between">
      <button
        type="button"
        disabled={!hasPrevious}
        onClick={onPrevious}
        className="rounded-md border border-input-border bg-input-background px-3 py-1.5 text-sm font-medium text-text-primary hover:bg-surface-hover disabled:cursor-not-allowed disabled:opacity-40"
      >
        Previous
      </button>
      <span className="text-sm text-text-muted">Page {page}</span>
      <button
        type="button"
        disabled={!hasNext}
        onClick={onNext}
        className="rounded-md border border-input-border bg-input-background px-3 py-1.5 text-sm font-medium text-text-primary hover:bg-surface-hover disabled:cursor-not-allowed disabled:opacity-40"
      >
        Next
      </button>
    </nav>
  );
}