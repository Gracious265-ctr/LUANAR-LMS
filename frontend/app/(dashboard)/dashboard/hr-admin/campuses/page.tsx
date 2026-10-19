import Link from "next/link";
import { redirect } from "next/navigation";
import { Plus } from "lucide-react";

import { CampusTable } from "@/components/hr/campus-table";
import type { Campus, Team } from "@/lib/teams";
import { listCampuses, listTeams } from "@/lib/teams";
import { getCurrentUser } from "@/lib/auth";
import { isOrganisationAdministrator } from "@/lib/nav/organisation-nav";
import { buttonVariants } from "@/components/ui/button";

const CAMPUSES_ERROR = "Unable to load campuses. Please try again.";
const TEAMS_ERROR = "Unable to load teams, so the campuses cannot be listed.";

/**
 * Campuses, and the academic teams that sit at each.
 *
 * A campus is not reference data in the ordinary sense: choosing one is what
 * makes campus-wide approvers reachable for a team's stages, so the list shows
 * the teams that have made that choice rather than just the rows. Retired
 * campuses stay on the page — a campus a team already sits at must still be
 * readable, and hiding it would make the team look like it sits nowhere.
 */
export default async function CampusesPage() {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (!isOrganisationAdministrator(user)) {
    redirect("/dashboard");
  }

  const [campusesResult, teamsResult] = await Promise.all([
    listCampuses(true).then(
      (value) => ({ value, error: "" }),
      () => ({ value: [] as Campus[], error: CAMPUSES_ERROR })
    ),
    listTeams({ includeInactive: true }).then(
      (value) => ({ value, error: "" }),
      () => ({ value: [] as Team[], error: TEAMS_ERROR })
    ),
  ]);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-text-primary">Campuses</h2>
          <p className="text-text-secondary">
            Where an academic team sits. A campus scopes campus-wide approvers
            to the teams at it, and an administration team — which is
            institution-wide — never sits at one.
          </p>
        </div>
        <Link
          href="/dashboard/hr-admin/campuses/new"
          className={buttonVariants({ variant: "primary" })}
        >
          <Plus className="h-4 w-4" />
          New campus
        </Link>
      </div>

      {campusesResult.error ? (
        <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
          <div className="rounded-md bg-status-rejected-subtle py-12 text-center text-sm text-status-rejected">
            {campusesResult.error}
          </div>
        </div>
      ) : (
        <CampusTable
          campuses={campusesResult.value}
          teams={teamsResult.value}
        />
      )}

      {teamsResult.error && (
        <p className="rounded-md bg-status-rejected-subtle p-3 text-sm text-status-rejected">
          {teamsResult.error}
        </p>
      )}
    </div>
  );
}
