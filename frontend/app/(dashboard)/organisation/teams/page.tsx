import Link from "next/link";
import { redirect } from "next/navigation";

import { CampusQuickAdd } from "@/components/hr/campus-form";
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
import { FadeIn } from "@/components/motion/FadeIn";

const TEAMS_ERROR = "Unable to load teams. Please try again.";
const CAMPUSES_ERROR = "Unable to load campuses. Please try again.";
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
  const isHr = user.role === "hr";
  if (!isHr && user.manages_teams !== true) {
    redirect("/");
  }
  if (!isHr && user.manages_teams === true) {
    // Managers see only their team. Landing on the list that contains a single
    // owned team is convenient; redirect straight to it.
    const teams = await listTeams().catch(() => [] as Team[]);
    if (teams.length === 1) {
      redirect(`/organisation/teams/${teams[0].id}`);
    }
  }

  const { retired } = await searchParams;
  const showRetired = retired === "1";

  // The create overlay needs its option set on the page, so it is read here
  // rather than on open: the campuses an academic team may sit at, the
  // team-scoped approver roles its manager may hold, the employees who may be
  // that manager, and every current wide holder — a person holds only one wide
  // approver role, so those are excluded from the manager picker.
  const [
    teamsResult,
    campusesResult,
    rolesResult,
    employeesResult,
    institutionHoldingsResult,
    teamHoldingsResult,
    campusHoldingsResult,
  ] = await Promise.all([
    listTeams({ includeInactive: showRetired }).then(
      (value) => ({ value, error: "" }),
      () => ({ value: [] as Team[], error: TEAMS_ERROR })
    ),
    listCampuses().then(
      (value) => ({ value, error: "" }),
      () => ({ value: [] as Campus[], error: CAMPUSES_ERROR })
    ),
    listApproverRoles().then(
      (value) => ({ value, error: "" }),
      () => ({ value: [] as ApproverRole[], error: ROLES_ERROR })
    ),
    listAllEmployees().catch(() => [] as Employee[]),
    listRoleAssignments().catch(() => [] as RoleAssignment[]),
    listTeamRoleAssignments().catch(() => [] as TeamRoleAssignment[]),
    listCampusRoleAssignments().catch(() => [] as CampusRoleAssignment[]),
  ]);

  // The manager picker offers team-scoped roles only: an institution-wide role
  // is held outside any one team, so it cannot be the role a manager holds.
  const managerRoles = rolesResult.value.filter(
    (role) => role.is_active && !role.is_institution_wide
  );

  const wideHolderUserIds = Array.from(
    new Set(
      [
        ...institutionHoldingsResult,
        ...teamHoldingsResult,
        ...campusHoldingsResult,
      ].map((assignment) => assignment.user)
    )
  );

  const filters = [
    { label: "In force and draft", href: "/organisation/teams", current: !showRetired },
    { label: "Including retired", href: "/organisation/teams?retired=1", current: showRetired },
  ];

  return (
    <FadeIn>
      <div className="space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-text-primary">Teams</h2>
          <p className="text-text-secondary">
            The routing unit: an employee belongs to a team, and that
            team&apos;s chain decides who approves their application. A team is
            either academic — sitting at a campus — or administration-wide, and
            only a team that is in force routes anything.
          </p>
        </div>

        <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
          <TeamsSection
            teams={teamsResult.value}
            campuses={campusesResult.value}
            roles={managerRoles}
            rolesError={rolesResult.error}
            employees={employeesResult}
            wideHolderUserIds={wideHolderUserIds}
            error={teamsResult.error}
            filters={filters}
            canCreate={isHr}
          />
        </div>

        {isHr && (
          <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-lg font-semibold text-text-primary">Campuses</h3>
              <Link
                href="/organisation/campuses"
                className="text-sm font-medium text-brand-primary hover:text-brand-primary-hover"
              >
                Manage campuses
              </Link>
            </div>
            {campusesResult.error ? (
              <p className="text-sm text-status-rejected">{campusesResult.error}</p>
            ) : (
              <CampusQuickAdd campuses={campusesResult.value} />
            )}
          </div>
        )}
      </div>
    </FadeIn>
  );
}

export default TeamsPage;
