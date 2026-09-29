import { redirect } from "next/navigation";

import { PlanApprovalsWorkspace } from "@/components/plans/plan-approvals-workspace";
import { getCurrentUser } from "@/lib/auth";

const APPROVER_ROLES = ["supervisor", "hod", "dean", "registrar", "dvc", "hr"];

export const metadata = {
  title: "Plan approvals",
};

export default async function PlanApprovalsPage() {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }

  if (!APPROVER_ROLES.includes(user.role)) {
    redirect("/dashboard/plans");
  }

  return <PlanApprovalsWorkspace />;
}