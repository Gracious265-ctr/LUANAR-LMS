"use client";

import { ChevronRight, RefreshCw, SlidersHorizontal } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { formatDate, formatDateTime } from "@/lib/cancellations/format";
import { fetchCancellations } from "@/lib/cancellations/service";
import type {
  CancellationListResponse,
  CancellationRow,
  CancellationTab,
} from "@/lib/cancellations/types";
import { cn } from "@/lib/utils";

/**
 * Approver queue of cancellation requests (Unit 18, spec 2.3). Two-inner tabs
 * (Pending / Decided by me), oldest request first, pagination following the
 * Unit 16 convention.
 */
export function CancellationRequestsTable() {
  const [tab, setTab] = useState<CancellationTab>("pending");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<CancellationListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    fetchCancellations(tab, page)
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
        if (!cancelled) setError("Failed to load cancellation requests.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [tab, page, reloadKey]);

  function switchTab(next: CancellationTab) {
    if (next === tab) return;
    setTab(next);
    setPage(1);
  }

  function retry() {
    setError("");
    setLoading(true);
    setReloadKey((value) => value + 1);
  }

  if (error) {
    return (
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
    );
  }

  return (
    <div className="space-y-4">
      <div
        role="tablist"
        aria-label="Cancellation requests"
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
          Pending
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

      {loading ? (
        <SkeletonRows count={4} />
      ) : !data || data.results.length === 0 ? (
        <div className="rounded-xl border border-border-default bg-surface-card p-10 text-center shadow-subtle">
          <SlidersHorizontal
            className="mx-auto h-8 w-8 text-text-muted"
            aria-hidden="true"
          />
          <p className="mt-3 text-sm font-medium text-text-primary">
            {tab === "pending"
              ? "No cancellation requests are waiting for you."
              : "You haven't decided any cancellation requests yet."}
          </p>
          <p className="mt-1 text-sm text-text-secondary">
            {tab === "pending"
              ? "Requests will appear here when an employee asks to cancel approved leave."
              : "Requests you have decided on will appear here."}
          </p>
        </div>
      ) : (
        <>
          <Table rows={data.results} />
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

function Table({ rows }: { rows: CancellationRow[] }) {
  return (
    <>
      <div className="hidden overflow-hidden rounded-xl border border-border-default bg-surface-card shadow-subtle lg:block">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-border-default text-xs uppercase tracking-wide text-text-muted">
              <th className="px-4 py-3 font-medium">Reference</th>
              <th className="px-4 py-3 font-medium">Employee</th>
              <th className="px-4 py-3 font-medium">Leave type</th>
              <th className="px-4 py-3 font-medium">Leave dates</th>
              <th className="px-4 py-3 font-medium">Days</th>
              <th className="px-4 py-3 font-medium">Requested on</th>
              <th className="px-4 py-3 font-medium">Current stage</th>
              <th className="px-4 py-3 font-medium">Starts</th>
              <th className="w-8 px-2 py-3" />
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <TableRow key={row.request_id} row={row} desktop />
            ))}
          </tbody>
        </table>
      </div>

      <ul className="space-y-3 lg:hidden">
        {rows.map((row) => (
          <TableRow key={row.request_id} row={row} />
        ))}
      </ul>
    </>
  );
}

function TableRow({ row, desktop }: { row: CancellationRow; desktop?: boolean }) {
  const body = (
    <>
      <td className="px-4 py-3 font-medium text-text-primary">{row.reference}</td>
      <td className="px-4 py-3">
        <span className="font-medium text-text-primary">{row.employee_name}</span>
        {desktop && (
          <span className="mt-0.5 block text-xs text-text-muted">
            {row.leave_type.name || "—"}
          </span>
        )}
      </td>
      <td className="px-4 py-3 text-text-secondary">{row.leave_type.name || "—"}</td>
      <td className="px-4 py-3 text-text-secondary">
        {formatDate(row.start_date) || "—"} → {formatDate(row.end_date) || "—"}
      </td>
      <td className="px-4 py-3 text-text-secondary">{row.working_days}</td>
      <td className="px-4 py-3 text-text-secondary">
        {formatDateTime(row.requested_at) || "—"}
      </td>
      <td className="px-4 py-3 text-text-secondary">
        {row.current_stage_role_label || "—"}
      </td>
      <td className="px-4 py-3">
        <StartsLabel row={row} />
      </td>
      {desktop && (
        <td className="px-2 py-3">
          <ChevronRight className="h-4 w-4 text-text-muted" aria-hidden="true" />
        </td>
      )}
    </>
  );

  if (desktop) {
    return (
      <tr className="border-b border-border-default last:border-b-0 transition-colors hover:bg-surface-hover">
        <RowLink row={row}>{body}</RowLink>
      </tr>
    );
  }

  return (
    <li className="rounded-xl border border-border-default bg-surface-card p-4 shadow-subtle">
      <RowLink row={row}>
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="truncate font-medium text-text-primary">{row.reference}</p>
            <p className="truncate text-sm text-text-secondary">{row.employee_name}</p>
            <p className="mt-1 text-xs text-text-muted">
              {row.leave_type.name || "—"} · {formatDate(row.start_date) || "—"} →{" "}
              {formatDate(row.end_date) || "—"}
            </p>
          </div>
          <div className="flex shrink-0 flex-col items-end gap-2">
            <StartsLabel row={row} />
            <ChevronRight className="h-4 w-4 text-text-muted" aria-hidden="true" />
          </div>
        </div>
      </RowLink>
    </li>
  );
}

function RowLink({
  row,
  children,
}: {
  row: CancellationRow;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={`/dashboard/approvals/${row.application_id}?cancellation=${row.request_id}`}
    >
      {children}
    </Link>
  );
}

export function StartsLabel({ row }: { row: CancellationRow }) {
  if (row.leave_started) {
    return <span className="font-medium text-status-rejected">Started</span>;
  }
  if (row.starts_in_days == null) {
    return <span className="text-text-muted">—</span>;
  }
  if (row.starts_in_days <= 3) {
    return (
      <span className="font-medium text-status-pending">
        Starts in {row.starts_in_days} day{row.starts_in_days === 1 ? "" : "s"}
      </span>
    );
  }
  return (
    <span className="text-text-muted">
      Starts in {row.starts_in_days} day{row.starts_in_days === 1 ? "" : "s"}
    </span>
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