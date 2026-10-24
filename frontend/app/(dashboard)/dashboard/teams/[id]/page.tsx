import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { ArrowLeft, Pencil } from "lucide-react";

import { TeamLifecycleActions } from "@/components/hr/team-lifecycle-actions";
import { TeamMemberList } from "@/components/hr/team-member-list";
import { TeamMembersPanel } from "@/components/hr/team-members-panel";
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
import { listActiveApproverRoles } from "@/lib/approver-roles-client";
import type { Employee, EmployeeCategory } from "@/lib/employees";
import { listAllEmployees } from "@/lib/employees";
import { getCurrentUser } from "@/lib/auth";
<<<<<<< HEAD
import {
  canAccessTeams,
  isTeamsAdministrator,
} from "@/lib/nav/teams-nav";
=======
import { canAccessOrganisation, isOrganisationAdministrator } from "@/lib/nav/organisation-nav";
>>>>>>> features/team-base
import type { Team, WorkflowRef } from "@/lib/teams";
import { getTeam, listTeamWorkflows } from "@/lib/teams";
import { listMemberCandidates } from "@/lib/teams-client";
import {
<<<<<<< HEAD
  teamCategoryBadgeTone,
=======
  getTeam,
  listTeamMemberCandidates,
  listTeamWorkflows,
  teamCategoryBadgeClass,
>>>>>>> features/team-base
  teamCategoryLabel,
  teamStatusBadgeClass,
  teamStatusLabel,
} from "@/lib/teams";
import type { TeamMemberCandidate } from "@/lib/team-members";
import type { WideHolding } from "@/components/hr/wide-holding-panel";
import { WideHoldingPanel } from "@/components/hr/wide-holding-panel";
import { FadeIn } from "@/components/motion/FadeIn";
import { canConfigureChains, visibleTeamTabs } from "@/lib/team-access";

/**
 * The tabs a team is read through.
 *
 * One team answers four different questions — is it in force, who decides at
 * each step, who may be reached when a step has nobody, and whose leave it
 * routes — and stacking all four on one screen made the first answer the hard
 * one to find. Each is a page under the same URL, so the team stays one thing
 * and the question being asked is what the address says.
 *
 * Which of them a user sees is decided by `visibleTeamTabs`: staffing a step
 * and holding the roster are the team manager's writes, the team-wide
 * approvers are HR's, and showing a tab whose every action the server refuses
 * would be a screen of 403s.
 */
const TABS = [
  { value: "overview", label: "Overview" },
  { value: "steps", label: "Approval steps" },
  { value: "approvers", label: "Approvers" },
  { value: "members", label: "Members" },
] as const;

type TabValue = (typeof TABS)[number]["value"];

/**
 * The people a roster may add, read by whoever is looking.
 *
 * HR reads the employee directory's "unassigned, matching category, not a wide
 * approver for this team" filters. A team's manager may not reach the directory
 * at all, so they read the same list through the team's own member-candidates
 * route, scoped by the backend to the team they run. Both are the backend's
 * answer, never a subtraction here.
 */
async function loadMemberCandidates(
  team: Team,
  isAdministrator: boolean
): Promise<Employee[]> {
  try {
    if (isAdministrator) {
      return await listUnassignedEmployees(
        team.category as EmployeeCategory,
        team.id
      );
    }
    return await listMemberCandidates(team.id);
  } catch {
    return [];
  }
}

/**
 * The roles a team-wide holder may be given, read by whoever is looking.
 *
 * HR reads the whole role list. A manager may not reach the HR-only role
 * endpoint, so they read the read-only list a manager is allowed; writing roles
 * stays HR's either way.
 */
async function loadScopedRoles(
  isAdministrator: boolean
): Promise<ApproverRole[]> {
  try {
    return isAdministrator
      ? await listApproverRoles()
      : await listActiveApproverRoles();
  } catch {
    return [];
  }
}

/**
 * One team: what it is, what it routes, and who can act for it.
 *
 * The chain and its roster live here rather than on the list, because staffing
 * a step is a decision about one team and belongs next to that team's status —
 * a step staffed on an inactive team is not doing anything, and saying so in
 * the same view is the point.
 */
export default async function TeamPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ tab?: string }>;
}) {
  const { id } = await params;
  const { tab: tabParam } = await searchParams;
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (!canAccessTeams(user)) {
    redirect("/dashboard");
  }

  // Whether the viewer sees the HR-only controls on this team. A manager may
  // read and configure their team's chains and roster, but editing the team's
  // identity and retiring it stay HR's.
  const isAdministrator = isTeamsAdministrator(user);

  let team: Team;
  try {
    team = await getTeam(id);
  } catch {
    notFound();
  }

  // The tabs a user may open follow the handover: HR holds the team's wide
  // roles, the manager staffs its steps and roster. A tab the server would
  // refuse is not shown rather than opened into a wall of 403s.
  const allowedTabs = visibleTeamTabs(isAdministrator);
  const visibleTabs = TABS.filter((candidate) =>
    allowedTabs.includes(candidate.value)
  );

  const tab = visibleTabs.some((candidate) => candidate.value === tabParam)
    ? (tabParam as TabValue)
    : "overview";

<<<<<<< HEAD
  const [employeesResult, candidatesResult, workflowsResult, holdersResult, rolesResult, institutionHoldingsResult, campusHoldingsResult] =
    await Promise.all([
      // A team-wide holder must be the same category as the team, so the
      // Approvers tab's feed is the whole directory's matching half, read as a
      // server filter rather than by subtracting here. A holder need not be a
      // member of the team. HR-only: a manager cannot read the directory, so for
      // them this is empty and the Approvers tab is read-only.
      isAdministrator
        ? listAllEmployees(team.category as EmployeeCategory).catch(
            () => [] as Employee[]
          )
        : Promise.resolve([] as Employee[]),
      // The roster's candidates match this team: only unassigned employees of
      // the team's own category, never a wide approver (who serves steps from
      // the Approvers tab). Read through the team's own route, which a manager
      // may reach; HR reads the same list from the directory's filters.
      loadMemberCandidates(team, isAdministrator),
      listTeamWorkflows(id).catch(() => [] as WorkflowRef[]),
      // Every team's holdings, so this team's own can be filtered out here and
      // the whole set still fed to the panel as the one-wide-approver pool.
=======
  // A team-wide holder must be the same category as the team, so the
  // Approvers tab's feed is the whole directory's matching half, read as a
  // server filter rather than by subtracting here. A holder need not be a
  // member of the team.
  //
  // The member-candidate feed is the manager's — its endpoint refuses HR — so
  // it is read only for a manager. The chain list is shared: HR reads it to
  // decide which one routes.
  const canConfigure = canConfigureChains(isAdministrator);
  const [candidatesResult, workflowsResult] = await Promise.all([
    canConfigure
      ? listTeamMemberCandidates(id).catch((err: unknown) => {
          // Swallowed to a bare `[]` is how a failing read became a picker
          // that said "no employees" with nothing to trace it to. The page
          // still renders, but the reason is no longer invisible.
          console.error(
            `member-candidates failed for team ${id}:`,
            err instanceof Error ? err.message : err
          );
          return [] as TeamMemberCandidate[];
        })
      : Promise.resolve([] as TeamMemberCandidate[]),
    listTeamWorkflows(id).catch(() => [] as WorkflowRef[]),
  ]);

  const candidates = candidatesResult;
  const workflows = workflowsResult;

  let employees: Employee[] = [];
  let holdings: WideHolding[] = [];
  let wideHolderUserIds: number[] = [];
  let roles: ApproverRole[] = [];

  if (isAdministrator) {
    const [
      employeesResult,
      holdersResult,
      rolesResult,
      institutionHoldingsResult,
      campusHoldingsResult,
    ] = await Promise.all([
      listAllEmployees(team.category as EmployeeCategory).catch(
        () => [] as Employee[]
      ),
>>>>>>> features/team-base
      listTeamRoleAssignments().catch(() => [] as TeamRoleAssignment[]),
      loadScopedRoles(isAdministrator),
      listRoleAssignments().catch(() => [] as RoleAssignment[]),
      listCampusRoleAssignments().catch(() => [] as CampusRoleAssignment[]),
    ]);

    employees = employeesResult;
    const teamHoldings = holdersResult.filter(
      (assignment) => assignment.team === team.id
    );
    holdings = teamHoldings.map((assignment) => ({
      id: assignment.id,
      role: assignment.role,
      user: assignment.user,
      user_name: assignment.user_name,
      role_label: assignment.role_label,
      is_team_manager: assignment.is_team_manager,
    }));
    wideHolderUserIds = Array.from(
      new Set(
        [
          ...institutionHoldingsResult,
          ...holdersResult,
          ...campusHoldingsResult,
        ].map((assignment) => assignment.user)
      )
    );
    roles = rolesResult.filter(
      (role) => role.is_active && !role.is_institution_wide
    );
  }

  return (
    <FadeIn>
    <div className="space-y-6">
      <div>
        <Link
          href="/dashboard/teams"
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
                className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${teamCategoryBadgeClass(
                  team.category
                )}`}
              >
                {teamCategoryLabel(team.category)}
              </span>
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
                team.campus_name && `Campus: ${team.campus_name}`,
              ]
                .filter(Boolean)
                .join(" · ")}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Link
              href={`/dashboard/teams/${team.id}/workflows`}
              className="inline-flex items-center gap-2 rounded-md border border-border-default bg-button-secondary px-4 py-2 text-sm font-medium text-text-secondary hover:bg-button-secondary-hover"
            >
              Workflows
            </Link>
            {isAdministrator && (
              <Link
                href={`/dashboard/teams/${team.id}/edit`}
                className="inline-flex items-center gap-2 rounded-md border border-border-default bg-button-secondary px-4 py-2 text-sm font-medium text-text-secondary hover:bg-button-secondary-hover"
              >
                <Pencil className="h-4 w-4" />
                Edit team
              </Link>
            )}
          </div>
        </div>
      </div>

      <div
        className="flex flex-wrap items-center gap-2"
        role="navigation"
        aria-label="Team sections"
      >
        {visibleTabs.map((candidate) => (
          <Link
            key={candidate.value}
            href={
              candidate.value === "overview"
                ? `/dashboard/teams/${team.id}`
                : `/dashboard/teams/${team.id}?tab=${candidate.value}`
            }
            aria-current={tab === candidate.value ? "page" : undefined}
            className={`rounded-full px-3 py-1 text-xs font-medium ${
              tab === candidate.value
                ? "bg-brand-primary text-button-primary-foreground"
                : "border border-border-default bg-surface-card text-text-secondary hover:bg-button-secondary-hover"
            }`}
          >
            {candidate.label}
          </Link>
        ))}
      </div>

      {tab === "overview" && (
        <>
          <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
            <div className="grid gap-4 md:grid-cols-3">
              <div>
                <span className="text-xs uppercase tracking-wide text-text-muted">
                  Category
                </span>
                <p className="text-sm font-medium text-text-primary">
                  {teamCategoryLabel(team.category)}
                </p>
                <p className="mt-1 text-xs text-text-muted">
                  {team.category === "academic"
                    ? "Sits at a campus, and its stages may resolve to a campus-wide holder."
                    : "Institution-wide, and the only kind whose stages may resolve to an institution-wide holder."}
                </p>
              </div>
              <div>
                <span className="text-xs uppercase tracking-wide text-text-muted">
                  Chains
                </span>
                <p className="text-sm font-medium text-text-primary">
                  {workflows.length === 0
                    ? "None"
                    : `${workflows.length} chain${workflows.length === 1 ? "" : "s"}`}
                </p>
                <p className="mt-1 text-xs text-text-muted">
                  {workflows.length === 0
                    ? "This team owns no chains yet."
                    : "All of them route at once, each carrying its own members."}
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
            </div>

            {isAdministrator && (
              <div className="mt-4 border-t border-border-default pt-4">
                <TeamLifecycleActions team={team} />
              </div>
            )}
          </div>

          <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-lg font-semibold text-text-primary">
                Chains this team owns
              </h3>
              {canConfigureChains(isAdministrator) && (
                <Link
                  href={`/dashboard/teams/${team.id}/workflows/new`}
                  className="text-sm font-medium text-brand-primary hover:text-brand-primary-hover"
                >
                  New workflow
                </Link>
              )}
            </div>
            {workflows.length === 0 ? (
              <p className="text-sm text-text-muted">
                None yet. A team routes nothing until it owns a chain, and the
                chain is built on the team&apos;s own page.
              </p>
            ) : (
              <ul className="divide-y divide-border-default">
                {workflows.map((workflow) => (
                  <li
                    key={workflow.id}
                    className="flex flex-wrap items-center justify-between gap-2 py-2"
                  >
                    <div>
                      <Link
                        href={`/dashboard/teams/${team.id}/workflows/${workflow.id}`}
                        className="font-medium text-brand-primary hover:text-brand-primary-hover"
                      >
                        {workflow.name}
                      </Link>
                      <p className="text-xs text-text-muted">
                        {workflow.section_count} step
                        {workflow.section_count === 1 ? "" : "s"}
                      </p>
                    </div>
                    <span
                      className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${
                        workflow.is_active
                          ? "bg-brand-secondary-subtle text-brand-secondary"
                          : "bg-surface-muted text-text-muted"
                      }`}
                    >
                      {workflow.is_active ? "In force" : "Not in force"}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}

      {tab === "steps" && (
        <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
          <h3 className="text-lg font-semibold text-text-primary">
            Who decides at each step
          </h3>
          <p className="mt-1 text-sm text-text-secondary">
            The chain in force, and the one person who acts at each of its
            steps. A step with nobody on it stops the applications that would
            have reached it, naming the step so it can be filled.
          </p>
          <div className="mt-4">
            <TeamMemberList team={team} />
          </div>
        </div>
      )}

      {tab === "approvers" && (
        <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
          <h3 className="text-lg font-semibold text-text-primary">
            Team-wide approvers
          </h3>
          <p className="mt-1 text-sm text-text-secondary">
            One holder per role for this whole team. Every step falls back to
            these when nobody is appointed to it — and to a campus-wide holder
            at this team&apos;s campus next, before anything else.
          </p>
          {roles.length === 0 ? (
            <p className="mt-3 text-sm text-text-muted">
              No active scoped roles to hold here yet. An institution-wide role
              is held on the{" "}
              <Link
                href="/dashboard/hr-admin/approvers"
                className="font-medium text-brand-primary hover:text-brand-primary-hover"
              >
                Approvers
              </Link>{" "}
              page, and reaches only administration teams.
            </p>
          ) : (
            <div className="mt-4">
              <WideHoldingPanel
                scope="team"
                roles={roles}
                scopeId={team.id}
                requiredCategory={team.category as EmployeeCategory}
                employees={employees}
                holdings={holdings}
                excludedUserIds={wideHolderUserIds}
                canManage={isAdministrator}
              />
            </div>
          )}
        </div>
      )}

      {tab === "members" && (
        <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
          <h3 className="text-lg font-semibold text-text-primary">
            Team members
          </h3>
          <p className="mt-1 text-sm text-text-secondary">
            Add and remove the people whose submissions this team&apos;s chains
            decide. Being a team member is what makes someone selectable as a
            normal member of this team&apos;s workflows — it places nobody on a
            workflow by itself, and removal is refused while someone still ties
            to the team.
          </p>
          <div className="mt-4">
            <TeamMembersPanel team={team} candidates={candidates} />
          </div>
        </div>
      )}
    </div>
    </FadeIn>
  );
}
