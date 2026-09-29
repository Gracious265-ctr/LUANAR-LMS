import { redirect } from "next/navigation";

import { PlanScopeList } from "@/components/plans/plan-scope-list";
import { getCurrentUser } from "@/lib/auth";

export const metadata = {
  title: "Team plans",
};

export default async function TeamPlansPage() {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }

  return <PlanScopeList scope="team" />;
}