"use client";

import { useRouter } from "next/navigation";

import { Plus } from "lucide-react";

import type { LeaveType } from "@/lib/leave-rules";
import { useOverlayParam } from "@/lib/hooks/useOverlayParam";
import { AdminFormOverlay } from "@/components/hr/AdminFormOverlay";
import { LeaveTypeForm } from "@/components/hr/leave-type-form";
import { LeaveTypeTable } from "@/components/hr/leave-type-table";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

/** Query key for the leave-type overlay on the list page. */
export const LEAVE_TYPE_PARAM = "leaveType";

/**
 * The leave-types registry as a create/edit overlay.
 *
 * Edit mode resolves the record from the rows already on screen rather than
 * fetching it: the table holds `name` and `code`, which is the whole form. So
 * there is no per-record request, no loading state, and no not-found fetch
 * path — only the one case where the id in the URL matches no row.
 *
 * The row's name still links to `/edit`, which is now a redirect shim. Keeping
 * it a real link preserves middle-click and copy-link, and the shim means it
 * lands on the same overlay; the pencil is the direct path.
 */
export function LeaveTypesSection({ leaveTypes }: { leaveTypes: LeaveType[] }) {
  const router = useRouter();
  const overlay = useOverlayParam(LEAVE_TYPE_PARAM);

  const editing =
    overlay.target !== null && !overlay.isCreate
      ? leaveTypes.find((row) => String(row.id) === overlay.target)
      : undefined;

  return (
    <Card>
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-text-primary">
            Leave types
          </h3>
          <p className="mt-1 text-sm text-text-secondary">
            Manage the registry of leave types the university offers. Leave
            rules for each type are configured from the Leave Rules page.
          </p>
        </div>
        <Button variant="primary" onClick={overlay.openCreate} className="shrink-0">
          <Plus className="h-4 w-4" />
          New leave type
        </Button>
      </div>

      <LeaveTypeTable leaveTypes={leaveTypes} onEdit={overlay.openEdit} />

      <AdminFormOverlay
        open={overlay.isOpen}
        title={
          editing
            ? `Edit ${editing.name}`
            : overlay.isCreate
              ? "New leave type"
              : "Edit leave type"
        }
        description={
          editing
            ? "Update the name or code. Applications already filed keep the name they were filed under."
            : "Add a leave type such as annual, maternity, or a university-specific type. The code is optional and derived from the name when left blank."
        }
        onOpenChange={(open) => {
          if (!open) overlay.close();
        }}
        notFound={
          editing === undefined && !overlay.isCreate
            ? "That leave type is no longer in the list. It may have been deleted."
            : undefined
        }
      >
        <LeaveTypeForm
          leaveType={editing}
          onSuccess={() => {
            overlay.close();
            router.refresh();
          }}
          onCancel={overlay.close}
        />
      </AdminFormOverlay>
    </Card>
  );
}
