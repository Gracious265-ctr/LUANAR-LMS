import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { TeamForm } from "@/components/hr/team-form";
import type { ApproverRole } from "@/lib/approver-roles";
import { listApproverRoles } from "@/lib/approver-roles";
import type { Department } from "@/lib/departments";
import { listDepartments } from "@/lib/departments";
import type { Campus } from "@/lib/teams";
import { getTeam, listCampuses } from "@/lib/teams";
import { getCurrentUser } from "@/lib/auth";

const CAMPUSES_ERROR = "Unable to load campuses, so this team cannot be scoped to one.";
const ROLES_ERROR =
  "Unable to load approver roles, so the approval steps cannot be described.";
const DEPARTMENTS_ERROR =
  "Unable to load departments, so this team cannot be placed in one.";

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
          href={`/dashboard/hr-admin/teams/${team.id}`}
          className="inline-flex items-center gap-1 text-sm font-medium text-brand-primary hover:text-brand-primary-hover"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to {team.name}
        </Link>
        <h2 className="mt-2 text-2xl font-bold text-text-primary">
          Edit {team.name}
        </h2>
        <p className="text-text-secondary">
          What this team is, when it is in force, and the approval steps its
          applications follow. Whether it is routing is decided on the
          team&apos;s own page, by a check that refuses to put a chain nobody can
          act for in front of an applicant.
        </p>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <TeamForm
          team={team}
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
