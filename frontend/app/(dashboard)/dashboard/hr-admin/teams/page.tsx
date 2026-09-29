import Link from "next/link";
import { redirect } from "next/navigation";
import { Plus } from "lucide-react";

import { CampusForm } from "@/components/hr/campus-form";
import { TeamMemberList } from "@/components/hr/team-member-list";
import type { Campus, Team } from "@/lib/teams";
import { listCampuses, listTeams } from "@/lib/teams";
import { getCurrentUser } from "@/lib/auth";
import { listAllEmployees, type Employee } from "@/lib/employees";

const TEAMS_ERROR = "Unable to load teams. Please try again.";
const CAMPUSES_ERROR = "Unable to load campuses. Please try again.";
const PEOPLE_ERROR = "Unable to load employees, so team members cannot be added.";

export default async function TeamsPage() {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (user.role !== "hr") {
    redirect("/dashboard");
  }

  // Three independent reads, issued together rather than in sequence, and
  // reported separately because each narrows a different action on this page.
  const [teamsResult, campusesResult, employeesResult] = await Promise.all([
    listTeams(true).then(
      (value) => ({ value, error: "" }),
      () => ({ value: [] as Team[], error: TEAMS_ERROR })
    ),
    listCampuses().then(
      (value) => ({ value, error: "" }),
      () => ({ value: [] as Campus[], error: CAMPUSES_ERROR })
    ),
    listAllEmployees().then(
      (value) => ({ value, error: "" }),
      () => ({ value: [] as Employee[], error: PEOPLE_ERROR })
    ),
  ]);

  const teams = teamsResult.value;
  const teamsError = teamsResult.error;
  const campuses = campusesResult.value;
  const campusesError = campusesResult.error;
  const employees = employeesResult.value;
  const peopleError = employeesResult.error;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold text-text-primary">Teams</h2>
          <p className="text-text-secondary">
            The routing unit: an employee belongs to a team, and that
            team&apos;s workflow decides who approves the application. Staff each
            section the workflow asks for.
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

      {teamsError ? (
        <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
          <div className="rounded-md bg-status-rejected-subtle py-12 text-center text-sm text-status-rejected">
            {teamsError}
          </div>
        </div>
      ) : (
        <>
          {teams.length === 0 ? (
            <div className="rounded-xl border border-border-default bg-surface-card p-6 text-center shadow-subtle">
              <p className="text-base font-medium text-text-primary">
                No teams found
              </p>
              <p className="mt-1 text-sm text-text-muted">
                Create a team to route its employees&apos; applications through
                their own approvers.
              </p>
            </div>
          ) : (
            teams.map((team) => (
              <div
                key={team.id}
                className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <h3 className="text-lg font-semibold text-text-primary">
                      <Link
                        href={`/dashboard/hr-admin/teams/${team.id}/edit`}
                        className="hover:text-brand-primary"
                      >
                        {team.name}
                      </Link>
                    </h3>
                    <p className="text-sm text-text-secondary">
                      {[
                        team.description,
                        team.campus_name && `Campus: ${team.campus_name}`,
                        `${team.member_count} member${team.member_count === 1 ? "" : "s"}`,
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    </p>
                  </div>
                  {team.is_active ? (
                    <span className="inline-block rounded-full bg-brand-secondary-subtle px-2.5 py-0.5 text-xs font-medium text-brand-secondary">
                      Active
                    </span>
                  ) : (
                    <span className="inline-block rounded-full bg-surface-muted px-2.5 py-0.5 text-xs font-medium text-text-muted">
                      Inactive
                    </span>
                  )}
                </div>

                {peopleError ? (
                  <p className="mt-3 text-sm text-status-rejected">
                    {peopleError}
                  </p>
                ) : (
                  <TeamMemberList team={team} employees={employees} />
                )}
              </div>
            ))
          )}

          <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
            <h3 className="mb-2 text-lg font-semibold text-text-primary">
              Campuses
            </h3>
            {campusesError ? (
              <p className="text-sm text-status-rejected">{campusesError}</p>
            ) : (
              <CampusForm campuses={campuses} />
            )}
          </div>
        </>
      )}
    </div>
  );
}
