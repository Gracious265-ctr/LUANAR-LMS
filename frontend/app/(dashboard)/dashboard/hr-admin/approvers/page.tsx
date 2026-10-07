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

  const institutionByRole = groupByRole(
    holders.institution.map((assignment) => toHolding(assignment))
  );
  const teamByRole = groupByRole(
    holders.team
      .filter((assignment) => teamFilter === null || assignment.team === teamFilter)
      .map((assignment) => toHolding(assignment))
  );
  const campusByRole = groupByRole(
    holders.campus
      .filter(
        (assignment) => campusFilter === null || assignment.campus === campusFilter
      )
      .map((assignment) => toHolding(assignment))
  );

  const activeRoles = roles.filter((role) => role.is_active);
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
        <div className="space-y-6">
          {activeRoles.map((role) => {
            const panels: React.ReactNode[] = [];
            if (showInstitution) {
              panels.push(
                <WideHoldingPanel
                  key={`institution-${role.id}`}
                  role={role}
                  scope="institution"
                  employees={employees}
                  holdings={institutionByRole.get(role.id) ?? []}
                />
              );
            }
            if (showTeam) {
              panels.push(
                <WideHoldingPanel
                  key={`team-${role.id}`}
                  role={role}
                  scope="team"
                  scopeOptions={teamOptions}
                  employees={employees}
                  holdings={teamByRole.get(role.id) ?? []}
                />
              );
            }
            if (showCampus) {
              panels.push(
                <WideHoldingPanel
                  key={`campus-${role.id}`}
                  role={role}
                  scope="campus"
                  scopeOptions={campusOptions}
                  employees={employees}
                  holdings={campusByRole.get(role.id) ?? []}
                />
              );
            }

            return (
              <section
                key={role.id}
                className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle"
                aria-label={role.label}
              >
                <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
                  <div>
                    <h3 className="text-lg font-semibold text-text-primary">
                      {role.label}
                    </h3>
                    <p className="text-sm text-text-secondary">
                      {role.description ||
                        "Held at one or more of the three scopes below."}
                    </p>
                  </div>
                  <span className="text-xs uppercase tracking-wide text-text-muted">
                    {role.is_institution_wide
                      ? "Institution-wide role"
                      : "Scoped role"}
                  </span>
                </div>
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                  {panels}
                </div>
                {!role.is_institution_wide && (
                  <p className="mt-3 text-xs text-text-muted">
                    An institution-wide role is held here only; a team or campus
                    holding cannot serve an administration team&apos;s stages.
                  </p>
                )}
                {role.is_institution_wide && showInstitution && (
                  <p className="mt-3 text-xs text-text-muted">
                    Institution-wide holdings are the only ones an
                    administration team&apos;s stages may fall back to.
                  </p>
                )}
              </section>
            );
          })}
        </div>
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

function groupByRole(holdings: WideHolding[]): Map<number, WideHolding[]> {
  const byRole = new Map<number, WideHolding[]>();
  for (const holding of holdings) {
    const bucket = byRole.get(holding.role);
    if (bucket) {
      bucket.push(holding);
    } else {
      byRole.set(holding.role, [holding]);
    }
  }
  return byRole;
}
