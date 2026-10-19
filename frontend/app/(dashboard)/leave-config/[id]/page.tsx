import { notFound } from "next/navigation";

import { LeaveTypeForm } from "@/components/leave-config/LeaveTypeForm";
import { getLeaveType, requireLeaveConfigAccess } from "@/lib/leave-config-server";

/**
 * Edit one leave type (spec 3.3).
 *
 * Not-found covers both a typo in the URL and a type that no longer answers,
 * so a retired-then-purged record and a mistyped id land on the same page
 * instead of one showing an empty form the API would then reject.
 */
export default async function EditLeaveTypePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  await requireLeaveConfigAccess();
  const { id } = await params;
  if (!/^\d+$/.test(id)) {
    notFound();
  }

  const leaveType = await getLeaveType(id).catch(() => notFound());

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-text-primary">
          Edit leave type
        </h2>
        <p className="text-text-secondary">{leaveType.name}</p>
      </div>

      <LeaveTypeForm leaveType={leaveType} />
    </div>
  );
}
