import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { ArrowLeft, Pencil } from "lucide-react";

import { TeamLifecycleActions } from "@/components/hr/team-lifecycle-actions";
import { TeamMemberList } from "@/components/hr/team-member-list";
import { TeamRoster } from "@/components/hr/team-roster";
import { teamStatusBadgeClass, teamStatusLabel } from "@/lib/teams";
import { getTeam } from "@/lib/teams";
import {
  listEmployeesByTeam,
  listUnassignedEmployees,
  type Employee,
} from "@/lib/employees";
import { getCurrentUser } from "@/lib/auth";
import { STATUS_TEXT } from "@/lib/status-styles";
import { FadeIn } from "@/components/motion/FadeIn";

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
  let members: Employee[] = [];
  let candidates: Employee[] = [];
  try {
    team = await getTeam(id);
  } catch {
    notFound();
  }

  // The roster is a read of the directory scoped to this team, and the
  // candidates are the people the directory has not placed anywhere yet. Both
  // are fetched here rather than in the browser so the page has no loading
  // flicker and the filters run where the data lives.
  try {
    [members, candidates] = await Promise.all([
      listEmployeesByTeam(id),
      listUnassignedEmployees(),
    ]);
  } catch {
    // A directory read that fails must not take the whole team page with it:
    // the chain and the team's status are still worth showing.
    members = [];
    candidates = [];
  }

  return (
    <FadeIn>
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
                  className={`inline-block rounded-sm px-2.5 py-0.5 text-xs font-medium ${teamStatusBadgeClass(
                    team.status
                  )}`}
                >
                  {teamStatusLabel(team.status)}
                </span>
              </div>
              <p className="text-text-secondary">
                {[
                  team.description,
                  team.department_name && `Department: ${team.department_name}`,
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
                <p className={`text-xs ${STATUS_TEXT.pending}`}>
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
          <TeamMemberList team={team} />
        </div>

        <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
          <h3 className="text-lg font-semibold text-text-primary">
            Whose leave this team routes
          </h3>
          <TeamRoster team={team} members={members} candidates={candidates} />
        </div>
      </div>
    </FadeIn>
  );
}
