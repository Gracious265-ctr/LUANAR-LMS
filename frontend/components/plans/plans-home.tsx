"use client";

import { CalendarPlus, Loader2, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { fetchCapabilities, fetchMyPlans } from "@/lib/plans/service";
import type { PlanCapabilities, PlanRow } from "@/lib/plans/types";
import type { UserRole } from "@/lib/employees";
import { buttonVariants } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/states";

import { PlanCard } from "./plan-card";
import { PendingConfirmationsPanel } from "./pending-confirmations-panel";

const APPROVER_ROLES: UserRole[] = ["supervisor", "hod", "dean", "registrar", "dvc"];

export function PlansHome({ role }: { role: UserRole }) {
  const [plans, setPlans] = useState<PlanRow[]>([]);
  const [caps, setCaps] = useState<PlanCapabilities>({
    is_approver: false,
    approver_pending_count: 0,
    pending_confirmation_count: 0,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  const isApprover = APPROVER_ROLES.includes(role);
  const isHR = role === "hr";

  useEffect(() => {
    let cancelled = false;
    Promise.all([fetchMyPlans("mine"), fetchCapabilities()])
      .then(([planResult, capResult]) => {
        if (cancelled) return;
        if (planResult.ok) {
          setPlans(planResult.data.results);
          setError("");
        } else {
          setError(planResult.message);
        }
        setCaps(capResult);
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
  }, [reloadKey]);

  const showTeam = isApprover || isHR;
  const showConfirmQueue = caps.pending_confirmation_count > 0;

  return (
    <div className="space-y-6">
      <div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold tracking-tight text-text-primary">My plans</h2>
            <p className="text-text-secondary">
              Plan your leave year ahead. Blocks are validated and reserved when
              your plan is approved.
            </p>
          </div>
          <Link
            href="/dashboard/plans/new"
            className={buttonVariants({ variant: "primary" })}
          >
            <CalendarPlus className="size-4" />
            New plan
          </Link>
        </div>
      </div>

      {showConfirmQueue && <PendingConfirmationsPanel />}

      {(showTeam || isHR) && (
        <div className="flex flex-wrap gap-2">
          {showTeam && (
            <Link
              href="/dashboard/plans/team"
              className={buttonVariants({ variant: "secondary", size: "sm" })}
            >
              Team plans
            </Link>
          )}
          {isApprover && (
            <Link
              href="/dashboard/plans/approvals"
              className={buttonVariants({ variant: "secondary", size: "sm" })}
            >
              Approvals
              {caps.approver_pending_count > 0 && (
                <span className="ml-1 rounded-full bg-status-pending-subtle px-1.5 py-0.5 text-[11px] font-semibold text-status-pending">
                  {caps.approver_pending_count}
                </span>
              )}
            </Link>
          )}
          {isHR && (
            <>
              <Link
                href="/dashboard/plans/admin"
                className={buttonVariants({ variant: "secondary", size: "sm" })}
              >
                All plans
              </Link>
              <Link
                href="/dashboard/plans/settings"
                className={buttonVariants({ variant: "secondary", size: "sm" })}
              >
                Settings
              </Link>
            </>
          )}
        </div>
      )}

      <div>
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-base font-semibold text-text-primary">
            {plans.length} {plans.length === 1 ? "plan" : "plans"}
          </h3>
          <button
            type="button"
            onClick={() => setReloadKey((n) => n + 1)}
            className="rounded-md p-1 text-text-muted transition-colors hover:bg-surface-hover hover:text-text-primary"
            aria-label="Refresh plans"
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
        ) : plans.length === 0 ? (
          <EmptyState
            icon={<CalendarPlus className="size-8 text-text-muted" />}
            title="No plans yet"
            description="Create a plan for the coming financial year to reserve your leave blocks."
            action={
              <Link
                href="/dashboard/plans/new"
                className={buttonVariants({ variant: "primary" })}
              >
                Create your first plan
              </Link>
            }
          />
        ) : (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {plans.map((plan) => (
              <PlanCard key={plan.id} plan={plan} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}