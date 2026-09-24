"use client";

import { useState } from "react";

import Link from "next/link";
import {
  ArrowLeft,
  ArrowRight,
  Ban,
  RefreshCw,
  TriangleAlert,
} from "lucide-react";

import { cn } from "@/lib/utils";

import { formatDate, formatDateTime } from "@/lib/tracking/format";
import {
  startsInLabel,
} from "@/lib/cancellation/format";
import { useCancellationApprovalsList } from "@/lib/cancellation/hooks";
import type { CancellationApprovalListItem } from "@/lib/cancellation/types";

import { Tabs } from "../ui/tabs";

const PAGE_SIZE = 20;

export function CancellationRequestsTable() {
  const [tab, setTab] = useState<"pending" | "decided">("pending");
  const [page, setPage] = useState(1);

  const { state, refetch } = useCancellationApprovalsList({
    tab,
    page,
    pageSize: PAGE_SIZE,
  });

  function changeTab(next: "pending" | "decided") {
    setTab(next);
    setPage(1);
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <Tabs
          label="Cancellation queue tabs"
          tabs={[
            { value: "pending", label: "Pending" },
            { value: "decided", label: "Decided by me" },
          ]}
          value={tab}
          onChange={changeTab}
        />
      </div>

      <div aria-busy={state.status === "loading"}>
        {state.status === "loading" && <ListSkeleton />}

        {state.status === "error" && (
          <ErrorState message={state.message} onRetry={refetch} />
        )}

        {state.status === "ok" && state.data.results.length === 0 && (
          <EmptyState tab={tab} />
        )}

        {state.status === "ok" && state.data.results.length > 0 && (
          <>
            <div className="overflow-x-auto rounded-xl border border-border-default bg-surface-card shadow-subtle">
              <table className="w-full min-w-[820px] text-left text-sm">
                <thead>
                  <tr className="border-b border-border-default text-xs tracking-wide text-text-secondary uppercase">
                    <th scope="col" className="px-4 py-3 font-medium">
                      Reference
                    </th>
                    <th scope="col" className="px-4 py-3 font-medium">
                      Employee
                    </th>
                    <th scope="col" className="px-4 py-3 font-medium">
                      Leave type
                    </th>
                    <th scope="col" className="px-4 py-3 font-medium">
                      Leave period
                    </th>
                    <th scope="col" className="px-4 py-3 font-medium">
                      Days
                    </th>
                    <th scope="col" className="px-4 py-3 font-medium">
                      Requested on
                    </th>
                    <th scope="col" className="px-4 py-3 font-medium">
                      Current stage
                    </th>
                    <th scope="col" className="px-4 py-3 font-medium">
                      Leave starts
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-default">
                  {state.data.results.map((item) => (
                    <ListRow key={item.id} item={item} />
                  ))}
                </tbody>
              </table>
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

function ListRow({ item }: { item: CancellationApprovalListItem }) {
  const start = startsInLabel(item.start_date, item.leave_started);
  return (
    <tr className="transition-colors hover:bg-surface-hover">
      <td className="px-4 py-3 font-medium">
        <Link
          href={`/approvals/${item.application_id}?cancellation=${item.id}`}
          className="rounded text-brand-primary transition-colors hover:text-brand-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary"
        >
          {item.application_reference}
        </Link>
      </td>
      <td className="px-4 py-3 text-text-primary">{item.employee_name}</td>
      <td className="px-4 py-3 text-text-secondary">{item.leave_type}</td>
      <td className="px-4 py-3 text-text-secondary">
        {formatDate(item.start_date)} – {formatDate(item.end_date)}
      </td>
      <td className="px-4 py-3 text-text-secondary">{item.working_days}</td>
      <td className="px-4 py-3 text-text-secondary">
        {formatDateTime(item.requested_at)}
      </td>
      <td className="px-4 py-3 text-text-primary">{item.current_stage_role ?? "—"}</td>
      <td
        className={cn(
          "px-4 py-3",
          start.variant === "started" && "font-semibold text-status-rejected",
          start.variant === "soon" && "font-medium text-status-pending"
        )}
      >
        {start.label}
      </td>
    </tr>
  );
}

function firstIndex(page: number, count: number): number {
  if (count === 0) return 0;
  return (page - 1) * PAGE_SIZE + 1;
}

function lastIndex(page: number, count: number): number {
  return Math.min(page * PAGE_SIZE, count);
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

function EmptyState({ tab }: { tab: "pending" | "decided" }) {
  return (
    <div className="rounded-xl border border-border-default bg-surface-card p-10 text-center shadow-subtle">
      <Ban className="mx-auto h-10 w-10 text-text-muted" aria-hidden="true" />
      <h2 className="mt-4 text-base font-semibold text-text-primary">
        {tab === "pending"
          ? "No cancellation requests are waiting for you"
          : "You haven't decided any cancellation requests yet"}
      </h2>
      <p className="mx-auto mt-1 max-w-sm text-sm text-text-secondary">
        {tab === "pending"
          ? "Requests that need your approval will appear here."
          : "Your decisions will appear here."}
      </p>
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
        Could not load cancellation requests
      </h2>
      <p className="mx-auto mt-1 max-w-sm text-sm text-text-secondary">
        {message}
      </p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-5 inline-flex items-center gap-1.5 rounded-lg bg-brand-primary px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-brand-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
      >
        <RefreshCw className="h-4 w-4" aria-hidden="true" />
        Try again
      </button>
    </div>
  );
}