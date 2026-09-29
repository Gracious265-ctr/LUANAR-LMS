"use client";

import { AlertTriangle, ArrowLeft, Check, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { formatDate } from "@/lib/plans/format";
import { PLAN_ACTION_META } from "@/lib/plans/labels";
import { fetchApprovalDetail } from "@/lib/plans/service";
import type {
  PlanApprovalDetail,
  PlanDecisionAction,
  PlanDetail,
} from "@/lib/plans/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/states";
import { Panel } from "@/components/approvals/panel";

import { PlanDecisionDialog } from "./plan-decision-dialog";
import { BlockStatusBadge, PlanStatusBadge, StageStatusBadge } from "./plan-status-badge";

export function PlanApprovalDetailView({ id }: { id: string }) {
  const [data, setData] = useState<PlanApprovalDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [decisionKind, setDecisionKind] = useState<PlanDecisionAction | null>(null);
  const [briefing, setBriefing] = useState<PlanDetail | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchApprovalDetail(id)
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
        if (!cancelled) setError("Failed to load the plan.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id, reloadKey]);

  if (loading && !data) {
    return <div className="py-16 text-center text-text-muted">Loading plan…</div>;
  }

  if (!data) {
    return (
      <EmptyState
        icon={<AlertTriangle className="size-8 text-text-muted" />}
        title="Could not load this plan"
        description={error}
        action={
          <Button variant="secondary" onClick={() => setReloadKey((n) => n + 1)}>
            Try again
          </Button>
        }
      />
    );
  }

  const { meta, employee, blocks, stages, decisions } = data;

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/dashboard/plans/approvals"
          className="inline-flex items-center gap-1 text-sm font-medium text-brand-primary hover:text-brand-primary-hover"
        >
          <ArrowLeft className="size-4" />
          Back to approvals
        </Link>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <h2 className="text-xl font-semibold tracking-tight text-text-primary">
            {employee.name}&apos;s plan
          </h2>
          <PlanStatusBadge status={meta.status} />
        </div>
        <p className="mt-1 text-sm text-text-secondary">
          {employee.department || "—"} · {formatDate(meta.period_start)} →{" "}
          {formatDate(meta.period_end)} · {meta.financial_year_label || "—"}
          {meta.submitted_at && <> · submitted {formatDate(meta.submitted_at)}</>}
        </p>
      </div>

      {briefing && (
        <div className="rounded-xl border border-status-approved bg-status-approved-subtle p-5">
          <p className="flex items-center gap-2 font-medium text-status-approved">
            <Check className="size-5" />
            Decision recorded. The plan is now{" "}
            {briefing.meta.status_label.toLowerCase()}.
          </p>
          <div className="mt-3 flex gap-2">
            <Link href={briefing.meta.id === id ? `/dashboard/plans/${briefing.meta.id}` : `/dashboard/plans/${briefing.meta.id}`}>
              <Button variant="primary" size="sm">
                Open plan
              </Button>
            </Link>
            <Button variant="secondary" size="sm" onClick={() => setBriefing(null)}>
              Review another
            </Button>
          </div>
        </div>
      )}

      {!briefing && data.can_decide && (
        <Panel title="Decision">
          <p className="mb-3 text-sm text-text-secondary">
            Approving reserves the plan&apos;s blocks against the leave balance.
            Rejecting requires a comment.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="primary"
              onClick={() => setDecisionKind("approve")}
            >
              <Check className="size-4" />
              Approve
            </Button>
            <Button
              variant="destructive"
              onClick={() => setDecisionKind("reject")}
            >
              <X className="size-4" />
              Reject
            </Button>
          </div>
        </Panel>
      )}

      {data.my_decision && (
        <span
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium",
            data.my_decision.action === "approve"
              ? "bg-status-approved-subtle text-status-approved"
              : "bg-status-rejected-subtle text-status-rejected"
          )}
        >
          {data.my_decision.action === "approve" ? (
            <Check className="size-3.5" />
          ) : (
            <X className="size-3.5" />
          )}
          Your decision:{" "}
          {PLAN_ACTION_META[data.my_decision.action].label.toLowerCase()} ·{" "}
          {formatDate(data.my_decision.decided_at)}
        </span>
      )}

      {blocks.length > 0 && (
        <Panel title="Leave blocks">
          <ul className="divide-y divide-border-default">
            {blocks.map((block) => (
              <li
                key={block.id}
                className="flex flex-wrap items-center justify-between gap-3 py-3 first:pt-0 last:pb-0"
              >
                <div className="text-sm">
                  <div className="font-medium text-text-primary">
                    {block.leave_type_name || block.leave_type_code || "Leave"}
                  </div>
                  <div className="text-text-secondary">
                    {formatDate(block.start_date)} → {formatDate(block.end_date)}{" "}
                    · {block.working_days ?? "—"} days
                  </div>
                </div>
                <BlockStatusBadge status={block.status} />
              </li>
            ))}
          </ul>
        </Panel>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {stages.length > 0 && (
          <Panel title="Approval stages">
            <ol className="space-y-3">
              {stages.map((stage) => (
                <li key={stage.id} className="flex items-start justify-between gap-3">
                  <div className="text-sm">
                    <div className="font-medium text-text-primary">
                      {stage.stage_order}. {stage.role_label}
                    </div>
                    <div className="text-xs text-text-muted">
                      {stage.approver_name || "Not assigned"}
                    </div>
                  </div>
                  <StageStatusBadge status={stage.status} />
                </li>
              ))}
            </ol>
          </Panel>
        )}

        {decisions.length > 0 && (
          <Panel title="Decisions">
            <ul className="space-y-3">
              {decisions.map((decision) => {
                const meta2 = PLAN_ACTION_META[decision.action];
                return (
                  <li key={decision.id} className="text-sm">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium text-text-primary">
                        {decision.role_label}
                      </span>
                      <span
                        className={cn(
                          "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium",
                          meta2.badgeClass
                        )}
                      >
                        <meta2.icon className="size-3" />
                        {meta2.label}
                      </span>
                    </div>
                    <div className="mt-0.5 text-xs text-text-muted">
                      {decision.approver_name} ·{" "}
                      {decision.decided_at ? formatDate(decision.decided_at) : "—"}
                    </div>
                    {decision.comment && (
                      <p className="mt-1 text-text-secondary">
                        “{decision.comment}”
                      </p>
                    )}
                  </li>
                );
              })}
            </ul>
          </Panel>
        )}
      </div>

      <PlanDecisionDialog
        kind={decisionKind}
        data={data}
        onClose={() => setDecisionKind(null)}
        onSubmitted={(briefingData) => {
          setDecisionKind(null);
          setBriefing(briefingData);
        }}
        onReloadRequest={() => {
          setDecisionKind(null);
          setReloadKey((n) => n + 1);
        }}
      />
    </div>
  );
}