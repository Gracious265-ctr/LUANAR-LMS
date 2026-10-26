"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { Plus } from "lucide-react";

import type { ApproverRole } from "@/lib/approver-roles";
import type { Employee } from "@/lib/employees";
import type { Campus, Team } from "@/lib/teams";
import { useOverlayParam } from "@/lib/hooks/useOverlayParam";
import { AdminFormOverlay } from "@/components/hr/AdminFormOverlay";
import { TeamForm } from "@/components/hr/team-form";
import { TeamTable } from "@/components/hr/team-table";
import { Button } from "@/components/ui/button";

/** Query key for the team overlay. Distinct from the `?retired` list filter. */
export const TEAM_PARAM = "team";

/** One entry in the retired/in-force toggle. The page owns every href. */
export interface TeamStatusFilter {
  label: string;
  href: string;
  current: boolean;
}

export interface TeamsSectionProps {
  teams: Team[];
  campuses: Campus[];
  /** Every approver role: the chain builder picks one per step. */
  roles: ApproverRole[];
  rolesError: string;
  /**
   * Everyone the create overlay's manager picker may offer. The manager is
   * designated when the team is created, so the people who may hold it have to
   * be on the page before the overlay opens.
   */
  employees?: Employee[];
  /**
   * Every current wide approver, whatever their scope. A person holds only one
   * wide approver role, so those who already hold one are not offered as a
   * team's manager.
   */
  wideHolderUserIds?: number[];
  /**
   * The retired/in-force toggle.
   *
   * Plain data rather than a JSX slot, because markup authored in the page's
   * server component and rendered inside this client component crosses the RSC
   * boundary. The boundary re-creates those elements without the dev runtime's
   * "written as static siblings" flag, so React treats them as a list and warns
   * that each child needs a key. Passing data keeps the array on this side of
   * the boundary, and the page still owns the URLs.
   */
  filters?: TeamStatusFilter[];
  error?: string;
  /**
   * Whether the viewer may create a team.
   *
   * Creating a team is HR's, not a manager's: a manager inherits the teams they
   * are flagged for and configures their chains and rosters, but does not mint
   * new routing units. Defaults to `true` so the existing HR caller is
   * unchanged.
   */
  canCreate?: boolean;
}

/**
 * The teams list as a create overlay.
 *
 * Only create is here. Editing a team stays a page, because what the edit form
 * leaves out is the point of it: the per-section roster is managed on the team's
 * own page, so an edit dialog would show a form whose most important field is
 * not in it.
 *
 * There is deliberately no "saved but not in this table" warning here, unlike the
 * delegations and employees lists. A new team is a draft, and the list query
 * excludes only retired teams, so a draft is in the table under both filters —
 * the warning would be code that can never fire.
 */
export function TeamsSection({
  teams,
  campuses,
  roles,
  rolesError,
  employees = [],
  wideHolderUserIds = [],
  filters = [],
  error,
  canCreate = true,
}: TeamsSectionProps) {
  const router = useRouter();
  const overlay = useOverlayParam(TEAM_PARAM);

  return (
    <>
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-text-primary">Teams</h3>
        </div>
        {canCreate && (
          <Button
            variant="primary"
            onClick={overlay.openCreate}
            className="shrink-0"
          >
            <Plus className="h-4 w-4" />
            New team
          </Button>
        )}
      </div>

      {filters.length > 0 && (
        <div
          className="mb-4 flex flex-wrap items-center gap-2"
          role="group"
          aria-label="Filter teams by status"
        >
          {filters.map((filter) => (
            <Link
              key={filter.label}
              href={filter.href}
              aria-current={filter.current ? "page" : undefined}
              className={`rounded-sm px-3 py-1 text-xs font-medium ${
                filter.current
                  ? "bg-brand-primary text-button-primary-foreground"
                  : "border border-border-default bg-surface-card text-text-secondary hover:bg-button-secondary-hover"
              }`}
            >
              {filter.label}
            </Link>
          ))}
        </div>
      )}

      {error ? (
        <div className="rounded-lg bg-status-rejected-subtle py-12 text-center text-sm text-status-rejected">
          {error}
        </div>
      ) : (
        <TeamTable teams={teams} />
      )}

      {canCreate && (
        <AdminFormOverlay
          open={overlay.isOpen}
          targetKey={overlay.target}
          size="lg"
          title="New team"
          description="A team routes nothing until it owns an approval chain."
          onOpenChange={(open) => {
            if (!open) overlay.close();
          }}
        >
          <TeamForm
            campuses={campuses}
            roles={roles}
            rolesError={rolesError}
            employees={employees}
            wideHolderUserIds={wideHolderUserIds}
            onSuccess={() => {
              overlay.close();
              router.refresh();
            }}
            onCancel={overlay.close}
          />
        </AdminFormOverlay>
      )}
    </>
  );
}