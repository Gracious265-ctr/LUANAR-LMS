import { redirect } from "next/navigation";

import { DashboardShell } from "@/components/dashboard/dashboard-shell";
import { getCurrentUser } from "@/lib/auth";
import { ReviewSummaryClient } from "./ReviewSummaryClient";

export default async function ReviewLeavePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const user = await getCurrentUser();
  if (!user) redirect("/login");

  const { id } = await params;

  return (
    <DashboardShell user={user}>
      <div className="max-w-2xl mx-auto">
        <ReviewSummaryClient applicationId={id} />
      </div>
    </DashboardShell>
  );
}
