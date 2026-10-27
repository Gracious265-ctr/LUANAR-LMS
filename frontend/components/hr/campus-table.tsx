import Link from "next/link";

import { teamCategoryLabel } from "@/lib/team-category";
import type { Campus, Team } from "@/lib/teams";
import { Badge } from "@/components/ui/badge";
import { EmptyPanel } from "@/components/ui/states";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

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
  empty,
}: {
  campuses: Campus[];
  teams: Team[];
  /** Overrides the empty state — the list supplies search-aware copy. */
  empty?: React.ReactNode;
}) {
  if (campuses.length === 0) {
    return (
      empty ?? (
        <EmptyPanel
          title="No campuses yet"
          description="A campus is where an academic team sits."
        />
      )
    );
  }

  return (
    <div className="rounded-xl border border-border-default bg-surface-card shadow-subtle">
      <Table>
        <caption className="sr-only">
          Campuses, the academic teams that sit at each, and whether each campus
          is still active
        </caption>
        <TableHeader>
          <TableRow>
            <TableHead>Campus</TableHead>
            <TableHead>Code</TableHead>
            <TableHead>Academic teams</TableHead>
            <TableHead>Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {campuses.map((campus) => {
            const atCampus = teams.filter((team) => team.campus === campus.id);
            return (
              <TableRow key={campus.id}>
                <TableCell>
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
                </TableCell>
                <TableCell className="font-mono text-xs text-text-muted">
                  {campus.code}
                </TableCell>
                <TableCell>
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
                </TableCell>
                <TableCell>
                  <Badge size="sm" tone={campus.is_active ? "info" : "muted"}>
                    {campus.is_active ? "Active" : "Retired"}
                  </Badge>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
