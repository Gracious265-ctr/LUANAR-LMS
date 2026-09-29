import { redirect } from "next/navigation";

import { PlanSettingsForm } from "@/components/plans/plan-settings-form";
import { getCurrentUser } from "@/lib/auth";

export const metadata = {
  title: "Plan settings",
};

export default async function PlanSettingsPage() {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (user.role !== "hr") {
    redirect("/dashboard/plans");
  }

  return <PlanSettingsForm />;
}