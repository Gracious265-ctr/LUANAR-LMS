"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Calendar, FileText, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useToast } from "@/components/ui/toast";
import { formatDateRange } from "@/lib/date";
import { PLAN_STATUS_META, isActionable } from "@/lib/plans/labels";
import { applyPlan, cancelPlan } from "@/lib/plans/service";
import type { LeavePlan } from "@/lib/plans/types";

/**
 * One plan in "My Plans".
 *
 * `upcoming` and `notified` are live and carry the two actions the spec calls
 * for (Apply Now, cancel); the finished states are read-only. Apply Now is a
 * single click that hands off to the existing Leave draft editor, so the whole
 * "plan → submitted application" path stays inside the two-click budget (spec
 * 2.3 / 3.4).
 */
export function PlanCard({
  plan,
  onCancel,
}: {
  plan: LeavePlan;
  /** Optimistically drops the plan from the host list on cancel. */
  onCancel?: (id: string) => void;
}) {
  const router = useRouter();
  const { showToast } = useToast();
  const [applying, setApplying] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const meta = PLAN_STATUS_META[plan.status];
  const Icon = meta.icon;
  const actionable = isActionable(plan);

  const handleApply = async () => {
    setApplying(true);
    setError(null);
    try {
      const { application_id } = await applyPlan(plan.id);
      router.push(`/dashboard/leave/drafts?edit=${application_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start the application.");
      setApplying(false);
    }
  };

  const handleCancel = async () => {
    setCancelling(true);
    onCancel?.(plan.id);
    try {
      await cancelPlan(plan.id);
      showToast("Plan cancelled.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not cancel this plan.");
      showToast("Could not cancel this plan.", "error");
      setConfirming(false);
    } finally {
      setCancelling(false);
    }
  };

  return (
    <Card>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <Calendar className="h-4 w-4 text-text-muted" aria-hidden="true" />
          <span className="font-medium text-text-primary">{plan.leave_type_name}</span>
          <Badge tone={meta.badgeTone} size="sm">
            <Icon className="h-3 w-3" aria-hidden="true" />
            {meta.label}
          </Badge>
        </div>
      </div>

      <div className="mt-2 text-sm text-text-muted">
        {formatDateRange(plan.planned_start_date, plan.planned_end_date)}
      </div>

      {plan.financial_year_label && (
        <div className="mt-1 text-xs text-text-muted">{plan.financial_year_label}</div>
      )}

      {plan.notes && (
        <p className="mt-3 line-clamp-2 text-sm text-text-secondary">{plan.notes}</p>
      )}

      {error && (
        <p role="alert" className="mt-3 text-xs text-status-rejected">
          {error}
        </p>
      )}

      {actionable ? (
        <div className="mt-4 flex items-center gap-2">
          <Button
            type="button"
            variant="primary"
            size="sm"
            loading={applying}
            disabled={applying || cancelling}
            onClick={handleApply}
          >
            {applying ? "Preparing…" : "Apply Now"}
          </Button>

          {confirming ? (
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-status-rejected">Cancel plan?</span>
              <Button
                type="button"
                variant="link"
                size="sm"
                loading={cancelling}
                disabled={cancelling}
                onClick={handleCancel}
                className="h-auto text-status-rejected"
              >
                {cancelling ? "…" : "Yes"}
              </Button>
              <Button
                type="button"
                variant="link"
                size="sm"
                onClick={() => setConfirming(false)}
                className="h-auto text-text-muted"
              >
                No
              </Button>
            </div>
          ) : (
            <Button
              type="button"
              aria-label="Cancel plan"
              variant="ghost"
              size="icon"
              onClick={() => setConfirming(true)}
              className="h-auto w-auto rounded p-1.5 hover:text-status-rejected"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          )}
        </div>
      ) : plan.status === "converted" && plan.converted_application ? (
        <div className="mt-4">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() =>
              router.push(`/dashboard/leave/drafts?edit=${plan.converted_application}`)
            }
          >
            <FileText className="h-3.5 w-3.5" aria-hidden="true" />
            Open the draft
          </Button>
        </div>
      ) : plan.status === "missed" ? (
        <div className="mt-4 text-sm text-text-muted">
          Leave date has passed —{" "}
          <button
            type="button"
            onClick={() => router.push(`/dashboard/plans/new?leaveType=${plan.leave_type_id}`)}
            className="font-medium text-brand-primary hover:underline"
          >
            plan a new one
          </button>
        </div>
      ) : null}
    </Card>
  );
}
