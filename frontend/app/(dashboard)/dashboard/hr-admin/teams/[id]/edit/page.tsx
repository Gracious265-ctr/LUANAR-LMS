import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { TeamForm } from "@/components/hr/team-form";
import type { Campus } from "@/lib/teams";
import { getTeam, listCampuses } from "@/lib/teams";
import { getCurrentUser } from "@/lib/auth";
import { listWorkflows } from "@/lib/workflows";

const CAMPUSES_ERROR = "Unable to load campuses, so this team cannot be scoped to one.";

export default async function EditTeamPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (user.role !== "hr") {
    redirect("/dashboard");
  }

  let team;
  try {
    team = await getTeam(id);
  } catch {
    notFound();
  }

  let campuses: Campus[] = [];
  let campusesError = "";
  try {
    campuses = await listCampuses();
  } catch {
    campusesError = CAMPUSES_ERROR;
  }

  const { results: workflows } = await listWorkflows();

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/dashboard/hr-admin/teams"
          className="inline-flex items-center gap-1 text-sm font-medium text-brand-primary hover:text-brand-primary-hover"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to teams
        </Link>
        <h2 className="mt-2 text-2xl font-bold text-text-primary">
          Edit {team.name}
        </h2>
        <p className="text-text-secondary">
          The workflow this team routes through owns the approval sections;
          member staffing happens on the teams list.
        </p>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        {campusesError && (
          <p className="mb-4 rounded-md bg-status-rejected-subtle p-3 text-sm text-status-rejected">
            {campusesError}
          </p>
        )}
        <TeamForm team={team} campuses={campuses} workflows={workflows} />
      </div>
    </div>
  );
}
