import { redirect } from "next/navigation";

import { ReassignmentsSection } from "@/components/hr/ReassignmentsSection";
import { ReassignmentTable } from "@/components/hr/reassignment-table";
import { getCurrentUser } from "@/lib/auth";
import type { Employee } from "@/lib/employees";
import { listAllEmployees } from "@/lib/employees";
import {
  listPendingApplications,
  listReassignments,
} from "@/lib/reassignments";
import { Card } from "@/components/ui/card";
import { FadeIn } from "@/components/motion/FadeIn";

/**
 * The reassignment queue and its history.
 *
 * Reassigning happens in an overlay on the pending card; the old
 * `reassignments/new` route redirects here with the application id. The whole
 * employee list — what the overlay's picker needs — is fetched only while that
 * overlay is open, so a plain visit to this page does not pay for it.
 */
export default async function ReassignmentsPage({
  searchParams,
}: {
  searchParams: Promise<{ reassign?: string | string[] }>;
}) {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (user.role !== "hr") {
    redirect("/dashboard");
  }

  const { reassign } = await searchParams;
  const reassignId = typeof reassign === "string" ? reassign : "";

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

  let employees: Employee[] = [];
  let employeesError = "";
  if (reassignId) {
    try {
      // Whole list, not page one: a truncated picker would read to HR as
      // "nobody else can be chosen".
      employees = await listAllEmployees();
    } catch {
      employeesError = "Unable to load people for the approver list.";
    }
  }

  return (
    <FadeIn>
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold tracking-tight text-text-primary">
            Reassignments
          </h2>
          <p className="text-text-secondary">
            Intervene on pending leave applications: reassign them to a replacement
            approver with a mandatory reason, and review the reassignment history.
          </p>
        </div>

        <ReassignmentsSection
          applications={pending?.results ?? []}
          employees={employees}
          employeesError={employeesError}
          error={pendingError}
        />

        <Card>
          <h3 className="mb-4 text-lg font-semibold text-text-primary">
            Reassignment history
          </h3>
          {historyError ? (
            <div className="rounded-lg bg-status-rejected-subtle py-12 text-center text-sm text-status-rejected">
              {historyError}
            </div>
          ) : history ? (
            <ReassignmentTable reassignments={history.results} />
          ) : null}
        </Card>
      </div>
    </FadeIn>
  );
}
