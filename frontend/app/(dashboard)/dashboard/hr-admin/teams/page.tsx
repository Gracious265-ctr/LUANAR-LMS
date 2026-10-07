import Link from "next/link";
import { redirect } from "next/navigation";
import { Plus } from "lucide-react";

import { CampusQuickAdd } from "@/components/hr/campus-form";
import { TeamTable } from "@/components/hr/team-table";
import type { Campus, Team } from "@/lib/teams";
import { listCampuses, listTeams } from "@/lib/teams";
import { getCurrentUser } from "@/lib/auth";

const TEAMS_ERROR = "Unable to load teams. Please try again.";
const CAMPUSES_ERROR = "Unable to load campuses. Please try again.";

/**
 * Which slice of the lifecycle is on screen. Kept out of the URL because there
 * is nothing here to deep-link to: the list is short, and a person arriving
 * from a link wants the teams that are live, not the filter that was applied
 * when the link was made.
 */
async function TeamsPage({
  searchParams,
}: {
  searchParams: Promise<{ retired?: string }>;
}) {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (user.role !== "hr") {
    redirect("/dashboard");
  }

  const { retired } = await searchParams;
  const showRetired = retired === "1";

  const [teamsResult, campusesResult] = await Promise.all([
    listTeams({ includeInactive: showRetired }).then(
      (value) => ({ value, error: "" }),
      () => ({ value: [] as Team[], error: TEAMS_ERROR })
    ),
    listCampuses().then(
      (value) => ({ value, error: "" }),
      () => ({ value: [] as Campus[], error: CAMPUSES_ERROR })
    ),
  ]);

  const teams = teamsResult.value;
  const teamsError = teamsResult.error;
  const campuses = campusesResult.value;
  const campusesError = campusesResult.error;

  const filters = [
    { label: "In force and draft", href: "/dashboard/hr-admin/teams", current: !showRetired },
    { label: "Including retired", href: "/dashboard/hr-admin/teams?retired=1", current: showRetired },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-text-primary">Teams</h2>
          <p className="text-text-secondary">
            The routing unit: an employee belongs to a team, and that
            team&apos;s chain decides who approves their application. A team is
            either academic — sitting at a campus — or administration-wide, and
            only a team that is in force routes anything.
          </p>
        </div>
        <Link
          href="/dashboard/hr-admin/teams/new"
          className="inline-flex items-center gap-2 rounded-md bg-button-primary px-4 py-2 text-sm font-medium text-button-primary-foreground hover:bg-button-primary-hover"
        >
          <Plus className="h-4 w-4" />
          New team
        </Link>
      </div>

      <div
        className="flex flex-wrap items-center gap-2"
        role="group"
        aria-label="Filter teams by status"
      >
        {filters.map((filter) => (
          <Link
            key={filter.label}
            href={filter.href}
            aria-current={filter.current ? "page" : undefined}
            className={`rounded-full px-3 py-1 text-xs font-medium ${
              filter.current
                ? "bg-brand-primary text-button-primary-foreground"
                : "border border-border-default bg-surface-card text-text-secondary hover:bg-button-secondary-hover"
            }`}
          >
            {filter.label}
          </Link>
        ))}
      </div>

      {teamsError ? (
        <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
          <div className="rounded-md bg-status-rejected-subtle py-12 text-center text-sm text-status-rejected">
            {teamsError}
          </div>
        </div>
      ) : (
        <TeamTable teams={teams} />
      )}

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-lg font-semibold text-text-primary">Campuses</h3>
          <Link
            href="/dashboard/hr-admin/campuses"
            className="text-sm font-medium text-brand-primary hover:text-brand-primary-hover"
          >
            Manage campuses
          </Link>
        </div>
        {campusesError ? (
          <p className="text-sm text-status-rejected">{campusesError}</p>
        ) : (
          <CampusQuickAdd campuses={campuses} />
        )}
      </div>
    </div>
  );
}

export default TeamsPage;
