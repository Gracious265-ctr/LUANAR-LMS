import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { ArrowLeft, Pencil } from "lucide-react";

import type {
  ApproverRole,
  CampusRoleAssignment,
  RoleAssignment,
  TeamRoleAssignment,
} from "@/lib/approver-roles";
import {
  listApproverRoles,
  listCampusRoleAssignments,
  listRoleAssignments,
  listTeamRoleAssignments,
} from "@/lib/approver-roles";
import type { Employee } from "@/lib/employees";
import { listAllEmployees } from "@/lib/employees";
import { getCurrentUser } from "@/lib/auth";
import { isTeamsAdministrator } from "@/lib/nav/teams-nav";
import type { Campus, Team } from "@/lib/teams";
import { getCampus, listTeams } from "@/lib/teams";
import type { WideHolding } from "@/components/hr/wide-holding-panel";
import { WideHoldingPanel } from "@/components/hr/wide-holding-panel";
import { teamStatusBadgeClass, teamStatusLabel } from "@/lib/teams";
import { buttonVariants } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/states";

const TEAMS_ERROR = "Unable to load the teams at this campus.";
const HOLDERS_ERROR = "Unable to load this campus's approver holdings.";
const ROLES_ERROR = "Unable to load approver roles, so holders cannot be chosen.";
const EMPLOYEES_ERROR = "Unable to load employees, so holders cannot be added.";

/**
 * One campus: the academic teams that sit at it, and who holds a role across
 * all of them.
 *
 * The campus-wide holding is the reason this screen exists as more than a
 * detail view. A campus-wide holder is reachable by every stage of every team
 * at the campus that has no team-wide holder for that role — which is how one
 * person can cover "Dean of Science" for every faculty team at a campus
 * without being written onto each of them in turn.
 */
export default async function CampusPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (!isTeamsAdministrator(user)) {
    redirect("/dashboard");
  }

  let campus: Campus;
  try {
    campus = await getCampus(id);
  } catch {
    notFound();
  }

  const [teamsResult, holdersResult, rolesResult, employeesResult, institutionHoldingsResult, teamHoldingsResult] =
    await Promise.all([
      listTeams({ includeInactive: true }).then(
        (value) => ({ value, error: "" }),
        () => ({ value: [] as Team[], error: TEAMS_ERROR })
      ),
      // Every campus's holdings, so this campus's own can be filtered out here
      // and the whole set still fed to the panel as the one-wide-approver pool.
      listCampusRoleAssignments().then(
        (value) => ({ value, error: "" }),
        () => ({ value: [] as CampusRoleAssignment[], error: HOLDERS_ERROR })
      ),
      listApproverRoles().then(
        (value) => ({ value, error: "" }),
        () => ({ value: [] as ApproverRole[], error: ROLES_ERROR })
      ),
      // A campus-wide holder must be an Academic employee — every team at a
      // campus is academic — so the feed reads only that half, server-side.
      listAllEmployees("academic").then(
        (value) => ({ value, error: "" }),
        () => ({ value: [] as Employee[], error: EMPLOYEES_ERROR })
      ),
      listRoleAssignments().catch(() => [] as RoleAssignment[]),
      listTeamRoleAssignments().catch(() => [] as TeamRoleAssignment[]),
    ]);

  const teams = teamsResult.value.filter((team) => team.campus === campus.id);
  const holdings = holdersResult.value
    .filter((assignment) => assignment.campus === campus.id)
    .map(
      (assignment): WideHolding => ({
        id: assignment.id,
        role: assignment.role,
        user: assignment.user,
        user_name: assignment.user_name,
        role_label: assignment.role_label,
      })
    );
  // A person holds one wide approver role, so everyone who already holds one
  // anywhere (institution, any team, any campus) is offered nowhere.
  const wideHolderUserIds = Array.from(
    new Set(
      [
        ...institutionHoldingsResult,
        ...teamHoldingsResult,
        ...holdersResult.value,
      ].map((assignment) => assignment.user)
    )
  );
  const roles = rolesResult.value.filter(
    (role) => role.is_active && !role.is_institution_wide
  );
  const employees = employeesResult.value;

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/dashboard/hr-admin/campuses"
          className="inline-flex items-center gap-1 text-sm font-medium text-brand-primary hover:text-brand-primary-hover"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to campuses
        </Link>
        <div className="mt-2 flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-3">
              <h2 className="text-2xl font-bold text-text-primary">
                {campus.name}
              </h2>
              <span
                className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${
                  campus.is_active
                    ? "bg-brand-secondary-subtle text-brand-secondary"
                    : "bg-surface-muted text-text-muted"
                }`}
              >
                {campus.is_active ? "Active" : "Retired"}
              </span>
            </div>
            <p className="text-text-secondary">
              {[
                campus.description,
                campus.code && `Code: ${campus.code}`,
              ]
                .filter(Boolean)
                .join(" · ")}
            </p>
          </div>
          <Link
            href={`/dashboard/hr-admin/campuses/${campus.id}/edit`}
            className={buttonVariants({ variant: "secondary" })}
          >
            <Pencil className="h-4 w-4" />
            Edit campus
          </Link>
        </div>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <h3 className="text-lg font-semibold text-text-primary">
          Academic teams at this campus
        </h3>
        <p className="mt-1 text-sm text-text-secondary">
          These teams&apos; stages may resolve to a campus-wide holding below.
          An administration team never sits at a campus, so it never appears
          here.
        </p>
        {teamsResult.error ? (
          <p className="mt-3 text-sm text-status-rejected">
            {teamsResult.error}
          </p>
        ) : teams.length === 0 ? (
          <EmptyState
            title="No teams sit here yet"
            description="A team is placed at a campus when it is created or edited, and only an academic team may be."
          />
        ) : (
          <ul className="mt-3 divide-y divide-border-default">
            {teams.map((team) => (
              <li
                key={team.id}
                className="flex flex-wrap items-center justify-between gap-2 py-2"
              >
                <div>
                  <Link
                    href={`/dashboard/teams/${team.id}`}
                    className="font-medium text-brand-primary hover:text-brand-primary-hover"
                  >
                    {team.name}
                  </Link>
                  <p className="text-xs text-text-muted">
                    {team.workflows.length === 0
                      ? "No chain yet"
                      : team.workflows
                          .map((workflow) => workflow.name)
                          .join(", ")}
                  </p>
                </div>
                <span
                  className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${teamStatusBadgeClass(
                    team.status
                  )}`}
                >
                  {teamStatusLabel(team.status)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <h3 className="text-lg font-semibold text-text-primary">
          Campus-wide approvers
        </h3>
        <p className="mt-1 text-sm text-text-secondary">
          One holder per role for this whole campus. Every stage at every team
          here falls back to these when it has no team-wide holder — and never
          when it has nobody, because an unheld role is refused at submission
          rather than guessed at.
        </p>
        {rolesResult.error && (
          <p className="mt-3 text-sm text-status-rejected">
            {rolesResult.error}
          </p>
        )}
        {holdersResult.error && (
          <p className="mt-3 text-sm text-status-rejected">
            {holdersResult.error}
          </p>
        )}
        {employeesResult.error && (
          <p className="mt-3 text-sm text-status-rejected">
            {employeesResult.error}
          </p>
        )}
        {roles.length === 0 ? (
          <p className="mt-3 text-sm text-text-muted">
            No active scoped roles to hold here. An institution-wide role is
            held on the Approvers page instead, and reaches only administration
            teams.
          </p>
        ) : (
          <div className="mt-4">
            <WideHoldingPanel
              scope="campus"
              roles={roles}
              scopeId={campus.id}
              requiredCategory="academic"
              employees={employees}
              holdings={holdings}
              excludedUserIds={wideHolderUserIds}
            />
          </div>
        )}
      </div>
    </div>
  );
}
