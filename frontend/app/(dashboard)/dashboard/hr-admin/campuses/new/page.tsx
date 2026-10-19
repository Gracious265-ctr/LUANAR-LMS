import Link from "next/link";
import { redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { CampusForm } from "@/components/hr/campus-form";
import { getCurrentUser } from "@/lib/auth";
import { isOrganisationAdministrator } from "@/lib/nav/organisation-nav";

/**
 * A new campus.
 *
 * Named and saved before any team sits at it, which is the ordinary order:
 * the campus has to exist before the team form can offer it, and a team that
 * is being placed somewhere new is the usual reason to be here.
 */
export default async function NewCampusPage() {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (!isOrganisationAdministrator(user)) {
    redirect("/dashboard");
  }

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/dashboard/hr-admin/campuses"
          className="inline-flex items-center gap-1 text-sm font-medium text-brand-primary hover:text-brand-primary-hover"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to campuses
        </Link>
        <h2 className="mt-2 text-2xl font-bold text-text-primary">
          New campus
        </h2>
        <p className="text-text-secondary">
          A campus is what an academic team sits at, and it is what scopes
          campus-wide approvers to the teams at it. Creating one here does not
          move anybody: a team is placed at a campus when it is created or
          edited.
        </p>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <CampusForm />
      </div>
    </div>
  );
}
