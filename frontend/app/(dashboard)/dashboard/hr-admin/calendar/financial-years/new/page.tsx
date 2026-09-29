import Link from "next/link";
import { redirect } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { FinancialYearForm } from "@/components/hr/financial-year-form";
import { getCurrentUser } from "@/lib/auth";
import { Card } from "@/components/ui/card";

export default async function NewFinancialYearPage() {
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
          New financial year
        </h2>
        <p className="text-text-secondary">
          Enter the start and end dates for a financial-year period. Periods must
          not overlap each other.
        </p>
      </div>

      <Card>
        <FinancialYearForm />
      </Card>
    </div>
  );
}