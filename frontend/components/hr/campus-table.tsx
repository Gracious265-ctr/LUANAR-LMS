import Link from "next/link";

import { teamCategoryLabel } from "@/lib/team-category";
import type { Campus, Team } from "@/lib/teams";

/**
 * Campuses as a list rather than a wall of cards.
 *
 * The question on this screen is "which of these is a campus teams actually
 * sit at?", and a table is what answers it: one row per campus, the teams at
 * each named, and a status column that says whether the campus can still be
 * chosen. A campus with no teams is not a mistake — it is the one HR is about
 * to use.
 */
export function CampusTable({
  campuses,
  teams,
}: {
  campuses: Campus[];
  teams: Team[];
}) {
  if (campuses.length === 0) {
    return (
      <div className="rounded-xl border border-border-default bg-surface-card p-6 text-center shadow-subtle">
        <p className="text-base font-medium text-text-primary">
          No campuses yet
        </p>
        <p className="mt-1 text-sm text-text-muted">
          A campus is where an academic team sits, and it is what makes
          campus-wide approvers reachable for that team&apos;s stages.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-border-default bg-surface-card shadow-subtle">
      <table className="w-full text-left text-sm">
        <caption className="sr-only">
          Campuses, the academic teams that sit at each, and whether each campus
          is still active
        </caption>
        <thead className="border-b border-border-default text-xs uppercase tracking-wide text-text-muted">
          <tr>
            <th scope="col" className="px-4 py-3">
              Campus
            </th>
            <th scope="col" className="px-4 py-3">
              Code
            </th>
            <th scope="col" className="px-4 py-3">
              Academic teams
            </th>
            <th scope="col" className="px-4 py-3">
              Status
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border-default">
          {campuses.map((campus) => {
            const atCampus = teams.filter((team) => team.campus === campus.id);
            return (
              <tr key={campus.id} className="hover:bg-surface-page">
                <td className="px-4 py-3">
                  <Link
                    href={`/dashboard/hr-admin/campuses/${campus.id}`}
                    className="font-medium text-brand-primary hover:text-brand-primary-hover"
                  >
                    {campus.name}
                  </Link>
                  {campus.description && (
                    <p className="mt-0.5 text-xs text-text-muted">
                      {campus.description}
                    </p>
                  )}
                </td>
                <td className="px-4 py-3 font-mono text-xs text-text-muted">
                  {campus.code}
                </td>
                <td className="px-4 py-3">
                  {atCampus.length === 0 ? (
                    <span className="text-xs text-text-muted">None yet</span>
                  ) : (
                    <ul className="space-y-0.5">
                      {atCampus.map((team) => (
                        <li key={team.id} className="text-xs">
                          <Link
                            href={`/dashboard/teams/${team.id}`}
                            className="text-text-secondary hover:text-brand-primary"
                          >
                            {team.name}
                          </Link>
                          <span className="ml-1 text-text-muted">
                            · {teamCategoryLabel(team.category)}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </td>
                <td className="px-4 py-3">
                  <span
                    className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${
                      campus.is_active
                        ? "bg-brand-secondary-subtle text-brand-secondary"
                        : "bg-surface-muted text-text-muted"
                    }`}
                  >
                    {campus.is_active ? "Active" : "Retired"}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
