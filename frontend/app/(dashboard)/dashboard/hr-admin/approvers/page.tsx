import Link from "next/link";
import { redirect } from "next/navigation";

import type { ApproverRole, CampusRoleAssignment, RoleAssignment, TeamRoleAssignment } from "@/lib/approver-roles";
import {
  listApproverRoles,
  listCampusRoleAssignments,
  listRoleAssignments,
  listTeamRoleAssignments,
} from "@/lib/approver-roles";
import type { Campus, Team } from "@/lib/teams";
import { listCampuses, listTeams } from "@/lib/teams";
import { getCurrentUser } from "@/lib/auth";
import type { Employee, EmployeeCategory } from "@/lib/employees";
import { listAllEmployees } from "@/lib/employees";
import {
  WideHoldingPanel,
  type WideHolding,
  type WideScope,
} from "@/components/hr/wide-holding-panel";
import { ScopeFilterSelect } from "@/components/hr/scope-filter-select";

const ROLES_ERROR = "Unable to load approver roles.";
const HOLDERS_ERROR = "Unable to load the current holders.";
const SCOPE_ERROR = "Unable to load the teams and campuses holders can be scoped to.";

type ScopeFilter = "all" | WideScope;

const SCOPE_FILTERS: { value: ScopeFilter; label: string }[] = [
  { value: "all", label: "All scopes" },
  { value: "institution", label: "Institution-wide" },
  { value: "team", label: "Team-wide" },
  { value: "campus", label: "Campus-wide" },
];

/**
 * Who approves what, at every scope.
 *
 * Three screens used to answer three different questions — an institution-wide
 * holder on the roles page, a team holder on the team, a campus holder
 * nowhere — and the person looking for "who holds the DVC role" had to know
 * which of the three to open. This is the one screen that answers it: every
 * role, every scope, every holder, in one list, with the form that changes
 * them.
 *
 * Institution-wide is still the only scope an administration team's stages may
 * resolve to, and campus-wide the only extra one an academic team's may — but
 * that is a rule about resolution, not about where a holding is written, so
 * all three are configured here the same way.
 */
export default async function ApproversPage({
  searchParams,
}: {
  searchParams: Promise<{ scope?: string; team?: string; campus?: string }>;
}) {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (user.role !== "hr") {
    redirect("/dashboard");
  }

  const params = await searchParams;
  const scope = (params.scope as ScopeFilter) || "all";
  const teamFilter = params.team ? Number(params.team) : null;
  const campusFilter = params.campus ? Number(params.campus) : null;

  const [rolesResult, holdersResult, employeesResult, teamsResult, campusesResult] =
    await Promise.all([
      listApproverRoles(true).then(
        (value) => ({ value, error: "" }),
        () => ({ value: [] as ApproverRole[], error: ROLES_ERROR })
      ),
      Promise.all([
        listRoleAssignments(),
        listTeamRoleAssignments(),
        listCampusRoleAssignments(),
      ]).then(
        ([institution, team, campus]) => ({ value: { institution, team, campus }, error: "" }),
        () => ({
          value: {
            institution: [] as RoleAssignment[],
            team: [] as TeamRoleAssignment[],
            campus: [] as CampusRoleAssignment[],
          },
          error: HOLDERS_ERROR,
        })
      ),
      listAllEmployees().then(
        (value) => ({ value, error: "" }),
        () => ({
          value: [] as Employee[],
          error: "Unable to load employees, so holders cannot be added.",
        })
      ),
      listTeams({ includeInactive: true }).then(
        (value) => ({ value, error: "" }),
        () => ({ value: [] as Team[], error: SCOPE_ERROR })
      ),
      listCampuses(true).then(
        (value) => ({ value, error: "" }),
        () => ({ value: [] as Campus[], error: SCOPE_ERROR })
      ),
    ]);

  const roles = rolesResult.value;
  const holders = holdersResult.value;
  const employees = employeesResult.value;
  const teams = teamsResult.value;
  const campuses = campusesResult.value;

  // A team option carries its category so the person list follows the chosen
  // team's half of the institution; a campus is always academic, because only
  // academic teams sit at one.
  const teamOptions = teams.map((team) => ({
    id: team.id,
    name: team.name,
    category: team.category as EmployeeCategory,
  }));
  const campusOptions = campuses.map((campus) => ({
    id: campus.id,
    name: campus.name,
    category: "academic" as const,
  }));

  const institutionHoldings = holders.institution.map(toHolding);
  const teamHoldings = holders.team
    .filter((assignment) => teamFilter === null || assignment.team === teamFilter)
    .map(toHolding);
  const campusHoldings = holders.campus
    .filter(
      (assignment) => campusFilter === null || assignment.campus === campusFilter
    )
    .map(toHolding);

  // A person holds one wide approver role, so everybody who already holds one
  // anywhere (read unfiltered, not just the scope shown) is offered nowhere.
  const wideHolderUserIds = Array.from(
    new Set(
      [...holders.institution, ...holders.team, ...holders.campus].map(
        (assignment) => assignment.user
      )
    )
  );

  const activeRoles = roles.filter((role) => role.is_active);
  // A team or campus holding may only use a scoped role; institution-wide
  // roles are written at the institution scope alone.
  const scopedRoles = activeRoles.filter((role) => !role.is_institution_wide);
  // A role held wide at a team or a campus cannot be held institution-wide at
  // the same time, and a saving it at institution scope would be refused — so
  // the institution panel only offers roles that are *already* institution-wide
  // or not wide at any scope yet. Saving one of those is what makes it a wide
  // role.
  const scopedHeldRoleIds = new Set(
    [...holders.team, ...holders.campus].map((assignment) => assignment.role)
  );
  const institutionRoles = activeRoles.filter(
    (role) => role.is_institution_wide || !scopedHeldRoleIds.has(role.id)
  );
  const scopeChips = SCOPE_FILTERS.map((filter) => {
    const query = new URLSearchParams();
    query.set("scope", filter.value);
    if (filter.value === "team" && teamFilter) query.set("team", String(teamFilter));
    if (filter.value === "campus" && campusFilter)
      query.set("campus", String(campusFilter));
    return {
      ...filter,
      href: `/dashboard/hr-admin/approvers?${query.toString()}`,
      current: scope === filter.value,
    };
  });

  const showInstitution = scope === "all" || scope === "institution";
  const showTeam = scope === "all" || scope === "team";
  const showCampus = scope === "all" || scope === "campus";

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-text-primary">Approvers</h2>
        <p className="text-text-secondary">
          Every role, every scope, every holder. A stage resolves its approver
          from the person appointed to it first, then from a team-wide holding,
          then from a campus-wide one, and only an administration team may fall
          back to an institution-wide holder — so where a role is held decides
          which teams it reaches.
        </p>
      </div>

      <div
        className="flex flex-wrap items-center gap-2"
        role="group"
        aria-label="Filter approver holdings by scope"
      >
        {scopeChips.map((chip) => (
          <Link
            key={chip.value}
            href={chip.href}
            aria-current={chip.current ? "page" : undefined}
            className={`rounded-full px-3 py-1 text-xs font-medium ${
              chip.current
                ? "bg-brand-primary text-button-primary-foreground"
                : "border border-border-default bg-surface-card text-text-secondary hover:bg-button-secondary-hover"
            }`}
          >
            {chip.label}
          </Link>
        ))}
      </div>

      {showTeam && (
        <ScopeFilterSelect
          id="team-scope"
          label="Team:"
          value={teamFilter}
          options={teamOptions}
          param="team"
          scope={scope}
          clearLabel="Clear team"
        />
      )}

      {showCampus && (
        <ScopeFilterSelect
          id="campus-scope"
          label="Campus:"
          value={campusFilter}
          options={campusOptions}
          param="campus"
          scope={scope}
          clearLabel="Clear campus"
        />
      )}

      {rolesResult.error && (
        <p className="rounded-md bg-status-rejected-subtle p-3 text-sm text-status-rejected">
          {rolesResult.error}
        </p>
      )}
      {holdersResult.error && (
        <p className="rounded-md bg-status-rejected-subtle p-3 text-sm text-status-rejected">
          {holdersResult.error}
        </p>
      )}
      {employeesResult.error && (
        <p className="rounded-md bg-status-rejected-subtle p-3 text-sm text-status-rejected">
          {employeesResult.error}
        </p>
      )}
      {teamsResult.error && (
        <p className="rounded-md bg-status-rejected-subtle p-3 text-sm text-status-rejected">
          {teamsResult.error}
        </p>
      )}

      {activeRoles.length === 0 ? (
        <div className="rounded-xl border border-border-default bg-surface-card p-6 text-center shadow-subtle">
          <p className="text-base font-medium text-text-primary">
            No active approver roles
          </p>
          <p className="mt-1 text-sm text-text-muted">
            Create a role first — a holding is always a person holding a role
            somewhere, so there is nothing to hold until the role exists.
          </p>
          <Link
            href="/dashboard/hr-admin/roles/new"
            className="mt-3 inline-block rounded-md bg-button-primary px-4 py-2 text-sm font-medium text-button-primary-foreground hover:bg-button-primary-hover"
          >
            New role
          </Link>
        </div>
      ) : (
        <section
          className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle"
          aria-label="Wide approver holdings"
        >
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {showInstitution && (
              <WideHoldingPanel
                key="institution"
                scope="institution"
                roles={institutionRoles}
                employees={employees}
                holdings={institutionHoldings}
                excludedUserIds={wideHolderUserIds}
              />
            )}
            {showTeam && (
              <WideHoldingPanel
                key="team"
                scope="team"
                roles={scopedRoles}
                scopeOptions={teamOptions}
                employees={employees}
                holdings={teamHoldings}
                excludedUserIds={wideHolderUserIds}
              />
            )}
            {showCampus && (
              <WideHoldingPanel
                key="campus"
                scope="campus"
                roles={scopedRoles}
                scopeOptions={campusOptions}
                employees={employees}
                holdings={campusHoldings}
                excludedUserIds={wideHolderUserIds}
              />
            )}
          </div>
          <p className="mt-3 text-xs text-text-muted">
            Saving a holder replaces that role&apos;s current holder at the
            chosen scope — and a person holds only one wide approver role, so a
            saved holder disappears from the other sections. Assigning a role
            its first institution-wide holder is also what makes the role
            institution-wide.
          </p>
        </section>
      )}

    </div>
  );
}

function toHolding(
  assignment:
    | RoleAssignment
    | TeamRoleAssignment
    | CampusRoleAssignment
): WideHolding {
  return {
    id: assignment.id,
    role: assignment.role,
    user: assignment.user,
    user_name: assignment.user_name,
    role_label: assignment.role_label,
  };
}
