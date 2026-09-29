"use client";

import { AlertTriangle, ArrowLeft, Lock, RotateCcw, Send } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { formatDate } from "@/lib/plans/format";
import { PLAN_ACTION_META } from "@/lib/plans/labels";
import {
  confirmBlock,
  fetchPlanDetail,
  releaseBlock,
  submitPlan,
} from "@/lib/plans/service";
import type { PlanDetail, PlanSubmitError } from "@/lib/plans/types";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/states";
import { Panel, DetailRow } from "@/components/approvals/panel";

import { BlockStatusBadge, PlanStatusBadge, StageStatusBadge } from "./plan-status-badge";

export function PlanDetailView({ id }: { id: string }) {
  const [data, setData] = useState<PlanDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [actionError, setActionError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    fetchPlanDetail(id)
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

  async function submit() {
    setBusy("submit");
    setActionError("");
    const result = await submitPlan(id);
    setBusy(null);
    if (result.ok) {
      setData(result.data);
    } else if (result.kind === "validation") {
      setActionError(
        validationMessage(result.errors, result.warnings)
      );
    } else {
      setActionError(result.message);
    }
  }

  async function confirm(blockId: string) {
    setBusy(blockId);
    setActionError("");
    const result = await confirmBlock(id, blockId);
    setBusy(null);
    if (!result.ok) setActionError(result.message);
    setReloadKey((n) => n + 1);
  }

  async function release(blockId: string) {
    setBusy(blockId);
    setActionError("");
    const result = await releaseBlock(id, blockId);
    setBusy(null);
    if (!result.ok) setActionError(result.message);
    setReloadKey((n) => n + 1);
  }

  if (loading && !data) {
    return <div className="py-16 text-center text-text-muted">Loading plan…</div>;
  }

  if (!data) {
    return (
      <EmptyState
        icon={<AlertTriangle className="size-8 text-text-muted" />}
        title="Could not load this plan"
        description={error}
        action={reloadKey > 0 || error ? (
          <Button variant="secondary" onClick={() => setReloadKey((n) => n + 1)}>
            Try again
          </Button>
        ) : undefined}
      />
    );
  }

  const { meta, employee, blocks, stages, decisions } = data;
  const peerConflicts = data.peer_conflicts ?? [];

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/dashboard/plans"
          className="inline-flex items-center gap-1 text-sm font-medium text-brand-primary hover:text-brand-primary-hover"
        >
          <ArrowLeft className="size-4" />
          Back to plans
        </Link>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <h2 className="text-xl font-semibold tracking-tight text-text-primary">
            {employee.name}&apos;s plan
          </h2>
          <PlanStatusBadge status={meta.status} />
        </div>
        <p className="mt-1 text-sm text-text-secondary">
          {formatDate(meta.period_start)} → {formatDate(meta.period_end)} ·{" "}
          {meta.financial_year_label || "—"} · cycle {meta.submission_cycle}
          {employee.department && <> · {employee.department}</>}
        </p>
      </div>

      {actionError && (
        <p className="rounded-lg border border-status-rejected bg-status-rejected-subtle px-3 py-2 text-sm text-status-rejected">
          {actionError}
        </p>
      )}

      {data.can_submit && (
        <Panel title="Submit this plan" className="border-brand-primary/30">
          <p className="mb-3 text-sm text-text-secondary">
            Submitting sends the plan to your approval chain. Blocks are
            validated against your balance and leave rules before they are
            reserved.
          </p>
          <Button
            variant="primary"
            loading={busy === "submit"}
            onClick={() => void submit()}
          >
            <Send className="size-4" />
            Submit for approval
          </Button>
        </Panel>
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
                  {block.confirmation_window_start && (
                    <div className="text-xs text-text-muted">
                      Confirm by {formatDate(block.confirmation_window_start)}
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <BlockStatusBadge status={block.status} />
                  {block.can_confirm && (
                    <Button
                      size="sm"
                      variant="primary"
                      loading={busy === block.id}
                      onClick={() => void confirm(block.id)}
                    >
                      <Lock className="size-3.5" />
                      Confirm
                    </Button>
                  )}
                  {block.can_release && (
                    <Button
                      size="sm"
                      variant="secondary"
                      loading={busy === block.id}
                      onClick={() => void release(block.id)}
                    >
                      <RotateCcw className="size-3.5" />
                      Release
                    </Button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </Panel>
      )}

      {peerConflicts.length > 0 && (
        <Panel title="Peer overlap warnings">
          <p className="mb-3 text-sm text-text-secondary">
            These blocks overlap with a colleague in your department and grade.
            Warnings only — resolve overlaps with your team before confirming.
          </p>
          <ul className="space-y-2">
            {peerConflicts.map((conflict, index) => (
              <li
                key={`${conflict.plan_id}-${index}`}
                className="rounded-lg bg-status-rejected-subtle px-3 py-2 text-sm text-status-rejected"
              >
                <span className="font-medium">{conflict.peer_name}</span>{" "}
                <span className="text-text-secondary">
                  ({conflict.peer_department || "—"}) overlaps{" "}
                  {formatDate(conflict.overlaps_start)} →{" "}
                  {formatDate(conflict.overlaps_end)}.
                </span>
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

      {meta.status === "approved" && (
        <Panel title="Plan details">
          <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <DetailRow label="Submitted">{formatDate(meta.submitted_at)}</DetailRow>
            <DetailRow label="Decided">{formatDate(meta.decided_at)}</DetailRow>
            <DetailRow label="Blocks">{blocks.length}</DetailRow>
            <DetailRow label="Working days">
              {blocks.reduce(
                (sum, block) => sum + (block.working_days ?? 0),
                0
              )}
            </DetailRow>
          </dl>
        </Panel>
      )}
    </div>
  );
}

function validationMessage(
  errors: PlanSubmitError[] | undefined,
  warnings: string[] | undefined
): string {
  const parts: string[] = [];
  if (errors && errors.length > 0) {
    parts.push(errors.map((e) => e.message).join(" "));
  }
  if (warnings && warnings.length > 0) {
    parts.push(warnings.join(" "));
  }
  return parts.length > 0 ? parts.join(" ") : "The plan could not be submitted.";
}