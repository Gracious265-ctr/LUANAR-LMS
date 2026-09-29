"use client";

import { CheckCircle2, ChevronRight, Inbox, Loader2, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { formatDate } from "@/lib/plans/format";
import { fetchApprovalsList } from "@/lib/plans/service";
import type { PlanApprovalListItem, PlanApprovalListResponse } from "@/lib/plans/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/states";
import { PlanStatusBadge } from "./plan-status-badge";

type Tab = "pending" | "decided";

export function PlanApprovalsWorkspace() {
  const [tab, setTab] = useState<Tab>("pending");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<PlanApprovalListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    fetchApprovalsList(tab, page)
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
  }, [tab, page, reloadKey]);

  function switchTab(next: Tab) {
    if (next === tab) return;
    setTab(next);
    setPage(1);
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold tracking-tight text-text-primary">Plan approvals</h2>
        <p className="text-text-secondary">
          Plans awaiting your decision, and those you have already decided.
        </p>
      </div>

      <div className="flex items-center justify-between gap-3 border-b border-border-default">
        <div className="flex gap-1">
          <button
            type="button"
            onClick={() => switchTab("pending")}
            className={cn(
              "rounded-t-md px-4 py-2 text-sm font-medium transition-colors",
              tab === "pending"
                ? "border-b-2 border-brand-primary text-brand-primary"
                : "text-text-secondary hover:text-text-primary"
            )}
          >
            Pending
            {data && tab === "pending" && (
              <span className="ml-1.5 rounded-full bg-status-pending-subtle px-1.5 py-0.5 text-[11px] font-semibold text-status-pending">
                {data.count}
              </span>
            )}
          </button>
          <button
            type="button"
            onClick={() => switchTab("decided")}
            className={cn(
              "rounded-t-md px-4 py-2 text-sm font-medium transition-colors",
              tab === "decided"
                ? "border-b-2 border-brand-primary text-brand-primary"
                : "text-text-secondary hover:text-text-primary"
            )}
          >
            Decided
          </button>
        </div>
        <button
          type="button"
          onClick={() => setReloadKey((n) => n + 1)}
          className="rounded-md p-1 text-text-muted transition-colors hover:bg-surface-hover hover:text-text-primary"
          aria-label="Refresh"
        >
          <RefreshCw className="size-4" />
        </button>
      </div>

      {loading ? (
        <div className="flex justify-center py-10">
          <Loader2 className="size-5 animate-spin text-text-muted" />
        </div>
      ) : error ? (
        <p className="text-status-rejected">{error}</p>
      ) : !data || data.results.length === 0 ? (
        <EmptyState
          icon={<Inbox className="size-8 text-text-muted" />}
          title={tab === "pending" ? "Nothing pending" : "No decisions yet"}
          description={
            tab === "pending"
              ? "No plans are waiting on you right now."
              : "Plans you have decided will appear here."
          }
        />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border-default bg-surface-card shadow-subtle">
          <ul className="divide-y divide-border-default">
            {data.results.map((item) => (
              <PlanApprovalRow key={item.id} item={item} />
            ))}
          </ul>
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
        </div>
      )}
    </div>
  );
}

function PlanApprovalRow({ item }: { item: PlanApprovalListItem }) {
  return (
    <li>
      <Link
        href={`/dashboard/plans/approvals/${item.id}`}
        className="flex flex-wrap items-center justify-between gap-3 px-5 py-4 transition-colors hover:bg-surface-hover"
      >
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2.5">
            <p className="font-medium text-text-primary">{item.employee_name}</p>
            <PlanStatusBadge status={item.status} />
            {item.stage_role_label && (
              <span className="rounded-full bg-surface-muted px-2 py-0.5 text-[11px] font-medium text-text-secondary">
                with {item.stage_role_label}
              </span>
            )}
          </div>
          <p className="mt-1 text-sm text-text-secondary">
            {item.department || "—"} ·{" "}
            {formatDate(item.period_start)} → {formatDate(item.period_end)}
            {item.submitted_at && <> · submitted {formatDate(item.submitted_at)}</>}
          </p>
          {item.blocks.length > 0 && (
            <p className="mt-1 truncate text-xs text-text-muted">
              {item.blocks
                .map(
                  (block) =>
                    `${block.leave_type_code || "Leave"} ${formatDate(block.start_date)}–${formatDate(block.end_date)}`
                )
                .join(" · ")}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {item.my_decision && (
            <span
              className={cn(
                "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium",
                item.my_decision.action === "approve"
                  ? "bg-status-approved-subtle text-status-approved"
                  : "bg-status-rejected-subtle text-status-rejected"
              )}
            >
              <CheckCircle2 className="size-3" />
              {item.my_decision.action === "approve" ? "Approved" : "Rejected"}
            </span>
          )}
          <ChevronRight className="size-4 text-text-muted" />
        </div>
      </Link>
    </li>
  );
}