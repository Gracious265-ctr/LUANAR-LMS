import { redirect } from "next/navigation";

import { PlanScopeList } from "@/components/plans/plan-scope-list";
import { getCurrentUser } from "@/lib/auth";

const DEPARTMENT_ROLES = ["supervisor", "hod", "dean", "registrar", "dvc", "hr"];

export const metadata = {
  title: "Department plans",
};

export default async function DepartmentPlansPage() {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }

  // Department review is for supervisors/HODs and above, and HR (D18). The
  // backend enforces this independently; the page-level check keeps the
  // sidebar and route consistent.
  if (!DEPARTMENT_ROLES.includes(user.role)) {
    redirect("/dashboard/plans");
  }

  return <PlanScopeList scope="department" />;
}