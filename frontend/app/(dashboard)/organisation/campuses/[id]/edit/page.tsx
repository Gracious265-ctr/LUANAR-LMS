import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { CampusForm } from "@/components/hr/campus-form";
import { getCampus } from "@/lib/teams";
import { getCurrentUser } from "@/lib/auth";

/**
 * Edit one campus.
 *
 * The name and description are ordinary edits. The code stays editable for as
 * long as no team uses the campus — a team stores the campus's id rather than
 * its code, so a rename is one write here — and the backend refuses the change
 * once a team sits at it, because the code is what the rest of the system
 * names the campus by.
 */
export default async function EditCampusPage({
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
    redirect("/");
  }

  let campus;
  try {
    campus = await getCampus(id);
  } catch {
    notFound();
  }

  return (
    <div className="space-y-6">
      <div>
        <Link
          href={`/organisation/campuses/${campus.id}`}
          className="inline-flex items-center gap-1 text-sm font-medium text-brand-primary hover:text-brand-primary-hover"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to {campus.name}
        </Link>
        <h2 className="mt-2 text-2xl font-bold text-text-primary">
          Edit campus
        </h2>
        <p className="text-text-secondary">
          {campus.name}
          {campus.code && (
            <span className="ml-2 font-mono text-xs text-text-muted">
              {campus.code}
            </span>
          )}
        </p>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <CampusForm campus={campus} />
      </div>
    </div>
  );
}
