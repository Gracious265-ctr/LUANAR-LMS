import { redirect } from "next/navigation";

import { PlanApprovalDetailView } from "@/components/plans/plan-approval-detail";
import { getCurrentUser } from "@/lib/auth";

const APPROVER_ROLES = ["supervisor", "hod", "dean", "registrar", "dvc", "hr"];

export const metadata = {
  title: "Plan approval",
};

export default async function PlanApprovalDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }

  if (!APPROVER_ROLES.includes(user.role)) {
    redirect("/dashboard/plans");
  }

  const { id } = await params;
  return <PlanApprovalDetailView id={id} />;
}