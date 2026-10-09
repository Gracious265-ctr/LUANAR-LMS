"use client";

import { ArrowLeft, Check, Send, Undo2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { formatDate, formatDateTime, formatPeriod, formatWorkingDays } from "@/lib/plans/format";
import { candidateSummary, planVerb } from "@/lib/plans/labels";
import { STATUS_TEXT } from "@/lib/status-styles";
import {
  confirmBlock,
  fetchPlan,
  releaseBlock,
  submitPlan,
} from "@/lib/plans/service";
import type {
  PeerConflict,
  PlanBlock,
  PlanDetail,
  PlanValidationIssue,
} from "@/lib/plans/types";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { ErrorState } from "@/components/ui/states";
import { Alert } from "@/components/ui/alert";
import { FormError } from "@/components/ui/form-error";
import { useToast } from "@/components/ui/toast";

import { BlockStatusBadge, PlanStatusBadge } from "./badges";
import { DetailRow } from "./panels";
import { Stepper } from "@/components/ui/Stepper";
import { chainFromPlanStages } from "@/lib/chain-steps";

export function PlanDetailView({ id }: { id: string }) {
  const [data, setData] = useState<PlanDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [issues, setIssues] = useState<PlanValidationIssue[]>([]);
  const [warnings, setWarnings] = useState<PeerConflict[]>([]);
  const { showToast } = useToast();
  const [busyBlock, setBusyBlock] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    fetchPlan(id)
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

  function retry() {
    setError("");
    setLoading(true);
    setReloadKey((value) => value + 1);
  }

  async function onSubmit() {
    setSubmitting(true);
    setActionError("");
    setIssues([]);
    setWarnings([]);
    const result = await submitPlan(id);
    if (result.ok) {
      setData(result.data);
      showToast(
        `Plan ${planVerb(result.data.meta.status)}`,
        result.data.meta.status === "rejected" ? "error" : "success"
      );
    } else {
      // A refused submission is a normal outcome, not a failure: the issues
      // name the block at fault so the owner can fix them in place.
      setActionError(result.message);
      setIssues(result.errors);
      setWarnings(result.warnings);
    }
    setSubmitting(false);
  }

  async function onBlockAction(
    block: PlanBlock,
    action: "confirm" | "release"
  ) {
    setBusyBlock(block.id);
    setActionError("");
    const result =
      action === "confirm"
        ? await confirmBlock(id, block.id)
        : await releaseBlock(id, block.id);
    if (result.ok) {
      showToast(action === "confirm" ? "Block confirmed" : "Block released");
      setReloadKey((value) => value + 1);
    } else {
      setActionError(result.message);
    }
    setBusyBlock("");
  }

  if (notFound) {
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <Card>
          <CardHeader title="Plan not found" />
          <p className="text-sm text-text-secondary">
            This plan is not available to you, or it no longer exists.
          </p>
        </Card>
        <BackLink />
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-2xl">
        <ErrorState message={error} onRetry={retry} />
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

  const peerConflicts = data.peer_conflicts ?? [];

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold tracking-tight text-text-primary">
              {formatPeriod(data.meta.period_start, data.meta.period_end)}
            </h1>
            <PlanStatusBadge status={data.meta.status} />
          </div>
          <p className="mt-1 text-sm text-text-secondary">
            {data.employee.name}
            {data.employee.team_name ? ` · ${data.employee.team_name}` : ""}
            {data.meta.financial_year_label
              ? ` · ${data.meta.financial_year_label}`
              : ""}
          </p>
        </div>
        {data.can_submit && (
          <Button
            variant="primary"
            onClick={onSubmit}
            loading={submitting}
            disabled={submitting}
          >
            <Send className="h-4 w-4" aria-hidden="true" />
            Submit for approval
          </Button>
        )}
      </div>
      {actionError && <FormError>{actionError}</FormError>}

      {issues.length > 0 && (
        <Card>
          <CardHeader title="Fix these before submitting" />
          <ul className="space-y-1 text-sm text-status-rejected">
            {issues.map((issue) => (
              <li key={`${issue.field}-${issue.code}-${issue.block ?? "plan"}`}>
                {issue.message}
              </li>
            ))}
          </ul>
        </Card>
      )}

      {warnings.length > 0 && (
        <Alert tone="pending" className="flex-col gap-0">
          <p className="font-medium">Overlaps with your team</p>
          <ul className="mt-1 space-y-0.5">
            {warnings.map((conflict) => (
              <li key={`${conflict.peer_name}-${conflict.overlaps_start}`}>
                {conflict.peer_name}: {formatDate(conflict.overlaps_start)} –{" "}
                {formatDate(conflict.overlaps_end)}
              </li>
            ))}
          </ul>
          <p className="mt-1">
            Warnings, not blocks: submit anyway if you intend to.
          </p>
        </Alert>
      )}

      <Card>
        <CardHeader title="Planned leave" />
        {data.blocks.length === 0 ? (
          <p className="text-sm text-text-secondary">No blocks in this plan.</p>
        ) : (
          <ul className="space-y-3">
            {data.blocks.map((block) => (
              <li
                key={block.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border-default p-3"
              >
                <div className="min-w-0">
                  <p className="text-sm font-medium text-text-primary">
                    {block.leave_type_name || "—"}
                  </p>
                  <p className="mt-0.5 text-xs text-text-secondary">
                    {formatDate(block.start_date)} – {formatDate(block.end_date)} ·{" "}
                    {formatWorkingDays(block.working_days)}
                  </p>
                  {block.confirmation_window_start && (
                    <p className={`mt-0.5 text-xs ${STATUS_TEXT.pending}`}>
                      Confirm by {formatDate(block.confirmation_window_start)}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <BlockStatusBadge status={block.status} />
                  {block.can_confirm && (
                    <Button
                      variant="secondary"
                      size="sm"
                      loading={busyBlock === block.id}
                      disabled={busyBlock === block.id}
                      onClick={() => onBlockAction(block, "confirm")}
                    >
                      <Check className="h-4 w-4" aria-hidden="true" />
                      Confirm
                    </Button>
                  )}
                  {block.can_release && (
                    <Button
                      variant="ghost"
                      size="sm"
                      loading={busyBlock === block.id}
                      disabled={busyBlock === block.id}
                      onClick={() => onBlockAction(block, "release")}
                    >
                      <Undo2 className="h-4 w-4" aria-hidden="true" />
                      Release
                    </Button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {data.stages.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-base font-semibold text-text-primary">
            Approval chain
          </h2>
          <Stepper steps={chainFromPlanStages(data.stages)} />
        </section>
      )}

      {data.decisions.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-base font-semibold text-text-primary">Decisions</h2>
          <ul className="space-y-2">
            {data.decisions.map((decision) => (
              <li
                key={decision.id}
                className="rounded-lg border border-border-default p-3 text-sm"
              >
                <p className="font-medium text-text-primary">
                  {decision.role_label} — {decision.action}
                </p>
                <p className="mt-0.5 text-xs text-text-secondary">
                  {decision.approver_name} ·{" "}
                  {formatDateTime(decision.decided_at) || "—"}
                </p>
                {decision.comment && (
                  <p className="mt-1 text-text-secondary">{decision.comment}</p>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {peerConflicts.length > 0 && (
        <Card>
          <CardHeader title="Overlaps in your team" />
          <ul className="space-y-1 text-sm text-text-secondary">
            {peerConflicts.map((conflict) => (
              <li key={`${conflict.peer_name}-${conflict.overlaps_start}`}>
                {conflict.peer_name} · {formatDate(conflict.overlaps_start)} –{" "}
                {formatDate(conflict.overlaps_end)}
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card>
        <CardHeader title="Summary" />
        <dl className="divide-y divide-border-default">
          <DetailRow label="Submitted" value={formatDateTime(data.meta.submitted_at)} />
          <DetailRow label="Decided" value={formatDateTime(data.meta.decided_at)} />
          <DetailRow
            label="Current step"
            value={
              data.stages.find((stage) => stage.status === "pending")
                ? candidateSummary(
                    data.stages.find((stage) => stage.status === "pending")!
                  )
                : null
            }
          />
        </dl>
      </Card>

      <BackLink />
    </div>
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
