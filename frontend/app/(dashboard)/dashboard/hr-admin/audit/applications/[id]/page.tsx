import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { ApplicationHistoryView } from "@/components/hr/application-history-view";
import { getCurrentUser } from "@/lib/auth";
import { getFinalizedApplication } from "@/lib/audit";
<<<<<<< HEAD
import { getApplicationTimeline, type TimelineEntry } from "@/lib/leave-history";
=======
import { FadeIn } from "@/components/motion/FadeIn";
>>>>>>> feature/plans-teams

export default async function AuditApplicationDetailPage({
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

  let application;
  try {
    application = await getFinalizedApplication(id);
  } catch {
    notFound();
  }

<<<<<<< HEAD
  let entries: TimelineEntry[] = [];
  try {
    const timeline = await getApplicationTimeline(id);
    entries = timeline.entries;
  } catch {
    // The finalized detail is the source of truth for the summary; keep the
    // history section empty rather than failing the whole page.
  }

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/dashboard/hr-admin/audit"
          className="inline-flex items-center gap-1 text-sm font-medium text-brand-primary hover:text-brand-primary-hover"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to audit view
        </Link>
        <h2 className="mt-2 text-2xl font-bold text-text-primary">
          {application.reference_number || "Leave application"}
        </h2>
        <p className="text-text-secondary">
          {application.employee_name}
          {application.leave_type_name ? ` \u00b7 ${application.leave_type_name}` : ""}
        </p>
      </div>

      <ApplicationHistoryView application={application} entries={entries} />
    </div>
=======
  return (
    <FadeIn>
      <div className="space-y-6">
        <div>
          <Link
            href="/dashboard/hr-admin/audit"
            className="inline-flex items-center gap-1 text-sm font-medium text-brand-primary hover:text-brand-primary-hover"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to audit view
          </Link>
          <h2 className="mt-2 text-xl font-semibold tracking-tight text-text-primary">
            {application.reference_number || "Leave application"}
          </h2>
          <p className="text-text-secondary">
            {application.employee_name}
            {application.leave_type_name ? ` \u00b7 ${application.leave_type_name}` : ""}
          </p>
        </div>

        <ApplicationHistoryView application={application} />
      </div>
    </FadeIn>
>>>>>>> feature/plans-teams
  );
}