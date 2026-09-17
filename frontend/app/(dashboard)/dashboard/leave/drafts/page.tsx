import { redirect } from "next/navigation";

import { DashboardShell } from "@/components/dashboard/dashboard-shell";
import { getCurrentUser } from "@/lib/auth";
import { DraftsList } from "@/components/leave/DraftsList";

export default async function DraftsPage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login");

  return (
    <DashboardShell user={user}>
      <DraftsList />
    </DashboardShell>
  );
}
