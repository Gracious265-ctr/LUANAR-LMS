import { redirect } from "next/navigation";

import { PlanAdminView } from "@/components/plans/plan-admin";
import { getCurrentUser } from "@/lib/auth";

export const metadata = {
  title: "All plans",
};

export default async function PlanAdminPage() {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (user.role !== "hr") {
    redirect("/dashboard/plans");
  }

  return <PlanAdminView />;
}