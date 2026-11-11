import { redirect } from "next/navigation";

import { TeamsSection } from "@/components/hr/TeamsSection";
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
import type { Campus, Team } from "@/lib/teams";
import { listCampuses, listTeams } from "@/lib/teams";
import { getCurrentUser } from "@/lib/auth";
import {
  canAccessTeams,
  isTeamsAdministrator,
} from "@/lib/nav/teams-nav";
import { FadeIn } from "@/components/motion/FadeIn";

const TEAMS_ERROR = "Unable to load teams. Please try again.";
const ROLES_ERROR = "Unable to load approver roles. Please try again.";

/**
 * The teams list, with create in an overlay.
 *
 * The retired/in-force toggle lives in `?retired` so it survives a refresh and
 * can be linked to, and `useOverlayParam` keeps it when the overlay opens on top
 * of it.
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
  if (!canAccessTeams(user)) {
    redirect("/dashboard");
  }

  const isAdministrator = isTeamsAdministrator(user);

  const { retired } = await searchParams;
  const showRetired = retired === "1";

  // The create overlay needs its option set on the page, so it is read here
  // rather than on open: the campuses an academic team may sit at, the approver
  // roles its chain picks one of per step, and the employees its manager may be
  // chosen from. Whose wide holdings are already spoken for is read too,
  // because a person holds one wide approver role: naming a manager who already
  // has one means they run the team without a second holding, while everybody
  // else is given the team-wide role the create form asks for.
  //
  // A manager creates no teams (that is an HR decision), so for them none of it
  // is read: every one of these endpoints is HR-only, and asking would only fill
  // the page with errors about a form they never open.
  const [
    teamsResult,
    campuses,
    rolesResult,
    employeesResult,
    institutionHoldings,
    teamHoldings,
    campusHoldings,
  ] = await Promise.all([
      listTeams({ includeInactive: showRetired }).then(
        (value) => ({ value, error: "" }),
        () => ({ value: [] as Team[], error: TEAMS_ERROR })
      ),
      isAdministrator
        ? listCampuses().catch(() => [] as Campus[])
        : Promise.resolve([] as Campus[]),
      isAdministrator
        ? listApproverRoles().then(
            (value) => ({ value, error: "" }),
            () => ({ value: [] as ApproverRole[], error: ROLES_ERROR })
          )
        : Promise.resolve({ value: [] as ApproverRole[], error: "" }),
      isAdministrator
        ? listAllEmployees().catch(() => [] as Employee[])
        : Promise.resolve([] as Employee[]),
      isAdministrator
        ? listRoleAssignments().catch(() => [] as RoleAssignment[])
        : Promise.resolve([] as RoleAssignment[]),
      isAdministrator
        ? listTeamRoleAssignments().catch(() => [] as TeamRoleAssignment[])
        : Promise.resolve([] as TeamRoleAssignment[]),
      isAdministrator
        ? listCampusRoleAssignments().catch(
            () => [] as CampusRoleAssignment[]
          )
        : Promise.resolve([] as CampusRoleAssignment[]),
    ]);

  const wideHolderUserIds = Array.from(
    new Set(
      [
        ...institutionHoldings,
        ...teamHoldings,
        ...campusHoldings,
      ].map((assignment) => assignment.user)
    )
  );

  // A manager oversees a handful of teams at most, and often exactly one. A
  // list of one is a click that answers nothing, so they land straight on the
  // team they came to configure. HR and superusers keep the list: it is their
  // roster of every team, and the point of the page for them.
  //
  // An empty roster is the one thing a manager cannot act on from the team
  // page — every other tab describes a team that has nobody to route — so the
  // landing goes straight to the page that fills it.
  if (
    !isAdministrator &&
    !teamsResult.error &&
    teamsResult.value.length === 1
  ) {
    const [team] = teamsResult.value;
    redirect(
      team.roster_count === 0
        ? `/dashboard/teams/${team.id}/members/add`
        : `/dashboard/teams/${team.id}`
    );
  }

  const filters = [
    { label: "In force and draft", href: "/dashboard/teams", current: !showRetired },
    { label: "Including retired", href: "/dashboard/teams?retired=1", current: showRetired },
  ];

  return (
    <FadeIn>
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-text-primary">Teams</h2>
          <p className="text-text-secondary">The routing unit: a team&apos;s chain decides who approves its applications.</p>
        </div>

        <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
          <TeamsSection
            teams={teamsResult.value}
            campuses={campuses}
            roles={rolesResult.value}
            rolesError={rolesResult.error}
            employees={employeesResult}
            wideHolderUserIds={wideHolderUserIds}
            error={teamsResult.error}
            filters={filters}
            canCreate={isAdministrator}
          />
        </div>
      </div>
    </FadeIn>
  );
}

export default TeamsPage;
