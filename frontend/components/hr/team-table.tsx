import Link from "next/link";

import type { Team } from "@/lib/teams";
import { teamStatusBadgeClass, teamStatusLabel } from "@/lib/teams";

/**
 * Teams as a list rather than a wall of cards.
 *
 * The first question on this screen is "which of these is in force?", and a
 * table is what answers it: one row per team, one glance down the status
 * column, no scrolling to compare two of them. Each row opens the team, which
 * is where the chain and the roster live.
 */
export function TeamTable({ teams }: { teams: Team[] }) {
  if (teams.length === 0) {
    return (
      <div className="rounded-xl border border-border-default bg-surface-card p-6 text-center shadow-subtle">
        <p className="text-base font-medium text-text-primary">No teams found</p>
        <p className="mt-1 text-sm text-text-muted">
          Create a team to route its employees&apos; applications through their
          own approvers.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-border-default bg-surface-card shadow-subtle">
      <table className="w-full text-left text-sm">
        <caption className="sr-only">
          Teams, their approval chain, and whether they are in force
        </caption>
        <thead className="border-b border-border-default text-xs uppercase tracking-wide text-text-muted">
          <tr>
            <th scope="col" className="px-4 py-3">
              Team
            </th>
            <th scope="col" className="px-4 py-3">
              Chain
            </th>
            <th scope="col" className="px-4 py-3">
              Steps
            </th>
            <th scope="col" className="px-4 py-3">
              In force
            </th>
            <th scope="col" className="px-4 py-3">
              Status
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border-default">
          {teams.map((team) => (
            <tr key={team.id} className="hover:bg-surface-hover">
              <th scope="row" className="px-4 py-3 font-normal">
                <Link
                  href={`/dashboard/hr-admin/teams/${team.id}`}
                  className="font-medium text-text-primary hover:text-brand-primary"
                >
                  {team.name}
                </Link>
                <p className="text-xs text-text-muted">
                  {[
                    team.department_name && `Department: ${team.department_name}`,
                    team.campus_name && `Campus: ${team.campus_name}`,
                    `${team.member_count} ${
                      team.member_count === 1 ? "person" : "people"
                    } on the chain`,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
              </th>
              <td className="px-4 py-3 text-text-secondary">
                {team.workflow_name || (
                  <span className="text-text-muted">No chain</span>
                )}
              </td>
              <td className="px-4 py-3 text-text-secondary">
                {team.sections.length === 0
                  ? "—"
                  : `${team.sections.filter((s) => s.approver !== null).length} of ${
                      team.sections.length
                    } staffed`}
              </td>
              <td className="px-4 py-3 text-text-secondary">
                {inForceWindow(team)}
              </td>
              <td className="px-4 py-3">
                <span
                  className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${teamStatusBadgeClass(
                    team.status
                  )}`}
                >
                  {teamStatusLabel(team.status)}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/**
 * The window a team is in force, in the words HR would use. A team can be
 * active and still not routing today, so the date is shown next to the status
 * rather than left for the reader to infer.
 */
function inForceWindow(team: Team): string {
  const from = team.effective_from ? formatDate(team.effective_from) : null;
  const to = team.effective_to ? formatDate(team.effective_to) : null;
  if (from && to) {
    return `${from} to ${to}`;
  }
  if (from) {
    return `From ${from}`;
  }
  return "No dates set";
}

function formatDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(date);
}
