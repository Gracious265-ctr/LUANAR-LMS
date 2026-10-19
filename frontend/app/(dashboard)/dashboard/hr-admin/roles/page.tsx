import Link from "next/link";
import { redirect } from "next/navigation";

import { RolesSection } from "@/components/hr/RolesSection";
import type {
  ApproverRole,
  CampusRoleAssignment,
  TeamRoleAssignment,
} from "@/lib/approver-roles";
import {
  listApproverRoles,
  listCampusRoleAssignments,
  listRoleAssignments,
  listTeamRoleAssignments,
} from "@/lib/approver-roles";
import { getCurrentUser } from "@/lib/auth";
import { isOrganisationAdministrator } from "@/lib/nav/organisation-nav";
import { listCampuses, listTeams } from "@/lib/teams";
import { FadeIn } from "@/components/motion/FadeIn";
import { buttonVariants } from "@/components/ui/button";
import { Alert } from "@/components/ui/states";

const ROLES_ERROR = "Unable to load approver roles. Please try again.";
const HOLDERS_ERROR = "Unable to load who currently holds each role.";

async function RolesPage() {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (!isOrganisationAdministrator(user)) {
    redirect("/dashboard");
  }

  // One read for the roles, and one for every wide holding at all three
  // scopes: who holds what decides a role's scope, so the table is fed from
  // the same list the Approvers page writes, not a second copy of it. A
  // holding is grouped by its role so a row can name every person that covers
  // it — "held by this one person at campus scope" is a different answer from
  // "an active institution-wide role with nobody holding it", and both are
  // read straight from the same data.
  //
  // Retired roles stay on the page: HR needs to see that a role exists and why
  // it cannot be used, and a workflow may still name it.
  const [
    rolesResult,
    institutionResult,
    teamResult,
    campusResult,
    teamsResult,
    campusesResult,
  ] = await Promise.all([
    listApproverRoles(true).then(
      (value) => ({ value, error: "" }),
      () => ({ value: [] as ApproverRole[], error: ROLES_ERROR })
    ),
    listRoleAssignments().then(
      (assignments) => ({
        value: groupByRole(assignments),
        error: "",
      }),
      () => ({ value: undefined, error: HOLDERS_ERROR })
    ),
    listTeamRoleAssignments().then(
      (assignments) => ({
        value: groupByRole(assignments),
        error: "",
      }),
      () => ({ value: {} as Record<number, TeamRoleAssignment[]>, error: HOLDERS_ERROR })
    ),
    listCampusRoleAssignments().then(
      (assignments) => ({
        value: groupByRole(assignments),
        error: "",
      }),
      () => ({ value: {} as Record<number, CampusRoleAssignment[]>, error: HOLDERS_ERROR })
    ),
    listTeams({ includeInactive: true }).then(
      (teams) => ({
        value: Object.fromEntries(teams.map((team) => [team.id, team.name])),
        error: "",
      }),
      () => ({ value: {} as Record<number, string>, error: HOLDERS_ERROR })
    ),
    listCampuses(true).then(
      (campuses) => ({
        value: Object.fromEntries(
          campuses.map((campus) => [campus.id, campus.name])
        ),
        error: "",
      }),
      () => ({ value: {} as Record<number, string>, error: HOLDERS_ERROR })
    ),
  ]);

  const roles = rolesResult.value;
  const rolesError = rolesResult.error;
  const assignments = institutionResult.value;
  const teamHoldings = teamResult.value;
  const campusHoldings = campusResult.value;
  const holdersError =
    institutionResult.error || teamResult.error || campusResult.error;

  return (
    <FadeIn>
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold text-text-primary">Approver roles</h2>
          <p className="text-text-secondary">
            The approver positions a workflow step can name. Creating a role
            here is what makes it selectable on a chain; giving a role a holder
            — at institution, team or campus scope — is done on the Approvers
            page, and it is that holding (not an edit here) which decides a
            role&apos;s scope.
          </p>
        </div>
        <Link
          href="/dashboard/hr-admin/approvers"
          className={buttonVariants({ variant: "secondary" })}
        >
          Approvers
        </Link>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        {rolesError && (
          <div className="rounded-md bg-status-rejected-subtle py-12 text-center text-sm text-status-rejected">
            {rolesError}
          </div>
        )}
        {holdersError && (
          <Alert tone="error" className="mb-4">
            {holdersError} The holders column is hidden until the data loads
            again.
          </Alert>
        )}
        {!rolesError && (
          <RolesSection
            roles={roles}
            assignments={assignments}
            teamHoldings={teamHoldings}
            campusHoldings={campusHoldings}
            teamNameById={teamsResult.value}
            campusNameById={campusesResult.value}
          />
        )}
      </div>
    </div>
    </FadeIn>
  );
}

function groupByRole<T extends { role: number }>(assignments: T[]) {
  const byRole = new Map<number, T[]>();
  for (const assignment of assignments) {
    const list = byRole.get(assignment.role) ?? [];
    list.push(assignment);
    byRole.set(assignment.role, list);
  }
  return Object.fromEntries(byRole);
}

export default RolesPage;
