import { redirect } from "next/navigation";

import { PlansHome } from "@/components/plans/plans-home";
import { getCurrentUser } from "@/lib/auth";
import type { UserRole } from "@/lib/employees";

export const metadata = {
  title: "Plans",
};

export default async function PlansPage() {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }

  return <PlansHome role={user.role as UserRole} />;
}