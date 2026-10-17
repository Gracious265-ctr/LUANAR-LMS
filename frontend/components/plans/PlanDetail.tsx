"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Bell, FileText } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useToast } from "@/components/ui/toast";
import { formatDateRange } from "@/lib/date";
import { PLAN_STATUS_META, isActionable } from "@/lib/plans/labels";
import { applyPlan } from "@/lib/plans/service";
import type { LeavePlan } from "@/lib/plans/types";

/**
 * The body of the emailed deep link, `/plans/{id}` (spec 2.8 / 4.6).
 *
 * A plain, authenticated view of one plan — no signed token, because it is not
 * a login link. Ownership is enforced by the API, so a wrong id simply 404s.
 * A live plan gets "Apply now"; the finished states say what happened and where
 * to go next.
 */
export function PlanDetail({ plan }: { plan: LeavePlan }) {
  const router = useRouter();
  const { showToast } = useToast();
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const meta = PLAN_STATUS_META[plan.status];
  const actionable = isActionable(plan);

  const handleApply = async () => {
    setApplying(true);
    setError(null);
    try {
      const { application_id } = await applyPlan(plan.id);
      showToast("Draft application created.");
      router.push(`/dashboard/leave/drafts?edit=${application_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start the application.");
      setApplying(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <Link
        href="/dashboard/plans"
        className="inline-flex items-center gap-1.5 text-sm font-medium text-text-secondary hover:text-text-primary"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        My Plans
      </Link>

      <Card>
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-semibold text-text-primary">{plan.leave_type_name}</span>
          <Badge tone={meta.badgeTone} size="sm">
            {meta.label}
          </Badge>
        </div>

        <div className="mt-3 text-sm text-text-muted">
          {formatDateRange(plan.planned_start_date, plan.planned_end_date)}
          {plan.financial_year_label && ` · ${plan.financial_year_label}`}
        </div>

        {plan.notified_at && (
          <p className="mt-2 flex items-center gap-1.5 text-xs text-text-muted">
            <Bell className="h-3.5 w-3.5" aria-hidden="true" />
            Reminder sent
          </p>
        )}

        {plan.notes && (
          <p className="mt-3 text-sm text-text-secondary">{plan.notes}</p>
        )}

        {error && (
          <p role="alert" className="mt-3 text-sm text-status-rejected">
            {error}
          </p>
        )}

        <div className="mt-5 flex flex-wrap items-center gap-3">
          {actionable && (
            <Button
              type="button"
              variant="primary"
              loading={applying}
              disabled={applying}
              onClick={handleApply}
            >
              {applying ? "Preparing…" : "Apply now"}
            </Button>
          )}

          {plan.status === "converted" && plan.converted_application && (
            <Button
              type="button"
              variant="secondary"
              onClick={() =>
                router.push(`/dashboard/leave/drafts?edit=${plan.converted_application}`)
              }
            >
              <FileText className="h-4 w-4" aria-hidden="true" />
              Open the draft
            </Button>
          )}

          {plan.status === "missed" && (
            <Button
              type="button"
              variant="secondary"
              onClick={() =>
                router.push(`/dashboard/plans/new?leaveType=${plan.leave_type_id}`)
              }
            >
              Plan for different dates
            </Button>
          )}
        </div>
      </Card>
    </div>
  );
}
