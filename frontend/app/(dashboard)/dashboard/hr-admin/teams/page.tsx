import Link from "next/link";
import { redirect } from "next/navigation";

import { CampusForm } from "@/components/hr/campus-form";
import { TeamsSection } from "@/components/hr/TeamsSection";
import type { ApproverRole } from "@/lib/approver-roles";
import { listApproverRoles } from "@/lib/approver-roles";
import type { Campus, Team } from "@/lib/teams";
import { listCampuses, listTeams } from "@/lib/teams";
import type { Employee } from "@/lib/employees";
import { listAllEmployees } from "@/lib/employees";
import { getCurrentUser } from "@/lib/auth";

const TEAMS_ERROR = "Unable to load teams. Please try again.";
const CAMPUSES_ERROR = "Unable to load campuses. Please try again.";
const ROLES_ERROR = "Unable to load approver roles. Please try again.";
const PEOPLE_ERROR = "Unable to load employees. Please try again.";

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

  // The create overlay needs the whole option set on the page, so it is read
  // here rather than on open: `listAllEmployees` because a page-1 read would
  // quietly offer only the first twenty people to staff each step with.
  const [teamsResult, campusesResult, rolesResult, peopleResult] =
    await Promise.all([
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
      listAllEmployees().then(
        (value) => ({ value, error: "" }),
        () => ({ value: [] as Employee[], error: PEOPLE_ERROR })
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
          employees={peopleResult.value}
          rolesError={rolesResult.error}
          peopleError={peopleResult.error}
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