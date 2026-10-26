import Link from "next/link";
import { redirect } from "next/navigation";

import { CampusQuickAdd } from "@/components/hr/campus-form";
import { TeamsSection } from "@/components/hr/TeamsSection";
import type { ApproverRole } from "@/lib/approver-roles";
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
  if (!canAccessTeams(user)) {
    redirect("/dashboard");
  }

  const isAdministrator = isTeamsAdministrator(user);

  const { retired } = await searchParams;
  const showRetired = retired === "1";

  // The create overlay needs its option set on the page, so it is read here
  // rather than on open: the campuses an academic team may sit at, the approver
  // roles its chain picks one of per step, the employees its manager may be
  // chosen from, and every current wide holder — a person holds only one wide
  // approver role, so those are excluded from the manager picker.
  //
  // A manager creates no teams (that is an HR decision), so for them none of it
  // is read: every one of these endpoints is HR-only, and asking would only fill
  // the page with errors about a form they never open.
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
    isAdministrator
      ? listCampuses().then(
          (value) => ({ value, error: "" }),
          () => ({ value: [] as Campus[], error: CAMPUSES_ERROR })
        )
      : Promise.resolve({ value: [] as Campus[], error: "" }),
    isAdministrator
      ? listApproverRoles().then(
          (value) => ({ value, error: "" }),
          () => ({ value: [] as ApproverRole[], error: ROLES_ERROR })
        )
      : Promise.resolve({ value: [] as ApproverRole[], error: "" }),
    isAdministrator
      ? listAllEmployees().catch(() => [] as Employee[])
      : Promise.resolve([] as Employee[]),
    isAdministrator ? listRoleAssignments().catch(() => []) : Promise.resolve([]),
    isAdministrator
      ? listTeamRoleAssignments().catch(() => [])
      : Promise.resolve([]),
    isAdministrator
      ? listCampusRoleAssignments().catch(() => [])
      : Promise.resolve([]),
  ]);

  const wideHolderUserIds = Array.from(
    new Set(
      [
        ...institutionHoldingsResult,
        ...teamHoldingsResult,
        ...campusHoldingsResult,
      ].map((assignment) => assignment.user)
    )
  );

  // A manager oversees a handful of teams at most, and often exactly one. A
  // list of one is a click that answers nothing, so they land straight on the
  // team they came to configure. HR and superusers keep the list: it is their
  // roster of every team, and the point of the page for them.
  if (
    !isAdministrator &&
    !teamsResult.error &&
    teamsResult.value.length === 1
  ) {
    redirect(`/dashboard/teams/${teamsResult.value[0].id}`);
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
            campuses={campusesResult.value}
            roles={rolesResult.value}
            rolesError={rolesResult.error}
            employees={employeesResult}
            wideHolderUserIds={wideHolderUserIds}
            error={teamsResult.error}
            filters={filters}
            canCreate={isAdministrator}
          />
        </div>

        {isAdministrator && (
          <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-lg font-semibold text-text-primary">
                Campuses
              </h3>
              <Link
                href="/dashboard/hr-admin/campuses"
                className="text-sm font-medium text-brand-primary hover:text-brand-primary-hover"
              >
                Manage campuses
              </Link>
            </div>
            {campusesResult.error ? (
              <p className="text-sm text-status-rejected">
                {campusesResult.error}
              </p>
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
