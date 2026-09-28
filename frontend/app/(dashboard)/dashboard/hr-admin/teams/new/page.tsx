import Link from "next/link";
import { redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { TeamForm } from "@/components/hr/team-form";
import type { Campus } from "@/lib/teams";
import { listCampuses } from "@/lib/teams";
import { getCurrentUser } from "@/lib/auth";
import { listWorkflows } from "@/lib/workflows";

const CAMPUSES_ERROR = "Unable to load campuses, so this team cannot be scoped to one.";

export default async function NewTeamPage() {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (user.role !== "hr") {
    redirect("/dashboard");
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
        <h2 className="mt-2 text-2xl font-bold text-text-primary">New team</h2>
        <p className="text-text-secondary">
          Create the group an employee belongs to. Give it a workflow, then add
          the people who will approve.
        </p>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        {campusesError && (
          <p className="mb-4 rounded-md bg-status-rejected-subtle p-3 text-sm text-status-rejected">
            {campusesError}
          </p>
        )}
        <TeamForm campuses={campuses} workflows={workflows} />
      </div>
    </div>
  );
}
