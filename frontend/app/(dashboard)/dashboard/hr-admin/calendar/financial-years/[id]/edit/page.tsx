import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { FinancialYearForm } from "@/components/hr/financial-year-form";
import { getCurrentUser } from "@/lib/auth";
import { getFinancialYear } from "@/lib/financial-years";
import { Card } from "@/components/ui/card";

export default async function EditFinancialYearPage({
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

  let financialYear;
  try {
    financialYear = await getFinancialYear(id);
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
          Edit financial year
        </h2>
        <p className="text-text-secondary">
          {financialYear.start_date} – {financialYear.end_date}
          {financialYear.is_active ? " (active)" : ""}.
        </p>
      </div>

      <Card>
        <FinancialYearForm financialYear={financialYear} />
      </Card>
    </div>
  );
}