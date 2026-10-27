import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { AddTeamMembers } from "@/components/hr/add-team-members";
import { Badge } from "@/components/ui/badge";
import { Alert } from "@/components/ui/states";
import { FadeIn } from "@/components/motion/FadeIn";
import type { Employee } from "@/lib/employees";
import { getCurrentUser } from "@/lib/auth";
import { canAccessTeams } from "@/lib/nav/teams-nav";
import type { Team } from "@/lib/teams";
import {
  getTeam,
  teamCategoryBadgeTone,
  teamCategoryLabel,
} from "@/lib/teams";
import { listMemberCandidates } from "@/lib/teams-client";

const CANDIDATES_ERROR =
  "Unable to load the people who can join, so the list below may be incomplete.";

/**
 * Fill a team's roster.
 *
 * A page of its own rather than a dialog on the Members tab, because filling an
 * empty roster is where a new team's manager *starts*: the teams landing sends
 * them here directly when their team has nobody on it. As a page it can hold
 * the whole decision — who may join, who has been chosen, and the one write —
 * without a second overlay on top of the team screen.
 *
 * Only the team's designated manager may add anybody, so HR and other readers
 * are sent back to the roster they can read. The candidate list itself is the
 * backend's answer (`member-candidates`), which already scopes it to this team
 * and to the roster rule: unassigned employees of the team's category, plus
 * unassigned wide approvers of either category.
 */
export default async function AddTeamMembersPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (!canAccessTeams(user)) {
    redirect("/dashboard");
  }

  let team: Team;
  try {
    team = await getTeam(id);
  } catch {
    notFound();
  }

  if (!team.is_team_manager) {
    redirect(`/dashboard/teams/${team.id}?tab=members`);
  }

  let candidates: Employee[] = [];
  let candidatesError = "";
  try {
    candidates = await listMemberCandidates(team.id);
  } catch {
    candidatesError = CANDIDATES_ERROR;
  }

  return (
    <FadeIn>
      <div className="space-y-6">
        <div>
          <Link
            href={`/dashboard/teams/${team.id}?tab=members`}
            className="inline-flex items-center gap-1 text-sm font-medium text-brand-primary hover:text-brand-primary-hover"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to {team.name}
          </Link>
          <div className="mt-2 flex flex-wrap items-center gap-3">
            <h2 className="text-2xl font-bold text-text-primary">
              Add team members
            </h2>
            <Badge size="sm" tone={teamCategoryBadgeTone(team.category)}>
              {teamCategoryLabel(team.category)}
            </Badge>
          </div>
          <p className="mt-1 max-w-2xl text-text-secondary">
            Choose the people whose leave should route through{" "}
            <span className="font-medium text-text-primary">{team.name}</span>.
            {team.roster_count === 0
              ? " Nobody is on this team yet, so this is the first step."
              : ` ${team.roster_count} ${
                  team.roster_count === 1 ? "person is" : "people are"
                } already on it.`}
          </p>
        </div>

        {candidatesError && <Alert tone="error">{candidatesError}</Alert>}

        <AddTeamMembers team={team} candidates={candidates} />
      </div>
    </FadeIn>
  );
}
