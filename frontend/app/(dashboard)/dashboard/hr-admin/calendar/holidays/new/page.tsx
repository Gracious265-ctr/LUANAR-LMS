import Link from "next/link";
import { redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { PublicHolidayForm } from "@/components/hr/public-holiday-form";
import { getCurrentUser } from "@/lib/auth";

export default async function NewHolidayPage() {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (user.role !== "hr") {
    redirect("/dashboard");
  }

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/dashboard/hr-admin/calendar"
          className="inline-flex items-center gap-1 text-sm font-medium text-brand-primary hover:text-brand-primary-hover"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to leave calendar
        </Link>
        <h2 className="mt-2 text-xl font-semibold tracking-tight text-text-primary">
          New public holiday
        </h2>
        <p className="text-text-secondary">
          Add a date that should not count as a working leave day.
        </p>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <PublicHolidayForm />
      </div>
    </div>
  );
}