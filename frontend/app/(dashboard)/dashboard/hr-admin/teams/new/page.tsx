import Link from "next/link";
import { redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { TeamForm } from "@/components/hr/team-form";
import type { ApproverRole } from "@/lib/approver-roles";
import { listApproverRoles } from "@/lib/approver-roles";
import type { Campus } from "@/lib/teams";
import { listCampuses } from "@/lib/teams";
import { getCurrentUser } from "@/lib/auth";

const CAMPUSES_ERROR = "Unable to load campuses, so this team cannot be scoped to one.";
const ROLES_ERROR =
  "Unable to load approver roles, so the approval steps cannot be described.";

/**
 * Everything creating a team needs, loaded together and reported separately.
 * The page asks only what the team *is*; the approval chain is configured
 * later, once its employees are on it, because an approver is one of the
 * team's employees and a team being created has none yet. Roles are still
 * loaded for the chain-editing form this component also renders, though a new
 * team never reaches it.
 */
export default async function NewTeamPage() {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (user.role !== "hr") {
    redirect("/dashboard");
  }

  const [campusesResult, rolesResult] = await Promise.all([
      listCampuses().then(
        (value) => ({ value, error: "" }),
        () => ({ value: [] as Campus[], error: CAMPUSES_ERROR })
      ),
      listApproverRoles().then(
        (value) => ({ value, error: "" }),
        () => ({ value: [] as ApproverRole[], error: ROLES_ERROR })
      ),
    ]);

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
          Create the group an employee belongs to. The team starts as a draft,
          routes nothing, and opens on its Members tab once created — add its
          employees there, then configure the approval chain from the
          team&apos;s Overview. Nothing half-built can reach an applicant.
        </p>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <TeamForm
          campuses={campusesResult.value}
          roles={rolesResult.value}
          rolesError={rolesResult.error}
        />
      </div>
    </div>
  );
}
