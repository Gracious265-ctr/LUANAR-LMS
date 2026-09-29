import { redirect } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { PlanForm } from "@/components/plans/plan-form";
import { getCurrentUser } from "@/lib/auth";
import { listLeaveTypes } from "@/lib/leave-rules";
import { Card } from "@/components/ui/card";

export const metadata = {
  title: "New plan",
};

export default async function NewPlanPage() {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }

  let leaveTypes: Awaited<ReturnType<typeof listLeaveTypes>>["results"] = [];
  try {
    const response = await listLeaveTypes();
    leaveTypes = response.results;
  } catch {
    // The form stays usable with an empty leave-type list if they cannot load.
  }

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/dashboard/plans"
          className="inline-flex items-center gap-1 text-sm font-medium text-brand-primary hover:text-brand-primary-hover"
        >
          <ArrowLeft className="size-4" />
          Back to plans
        </Link>
        <h2 className="mt-2 text-xl font-semibold tracking-tight text-text-primary">New plan</h2>
        <p className="text-text-secondary">
          Set the financial year your plan covers and the leave blocks you intend
          to take. Only leave types that consume annual entitlement are reserved
          at approval.
        </p>
      </div>

      <Card>
        <PlanForm leaveTypes={leaveTypes} />
      </Card>
    </div>
  );
}