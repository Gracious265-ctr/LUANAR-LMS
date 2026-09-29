import { redirect } from "next/navigation";

import { PendingApplicationsTable } from "@/components/hr/pending-applications-table";
import { ReassignmentTable } from "@/components/hr/reassignment-table";
import { getCurrentUser } from "@/lib/auth";
import {
  listPendingApplications,
  listReassignments,
} from "@/lib/reassignments";

export default async function ReassignmentsPage() {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (user.role !== "hr") {
    redirect("/dashboard");
  }

  let pending;
  let pendingError = "";
  try {
    pending = await listPendingApplications();
  } catch {
    pendingError = "Unable to load pending applications. Please try again.";
  }

  let history;
  let historyError = "";
  try {
    history = await listReassignments();
  } catch {
    historyError = "Unable to load reassignment history. Please try again.";
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold tracking-tight text-text-primary">Reassignments</h2>
        <p className="text-text-secondary">
          Intervene on pending leave applications: reassign them to a replacement
          approver with a mandatory reason, and review the reassignment history.
        </p>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <h3 className="mb-4 text-lg font-semibold text-text-primary">
          Pending applications
        </h3>
        {pendingError ? (
          <div className="rounded-md bg-status-rejected-subtle py-12 text-center text-sm text-status-rejected">
            {pendingError}
          </div>
        ) : pending ? (
          <PendingApplicationsTable applications={pending.results} />
        ) : null}
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <h3 className="mb-4 text-lg font-semibold text-text-primary">
          Reassignment history
        </h3>
        {historyError ? (
          <div className="rounded-md bg-status-rejected-subtle py-12 text-center text-sm text-status-rejected">
            {historyError}
          </div>
        ) : history ? (
          <ReassignmentTable reassignments={history.results} />
        ) : null}
      </div>
    </div>
  );
}