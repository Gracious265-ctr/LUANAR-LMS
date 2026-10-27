import Link from "next/link";

import {
  teamCategoryBadgeTone,
  teamCategoryLabel,
} from "@/lib/team-category";
import type { Team } from "@/lib/teams";
import {
  teamStatusBadgeTone,
  teamStatusLabel,
} from "@/lib/teams-client";
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
 * Teams as a list rather than a wall of cards.
 *
 * The first question on this screen is "which of these is in force?", and a
 * table is what answers it: one row per team, one glance down the status
 * column, no scrolling to compare two of them. Each row opens the team, which
 * is where the chain and the roster live.
 */
export function TeamTable({
  teams,
  empty,
}: {
  teams: Team[];
  /** Overrides the empty state — the section supplies search-aware copy. */
  empty?: React.ReactNode;
}) {
  if (teams.length === 0) {
    return (
      empty ?? (
        <EmptyPanel
          title="No teams found"
          description="Create a team to route its employees' applications through their own approvers."
        />
      )
    );
  }

  return (
    <div className="rounded-xl border border-border-default bg-surface-card shadow-subtle">
      <Table>
        <caption className="sr-only">
          Teams, their approval chain, whether they are in force, and quick
          links to manage each team
        </caption>
        <TableHeader>
          <TableRow>
            <TableHead>Team</TableHead>
            <TableHead>Chain</TableHead>
            <TableHead>Steps</TableHead>
            <TableHead>In force</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right">Manage</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {teams.map((team) => (
            <TableRow key={team.id}>
              <TableCell>
                <Link
                  href={`/dashboard/teams/${team.id}`}
                  className="font-medium text-text-primary hover:text-brand-primary"
                >
                  {team.name}
                </Link>
                <p className="text-xs text-text-muted">
                  {[
                    team.campus_name && `Campus: ${team.campus_name}`,
                    `${team.member_count} ${
                      team.member_count === 1 ? "person" : "people"
                    } on the chain`,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
                <Badge size="xs" tone={teamCategoryBadgeTone(team.category)}>
                  {teamCategoryLabel(team.category)}
                </Badge>
              </TableCell>
              <TableCell className="text-text-secondary">
                {team.workflow_name || (
                  <span className="text-text-muted">No chain</span>
                )}
              </TableCell>
              <TableCell className="text-text-secondary">
                {team.sections.length === 0
                  ? "—"
                  : `${team.sections.filter((s) => s.approver !== null).length} of ${
                      team.sections.length
                    } staffed`}
              </TableCell>
              <TableCell className="text-text-secondary">
                {inForceWindow(team)}
              </TableCell>
              <TableCell>
                <Badge size="sm" tone={teamStatusBadgeTone(team.status)}>
                  {teamStatusLabel(team.status)}
                </Badge>
              </TableCell>
              <TableCell className="text-right">
                <span className="inline-flex flex-wrap items-center justify-end gap-2 text-xs">
                  <Link
                    href={`/dashboard/teams/${team.id}?tab=steps`}
                    className="font-medium text-brand-primary hover:text-brand-primary-hover"
                  >
                    Steps
                  </Link>
                  <Link
                    href={`/dashboard/teams/${team.id}?tab=approvers`}
                    className="font-medium text-brand-primary hover:text-brand-primary-hover"
                  >
                    Approvers
                  </Link>
                  <Link
                    href={`/dashboard/teams/${team.id}?tab=members`}
                    className="font-medium text-brand-primary hover:text-brand-primary-hover"
                  >
                    Members
                  </Link>
                </span>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
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
