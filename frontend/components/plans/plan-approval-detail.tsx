"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import {
  formatDate,
  formatDateTime,
  formatPeriod,
  formatWorkingDays,
} from "@/lib/plans/format";
import { candidateSummary, planVerb } from "@/lib/plans/labels";
import { fetchPlanApproval } from "@/lib/plans/service";
import type {
  PlanAction,
  PlanApprovalDetail,
  PlanBlock,
  PlanDecision,
} from "@/lib/plans/types";
import { Card, CardHeader } from "@/components/ui/card";
import { ErrorState } from "@/components/ui/states";
import { Toast, useToast } from "@/components/ui/toast";

import { BlockStatusBadge, PlanStatusBadge } from "./badges";
import { DetailRow, StageChain } from "./panels";
import { PlanDecisionDialog } from "./plan-decision-dialog";
import { PlanDecisionPanel } from "./plan-decision-panel";

export function PlanApprovalDetailView({ id }: { id: string }) {
  const [data, setData] = useState<PlanApprovalDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState("");
  const [dialogKind, setDialogKind] = useState<PlanAction | null>(null);
  const { toast, showToast, dismissToast } = useToast();
  const [reloadKey, setReloadKey] = useState(0);

  const reload = useCallback(() => {
    setError("");
    setLoading(true);
    setReloadKey((value) => value + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetchPlanApproval(id)
      .then((result) => {
        if (cancelled) return;
        if (result.ok) {
          setData(result.data);
          setNotFound(false);
          setError("");
        } else if (result.kind === "not_found") {
          setNotFound(true);
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
  }, [id, reloadKey]);

  if (notFound) {
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <Card>
          <CardHeader title="Plan not available" />
          <p className="text-sm text-text-secondary">
            This plan is not one you can review, or it no longer exists.
          </p>
        </Card>
        <BackLink />
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="mx-auto max-w-2xl">
        <ErrorState message={error} onRetry={reload} />
      </div>
    );
  }

  if (loading || !data) {
    return (
      <div
        className="h-40 animate-pulse rounded-xl border border-border-default bg-surface-card"
        aria-busy="true"
        aria-label="Loading plan"
      />
    );
  }

  const workingDays = data.blocks.reduce(
    (total, block) => total + (block.working_days ?? 0),
    0
  );
  const pendingStage = data.stages.find((stage) => stage.status === "pending");

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      {toast && <Toast onDismiss={dismissToast}>{toast}</Toast>}

      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold tracking-tight text-text-primary">
              {formatPeriod(data.meta.period_start, data.meta.period_end)}
            </h1>
            <PlanStatusBadge status={data.meta.status} />
          </div>
          <p className="mt-1 text-sm text-text-secondary">
            {data.employee.name} ·{" "}
            {data.employee.team_name || data.employee.department}
          </p>
        </div>
        <PlanDecisionPanel data={data} onAction={setDialogKind} />
      </div>

      <Card>
        <CardHeader title="Planned leave" />
        <ul className="space-y-3">
          {data.blocks.map((block) => (
            <BlockRow key={block.id} block={block} />
          ))}
        </ul>
      </Card>

      <section className="space-y-3">
        <h2 className="text-base font-semibold text-text-primary">
          Approval chain
        </h2>
        <StageChain stages={data.stages} />
      </section>

      {data.decisions.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-base font-semibold text-text-primary">Decisions</h2>
          <DecisionList decisions={data.decisions} />
        </section>
      )}

      <Card>
        <CardHeader title="Summary" />
        <dl className="divide-y divide-border-default">
          <DetailRow label="Working days" value={formatWorkingDays(workingDays)} />
          <DetailRow label="Financial year" value={data.meta.financial_year_label} />
          <DetailRow
            label="Waiting on"
            value={pendingStage ? candidateSummary(pendingStage) : null}
          />
        </dl>
      </Card>

      <PlanDecisionDialog
        kind={dialogKind}
        data={data}
        onClose={() => setDialogKind(null)}
        onSubmitted={() => {
          // `dialogKind` is read before it is cleared, so the toast reports the
          // decision that was actually recorded rather than assuming success.
          const decided = dialogKind === "approve" ? "approved" : "rejected";
          setDialogKind(null);
          showToast(`Plan ${planVerb(decided)}`);
          reload();
        }}
        onReloadRequest={reload}
      />

      <BackLink />
    </div>
  );
}

function BlockRow({ block }: { block: PlanBlock }) {
  return (
    <li className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border-default p-3">
      <div className="min-w-0">
        <p className="text-sm font-medium text-text-primary">
          {block.leave_type_name || "—"}
        </p>
        <p className="mt-0.5 text-xs text-text-secondary">
          {formatDate(block.start_date)} – {formatDate(block.end_date)} ·{" "}
          {formatWorkingDays(block.working_days)}
        </p>
      </div>
      <BlockStatusBadge status={block.status} />
    </li>
  );
}

function DecisionList({ decisions }: { decisions: PlanDecision[] }) {
  return (
    <ul className="space-y-2">
      {decisions.map((decision) => (
        <li
          key={decision.id}
          className="rounded-lg border border-border-default p-3 text-sm"
        >
          <p className="font-medium text-text-primary">
            {decision.role_label} — {decision.action}
          </p>
          <p className="mt-0.5 text-xs text-text-secondary">
            {decision.approver_name}
            {decision.decided_at ? ` · ${formatDateTime(decision.decided_at)}` : ""}
          </p>
          {decision.comment && (
            <p className="mt-1 text-text-secondary">{decision.comment}</p>
          )}
        </li>
      ))}
    </ul>
  );
}

function BackLink() {
  return (
    <Link
      href="/dashboard/plans"
      className="inline-flex items-center gap-1.5 text-sm font-medium text-brand-primary hover:underline"
    >
      <ArrowLeft className="h-4 w-4" aria-hidden="true" />
      Back to plans
    </Link>
  );
}
