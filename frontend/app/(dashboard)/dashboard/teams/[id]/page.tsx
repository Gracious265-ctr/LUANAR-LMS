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
import type { Employee, EmployeeCategory } from "@/lib/employees";
import { listAllEmployees, listUnassignedEmployees } from "@/lib/employees";
import { getCurrentUser } from "@/lib/auth";
import type { Team, WorkflowRef } from "@/lib/teams";
import {
  getTeam,
  listTeamWorkflows,
  teamCategoryBadgeClass,
  teamCategoryLabel,
  teamStatusBadgeClass,
  teamStatusLabel,
} from "@/lib/teams";
import type { WideHolding } from "@/components/hr/wide-holding-panel";
import { WideHoldingPanel } from "@/components/hr/wide-holding-panel";
import { FadeIn } from "@/components/motion/FadeIn";

/**
 * The tabs a team is read through.
 *
 * One team answers four different questions — is it in force, who decides at
 * each step, who may be reached when a step has nobody, and whose leave it
 * routes — and stacking all four on one screen made the first answer the hard
 * one to find. Each is a page under the same URL, so the team stays one thing
 * and the question being asked is what the address says.
 */
const TABS = [
  { value: "overview", label: "Overview" },
  { value: "steps", label: "Approval steps" },
  { value: "approvers", label: "Approvers" },
  { value: "members", label: "Members" },
] as const;

type TabValue = (typeof TABS)[number]["value"];

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
  if (user.role !== "hr") {
    redirect("/dashboard");
  }

  let team: Team;
  try {
    team = await getTeam(id);
  } catch {
    notFound();
  }

  const tab = TABS.some((candidate) => candidate.value === tabParam)
    ? (tabParam as TabValue)
    : "overview";

  const [employeesResult, candidatesResult, workflowsResult, holdersResult, rolesResult, institutionHoldingsResult, campusHoldingsResult] =
    await Promise.all([
      // A team-wide holder must be the same category as the team, so the
      // Approvers tab's feed is the whole directory's matching half, read as a
      // server filter rather than by subtracting here. A holder need not be a
      // member of the team.
      listAllEmployees(team.category as EmployeeCategory).catch(
        () => [] as Employee[]
      ),
      // The roster's candidates match this team: only unassigned employees of
      // the team's own category, never a wide approver (who serves steps from
      // the Approvers tab). Filtered by the backend, not by subtraction here.
      listUnassignedEmployees(
        team.category as EmployeeCategory,
        team.id
      ).catch(() => [] as Employee[]),
      listTeamWorkflows(id).catch(() => [] as WorkflowRef[]),
      // Every team's holdings, so this team's own can be filtered out here and
      // the whole set still fed to the panel as the one-wide-approver pool.
      listTeamRoleAssignments().catch(() => [] as TeamRoleAssignment[]),
      listApproverRoles().catch(() => [] as ApproverRole[]),
      listRoleAssignments().catch(() => [] as RoleAssignment[]),
      listCampusRoleAssignments().catch(() => [] as CampusRoleAssignment[]),
    ]);

  const candidates = candidatesResult;
  const workflows = workflowsResult;
  const holdings: WideHolding[] = holdersResult
    .filter((assignment) => assignment.team === team.id)
    .map((assignment) => ({
      id: assignment.id,
      role: assignment.role,
      user: assignment.user,
      user_name: assignment.user_name,
      role_label: assignment.role_label,
    }));
  // A person holds one wide approver role, so everyone who already holds one
  // anywhere (institution, any team, any campus) is offered nowhere.
  const wideHolderUserIds = Array.from(
    new Set(
      [
        ...institutionHoldingsResult,
        ...holdersResult,
        ...campusHoldingsResult,
      ].map((assignment) => assignment.user)
    )
  );
  const roles = rolesResult.filter(
    (role) => role.is_active && !role.is_institution_wide
  );
  const employees = employeesResult;

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
            <Link
              href={`/dashboard/teams/${team.id}/edit`}
              className="inline-flex items-center gap-2 rounded-md border border-border-default bg-button-secondary px-4 py-2 text-sm font-medium text-text-secondary hover:bg-button-secondary-hover"
            >
              <Pencil className="h-4 w-4" />
              Edit team
            </Link>
          </div>
        </div>
      </div>

      <div
        className="flex flex-wrap items-center gap-2"
        role="navigation"
        aria-label="Team sections"
      >
        {TABS.map((candidate) => (
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
                  Chain in force
                </span>
                <p className="text-sm font-medium text-text-primary">
                  {team.workflow_name || "None"}
                </p>
                <p className="mt-1 text-xs text-text-muted">
                  {workflows.length === 0
                    ? "This team owns no chains yet."
                    : `Owns ${workflows.length} chain${workflows.length === 1 ? "" : "s"}; routes one.`}
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

            <div className="mt-4 border-t border-border-default pt-4">
              <TeamLifecycleActions team={team} />
            </div>
          </div>

          <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-lg font-semibold text-text-primary">
                Chains this team owns
              </h3>
              <Link
                href={`/dashboard/teams/${team.id}/workflows/new`}
                className="text-sm font-medium text-brand-primary hover:text-brand-primary-hover"
              >
                New workflow
              </Link>
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
                        workflow.is_routing
                          ? "bg-brand-secondary-subtle text-brand-secondary"
                          : "bg-surface-muted text-text-muted"
                      }`}
                    >
                      {workflow.is_routing ? "Routing" : "Not routing"}
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
            steps. A step with nobody on it blocks activation — and blocks
            submission, for the applications that would have reached it.
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
