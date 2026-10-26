"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Plus } from "lucide-react";

import type { Delegation } from "@/lib/delegations";
import type { Employee } from "@/lib/employees";
import { useOverlayParam } from "@/lib/hooks/useOverlayParam";
import { AdminFormOverlay } from "@/components/hr/AdminFormOverlay";
import { DelegationForm } from "@/components/hr/delegation-form";
import { DelegationTable } from "@/components/hr/delegation-table";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

/** Query key for the delegation overlay. Distinct from the `?state` list filter. */
export const DELEGATION_PARAM = "delegation";

/** One entry in the state tab bar. The page owns every href. */
export interface DelegationStateTab {
  label: string;
  href: string;
  current: boolean;
}

export interface DelegationsSectionProps {
  delegations: Delegation[];
  /** Every employee, not one page: both pickers must offer the whole staff. */
  employees: Employee[];
  /**
   * The page's active `?state` filter, used to explain a created delegation that
   * the filter keeps out of the table.
   */
  stateFilter: string;
  /**
   * The state tab bar.
   *
   * Plain data rather than a JSX slot for the same reason as `TeamsSection`:
   * markup authored in the page's server component and rendered inside this
   * client component crosses the RSC boundary, where React stops recognising
   * statically written siblings and warns that each child needs a key.
   */
  tabs?: DelegationStateTab[];
  heading: string;
  /** Where "Show all states" goes, as a plain href across the RSC boundary. */
  clearFiltersHref?: string;
  /**
   * Set when the list read failed. It replaces the table but not the header or
   * the create trigger: the dialog does not need the list to be readable, so a
   * failed list should not also take away the one action that still works.
   */
  error?: string;
}

/**
 * The delegation list as a create overlay.
 *
 * There is no edit overlay and no edit route: a delegation is corrected by
 * approving a delegate, rejecting with a reason, or cancelling it, all of which
 * belong on the review page. So only `?delegation=new` is ever meaningful here,
 * and the row names stay links to that page.
 *
 * A new delegation is always `requested`, so creating one while a state filter
 * is active puts the row outside the table the page just refetched. The save
 * worked and the table is correct, but to HR the two together read as a failed
 * save, so the section says so rather than letting the row silently vanish.
 */
export function DelegationsSection({
  delegations,
  employees,
  stateFilter,
  tabs = [],
  heading,
  clearFiltersHref,
  error,
}: DelegationsSectionProps) {
  const router = useRouter();
  const overlay = useOverlayParam(DELEGATION_PARAM);
  // Visibility is decided from the list the server sends back after the refresh,
  // not from the created delegation's own `state`. That stays correct if the
  // filter is ever widened or the state machine gains a branch.
  const [createdId, setCreatedId] = useState<number | null>(null);
  const createdHidden =
    createdId !== null && !delegations.some((row) => row.id === createdId);

  return (
    <>
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-text-primary">{heading}</h3>
          <p className="mt-1 text-sm text-text-secondary">Approving, rejecting and cancelling happen on the delegation&apos;s own page.</p>
        </div>
        <Button
          variant="primary"
          onClick={overlay.openCreate}
          className="shrink-0"
        >
          <Plus className="h-4 w-4" />
          New delegation request
        </Button>
      </div>

      {tabs.length > 0 && (
        <div className="mb-4 flex flex-wrap gap-1 rounded-lg border border-border-default bg-surface-card p-1 shadow-subtle">
          {tabs.map((tab) => (
            <Link
              key={tab.href}
              href={tab.href}
              aria-current={tab.current ? "page" : undefined}
              className={
                tab.current
                  ? "rounded-md bg-brand-primary px-4 py-1.5 text-sm font-medium text-brand-primary-foreground"
                  : "rounded-md px-4 py-1.5 text-sm font-medium text-text-secondary hover:text-text-primary"
              }
            >
              {tab.label}
            </Link>
          ))}
        </div>
      )}

      {createdHidden && (
        <Alert tone="info" className="mb-4 flex-col items-start">
          <p>
            Saved, but it is not in this table. It was created as a{" "}
            <strong>requested</strong> delegation and this list is showing{" "}
            {stateFilter ? `${stateFilter} ones` : "another slice"}.
          </p>
          {clearFiltersHref && (
            <button
              type="button"
              onClick={() => router.push(clearFiltersHref)}
              className="mt-2 rounded-md px-2 py-1.5 text-sm font-medium text-brand-primary hover:text-brand-primary-hover"
            >
              Show all states
            </button>
          )}
        </Alert>
      )}

      {error ? (
        <div className="rounded-lg bg-status-rejected-subtle py-12 text-center text-sm text-status-rejected">
          {error}
        </div>
      ) : (
        <DelegationTable delegations={delegations} />
      )}

      <AdminFormOverlay
        open={overlay.isOpen}
        targetKey={overlay.target}
        size="md"
        title="New delegation request"
        description="Name the approver and the period."
        onOpenChange={(open) => {
          if (!open) overlay.close();
        }}
      >
        <DelegationForm
          employees={employees}
          onSuccess={(saved) => {
            setCreatedId(saved.id);
            overlay.close();
            router.refresh();
          }}
          onCancel={overlay.close}
        />
      </AdminFormOverlay>
    </>
  );
}