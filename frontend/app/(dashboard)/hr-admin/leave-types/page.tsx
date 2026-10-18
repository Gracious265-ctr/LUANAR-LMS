import { redirect } from "next/navigation";

import { LeaveTypesSection } from "@/components/hr/LeaveTypesSection";
import { getCurrentUser } from "@/lib/auth";
import { listLeaveTypes } from "@/lib/leave-rules";
import { FadeIn } from "@/components/motion/FadeIn";

export default async function LeaveTypesPage() {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (user.role !== "hr") {
    redirect("/");
  }

  let leaveTypes;
  let listError = "";
  try {
    leaveTypes = await listLeaveTypes();
  } catch {
    listError = "Unable to load leave types. Please try again.";
  }

  return (
    <FadeIn>
      <div className="space-y-6">
        <h2 className="text-xl font-semibold tracking-tight text-text-primary">
          Leave types
        </h2>
        {listError ? (
          <div className="rounded-lg bg-status-rejected-subtle py-12 text-center text-sm text-status-rejected">
            {listError}
          </div>
        ) : leaveTypes ? (
          <LeaveTypesSection leaveTypes={leaveTypes.results} />
        ) : null}
      </div>
    </FadeIn>
  );
}
