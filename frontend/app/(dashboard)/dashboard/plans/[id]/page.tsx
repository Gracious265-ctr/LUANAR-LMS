import { redirect } from "next/navigation";

import { PlanDetailView } from "@/components/plans/plan-detail";
import { getCurrentUser } from "@/lib/auth";

export const metadata = {
  title: "Plan",
};

export default async function PlanDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }

  const { id } = await params;
  return <PlanDetailView id={id} />;
}