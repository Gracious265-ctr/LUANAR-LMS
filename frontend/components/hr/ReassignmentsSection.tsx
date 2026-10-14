"use client";

import { useRouter } from "next/navigation";

import type { Employee } from "@/lib/employees";
import type { PendingApplication } from "@/lib/reassignments";
import { useOverlayParam } from "@/lib/hooks/useOverlayParam";
import { AdminFormOverlay } from "@/components/hr/AdminFormOverlay";
import { PendingApplicationsTable } from "@/components/hr/pending-applications-table";
import { ReassignmentForm } from "@/components/hr/reassignment-form";
import { Card } from "@/components/ui/card";

/** Query key for the reassignment overlay on the list page. */
export const REASSIGN_PARAM = "reassign";

/**
 * The pending-applications queue as a reassign overlay.
 *
 * Edit mode resolves the application from the row already on screen rather
 * than fetching it: the row carries the same record the standalone form read
 * from the pending list, so there is no per-record request and no loading
 * state — only the one case where the id in the URL matches no pending row,
 * which is also what a stale link to an application that has since been
 * assigned or decided produces.
 *
 * The employee list is different: the picker needs the whole staff, so the
 * page fetches it only while the overlay is open rather than on every visit
 * to a page whose queue does not otherwise need it.
 */
export function ReassignmentsSection({
  applications,
  employees,
  employeesError = "",
  error = "",
}: {
  applications: PendingApplication[];
  /** Whole staff, for the picker. Empty when the fetch failed or is unrun. */
  employees: Employee[];
  /** Set when the people fetch failed; the form is then replaced by a banner. */
  employeesError?: string;
  /** Set when the pending queue itself failed to load. */
  error?: string;
}) {
  const router = useRouter();
  const overlay = useOverlayParam(REASSIGN_PARAM);

  const editing =
    overlay.target !== null
      ? applications.find((row) => String(row.id) === overlay.target)
      : undefined;

  return (
    <Card>
      <h3 className="mb-4 text-lg font-semibold text-text-primary">
        Pending applications
      </h3>

      {error ? (
        <div className="rounded-lg bg-status-rejected-subtle py-12 text-center text-sm text-status-rejected">
          {error}
        </div>
      ) : (
        <PendingApplicationsTable
          applications={applications}
          onReassign={(application) => overlay.openEdit(application.id)}
        />
      )}

      <AdminFormOverlay
        open={overlay.isOpen}
        targetKey={overlay.target}
        title={
          editing
            ? `Reassign ${editing.reference_number || editing.employee_name}`
            : "Reassign application"
        }
        description="Transfer a pending application to a replacement approver and record the mandatory reassignment reason."
        onOpenChange={(open) => {
          if (!open) overlay.close();
        }}
        notFound={
          editing === undefined
            ? "That application is no longer in the pending queue. It may have been assigned an approver or decided already."
            : undefined
        }
      >
        {employeesError ? (
          <div className="rounded-md bg-status-rejected-subtle p-3 text-sm text-status-rejected">
            {employeesError}
          </div>
        ) : (
          /* `notFound` above renders instead of this branch whenever `editing`
             is undefined, so the form only ever mounts with a record. */
          editing && (
            <ReassignmentForm
              application={editing}
              employees={employees}
              onSuccess={() => {
                overlay.close();
                router.refresh();
              }}
              onCancel={overlay.close}
            />
          )
        )}
      </AdminFormOverlay>
    </Card>
  );
}
