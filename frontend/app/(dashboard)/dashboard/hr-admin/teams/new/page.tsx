import Link from "next/link";
import { redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { TeamForm } from "@/components/hr/team-form";
import type { ApproverRole } from "@/lib/approver-roles";
import { listApproverRoles } from "@/lib/approver-roles";
import type { Department } from "@/lib/departments";
import { listDepartments } from "@/lib/departments";
import type { Campus } from "@/lib/teams";
import { listCampuses } from "@/lib/teams";
import { getCurrentUser } from "@/lib/auth";

const CAMPUSES_ERROR = "Unable to load campuses, so this team cannot be scoped to one.";
const ROLES_ERROR =
  "Unable to load approver roles, so the approval steps cannot be described.";
const DEPARTMENTS_ERROR =
  "Unable to load departments, so this team cannot be placed in one.";

/**
 * Everything a team's two pages need, loaded together and reported separately:
 * each failure narrows a different part of the form, and a form with a silently
 * empty picker is how a chain gets built with a step nobody can act for.
 */
export default async function NewTeamPage() {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (user.role !== "hr") {
    redirect("/dashboard");
  }

  const [campusesResult, rolesResult, departmentsResult] = await Promise.all([
      listCampuses().then(
        (value) => ({ value, error: "" }),
        () => ({ value: [] as Campus[], error: CAMPUSES_ERROR })
      ),
      listApproverRoles().then(
        (value) => ({ value, error: "" }),
        () => ({ value: [] as ApproverRole[], error: ROLES_ERROR })
      ),
      listDepartments().then(
        (value) => ({ value, error: "" }),
        () => ({ value: [] as Department[], error: DEPARTMENTS_ERROR })
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
          Create the group an employee belongs to, and name who approves for it.
          The team starts as a draft and routes nothing until you put it into
          force, so nothing half-built can reach an applicant.
        </p>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <TeamForm
          campuses={campusesResult.value}
          departments={departmentsResult.value}
          roles={rolesResult.value}
          departmentsError={departmentsResult.error}
          rolesError={rolesResult.error}
        />
      </div>
    </div>
  );
}
