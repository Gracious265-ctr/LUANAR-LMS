import { LeaveTypeForm } from "@/components/leave-config/LeaveTypeForm";
import { requireLeaveConfigAccess } from "@/lib/leave-config-server";

/**
 * Create one leave type (spec 3.3).
 *
 * A bare URL cannot carry a record, so this route renders the same form the
 * edit route does with nothing to pre-fill it — one form component to keep in
 * step rather than two.
 */
export default async function NewLeaveTypePage() {
  await requireLeaveConfigAccess();

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-text-primary">
          Create leave type
        </h2>
        <p className="text-text-secondary">Name it, and decide who it applies to and how it is requested.</p>
      </div>

      <LeaveTypeForm />
    </div>
  );
}
