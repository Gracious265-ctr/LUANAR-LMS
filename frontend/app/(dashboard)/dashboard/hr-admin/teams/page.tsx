import Link from "next/link";
import { redirect } from "next/navigation";

import { CampusForm } from "@/components/hr/campus-form";
import { TeamsSection } from "@/components/hr/TeamsSection";
import type { ApproverRole } from "@/lib/approver-roles";
import { listApproverRoles } from "@/lib/approver-roles";
import type { Campus, Team } from "@/lib/teams";
import type { Department } from "@/lib/departments";
import { listDepartments } from "@/lib/departments";
import { listCampuses, listTeams } from "@/lib/teams";
import { getCurrentUser } from "@/lib/auth";

const TEAMS_ERROR = "Unable to load teams. Please try again.";
const CAMPUSES_ERROR = "Unable to load campuses. Please try again.";
const ROLES_ERROR = "Unable to load approver roles. Please try again.";
const DEPARTMENTS_ERROR =
  "Unable to load departments, so this team cannot be placed in one.";

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
  if (user.role !== "hr") {
    redirect("/dashboard");
  }

  const { retired } = await searchParams;
  const showRetired = retired === "1";

  // The create overlay needs its option set on the page, so it is read here
  // rather than on open. The people who may hold a step are fetched per step
  // from the department, which is what makes eligibility answerable.
  const [
    teamsResult,
    campusesResult,
    rolesResult,
    departmentsResult,
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
      // A team's department decides which people may be appointed to its steps,
      // so the create overlay needs the list up front rather than discovering
      // the empty picker only when a step refuses the write.
      listDepartments().then(
        (value) => ({ value, error: "" }),
        () => ({ value: [] as Department[], error: DEPARTMENTS_ERROR })
      ),
    ]);

  const filters = [
    { label: "In force and draft", href: "/dashboard/hr-admin/teams", current: !showRetired },
    { label: "Including retired", href: "/dashboard/hr-admin/teams?retired=1", current: showRetired },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-text-primary">Teams</h2>
        <p className="text-text-secondary">
          The routing unit: an employee belongs to a team, and that
          team&apos;s chain decides who approves their application. Only a
          team that is in force routes anything.
        </p>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <TeamsSection
          teams={teamsResult.value}
          campuses={campusesResult.value}
          roles={rolesResult.value}
          departments={departmentsResult.value}
          departmentsError={departmentsResult.error}
                  rolesError={rolesResult.error}
                  error={teamsResult.error}
          filter={
            <div
              className="mb-4 flex flex-wrap items-center gap-2"
              role="group"
              aria-label="Filter teams by status"
            >
              {filters.map((filter) => (
                <Link
                  key={filter.label}
                  href={filter.href}
                  aria-current={filter.current ? "page" : undefined}
                  className={`rounded-sm px-3 py-1 text-xs font-medium ${
                    filter.current
                      ? "bg-brand-primary text-button-primary-foreground"
                      : "border border-border-default bg-surface-card text-text-secondary hover:bg-button-secondary-hover"
                  }`}
                >
                  {filter.label}
                </Link>
              ))}
            </div>
          }
        />
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <h3 className="mb-2 text-lg font-semibold text-text-primary">
          Campuses
        </h3>
        {campusesResult.error ? (
          <p className="text-sm text-status-rejected">{campusesResult.error}</p>
        ) : (
          <CampusForm campuses={campusesResult.value} />
        )}
      </div>
    </div>
  );
}

export default TeamsPage;