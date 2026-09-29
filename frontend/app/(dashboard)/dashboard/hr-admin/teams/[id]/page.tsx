import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { ArrowLeft, Pencil } from "lucide-react";

import { TeamLifecycleActions } from "@/components/hr/team-lifecycle-actions";
import { TeamMemberList } from "@/components/hr/team-member-list";
import { teamStatusBadgeClass, teamStatusLabel } from "@/lib/teams";
import { getTeam } from "@/lib/teams";
import { getCurrentUser } from "@/lib/auth";
import { listAllEmployees, type Employee } from "@/lib/employees";

const PEOPLE_ERROR =
  "Unable to load employees, so the chain cannot be staffed from this screen.";

/**
 * One team: what it is, whether it is routing, and who can act at each step.
 *
 * The chain and its roster live here rather than on the list, because staffing
 * a step is a decision about one team and belongs next to that team's status —
 * a step staffed on an inactive team is not doing anything, and saying so in
 * the same view is the point.
 */
export default async function TeamPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (user.role !== "hr") {
    redirect("/dashboard");
  }

  let team;
  try {
    team = await getTeam(id);
  } catch {
    notFound();
  }

  // Separate from the team read so a failure to load the people list does not
  // take the team itself off the screen — the reader can still see the status
  // and act on it.
  let employees: Employee[] = [];
  let peopleError = "";
  try {
    employees = await listAllEmployees();
  } catch {
    peopleError = PEOPLE_ERROR;
  }

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/dashboard/hr-admin/teams"
          className="inline-flex items-center gap-1 text-sm font-medium text-brand-primary hover:text-brand-primary-hover"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to teams
        </Link>
        <div className="mt-2 flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-3">
              <h2 className="text-2xl font-bold text-text-primary">
                {team.name}
              </h2>
              <span
                className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${teamStatusBadgeClass(
                  team.status
                )}`}
              >
                {teamStatusLabel(team.status)}
              </span>
            </div>
            <p className="text-text-secondary">
              {[
                team.description,
                team.department && `Department: ${team.department}`,
                team.campus_name && `Campus: ${team.campus_name}`,
              ]
                .filter(Boolean)
                .join(" · ")}
            </p>
          </div>
          <Link
            href={`/dashboard/hr-admin/teams/${team.id}/edit`}
            className="inline-flex items-center gap-2 rounded-md border border-border-default bg-button-secondary px-4 py-2 text-sm font-medium text-text-secondary hover:bg-button-secondary-hover"
          >
            <Pencil className="h-4 w-4" />
            Edit team
          </Link>
        </div>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <div className="grid gap-4 md:grid-cols-3">
          <div>
            <span className="text-xs uppercase tracking-wide text-text-muted">
              Chain
            </span>
            <p className="text-sm font-medium text-text-primary">
              {team.workflow_name || "None"}
            </p>
          </div>
          <div>
            <span className="text-xs uppercase tracking-wide text-text-muted">
              In force
            </span>
            <p className="text-sm font-medium text-text-primary">
              {team.effective_from ?? "From activation"} to{" "}
              {team.effective_to ?? "no end date"}
            </p>
            {team.status === "active" && !team.is_effective && (
              <p className="text-xs text-status-pending">
                Not routing today — outside its effective window.
              </p>
            )}
          </div>
          <div>
            <span className="text-xs uppercase tracking-wide text-text-muted">
              People on the chain
            </span>
            <p className="text-sm font-medium text-text-primary">
              {team.member_count}
            </p>
          </div>
        </div>

        <div className="mt-4 border-t border-border-default pt-4">
          <TeamLifecycleActions team={team} />
        </div>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <h3 className="text-lg font-semibold text-text-primary">
          Who can approve
        </h3>
        {peopleError ? (
          <p className="mt-2 text-sm text-status-rejected">{peopleError}</p>
        ) : (
          <TeamMemberList team={team} employees={employees} />
        )}
      </div>
    </div>
  );
}
