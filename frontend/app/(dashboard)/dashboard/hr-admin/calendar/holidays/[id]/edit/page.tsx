import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { PublicHolidayForm } from "@/components/hr/public-holiday-form";
import { getCurrentUser } from "@/lib/auth";
import { getPublicHoliday } from "@/lib/financial-years";
import { Card } from "@/components/ui/card";

export default async function EditHolidayPage({
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

  let publicHoliday;
  try {
    publicHoliday = await getPublicHoliday(id);
  } catch {
    notFound();
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
          Edit public holiday
        </h2>
        <p className="text-text-secondary">
          Update the name or date for {publicHoliday.name}.
        </p>
      </div>

      <Card>
        <PublicHolidayForm publicHoliday={publicHoliday} />
      </Card>
    </div>
  );
}