"use client";

import { useRouter } from "next/navigation";

import { Plus } from "lucide-react";

import type { ApproverRole, CampusRoleAssignment, RoleAssignment, TeamRoleAssignment } from "@/lib/approver-roles";
import { useOverlayParam } from "@/lib/hooks/useOverlayParam";
import { AdminFormOverlay } from "@/components/hr/AdminFormOverlay";
import { ApproverRoleForm } from "@/components/hr/approver-role-form";
import { ApproverRoleTable } from "@/components/hr/approver-role-table";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

/** Query key for the approver-role overlay on the list page. */
export const APPROVER_ROLE_PARAM = "role";

/**
 * The approver-role registry as a create/edit overlay.
 *
 * Edit mode resolves the record from the rows already on screen: the table
 * carries the whole role, so there is no per-record request.
 *
 * Retired roles stay listed and stay editable — HR needs to see that a role
 * exists and why — so this list has no filter that could hide a row and no
 * not-found case beyond an id that matches nothing.
 *
 * The institution-wide holder block below the table is deliberately not part of
 * this section: `RoleAssignmentForm` is a per-role widget rather than a
 * create/edit form, and it stays inline on the page.
 */
export function RolesSection({
  roles,
  assignments,
  teamHoldings,
  campusHoldings,
  teamNameById,
  campusNameById,
}: {
  roles: ApproverRole[];
  /**
   * Institution-wide holdings keyed by role id. The table's holders column reads
   * this, so it has to travel with the rows rather than being dropped.
   */
  assignments?: Record<number, RoleAssignment[]>;
  /** Team-wide holdings, keyed by role id. Absent means "none". */
  teamHoldings?: Record<number, TeamRoleAssignment[]>;
  /** Campus-wide holdings, keyed by role id. Absent means "none". */
  campusHoldings?: Record<number, CampusRoleAssignment[]>;
  /** Team names, keyed by team id, so a team-wide holder reads as a person. */
  teamNameById?: Record<number, string>;
  /** Campus names, keyed by campus id, so a campus-wide holder reads as a person. */
  campusNameById?: Record<number, string>;
}) {
  const router = useRouter();
  const overlay = useOverlayParam(APPROVER_ROLE_PARAM);

  const editing =
    overlay.target !== null && !overlay.isCreate
      ? roles.find((row) => String(row.id) === overlay.target)
      : undefined;

  return (
    <Card>
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-text-primary">
            Approver roles
          </h3>
          <p className="mt-1 text-sm text-text-secondary">
            Roles decide which steps a workflow runs through and who may act at
            each one.
          </p>
        </div>
        <Button
          variant="primary"
          onClick={overlay.openCreate}
          className="shrink-0"
        >
          <Plus className="h-4 w-4" />
          New role
        </Button>
      </div>

            <ApproverRoleTable
        roles={roles}
        assignments={assignments}
        teamHoldings={teamHoldings}
        campusHoldings={campusHoldings}
        teamNameById={teamNameById}
        campusNameById={campusNameById}
        onEdit={overlay.openEdit}
      />

      <AdminFormOverlay
        open={overlay.isOpen}
        targetKey={overlay.target}
        size="md"
        title={
          editing
            ? `Edit ${editing.label}`
            : overlay.isCreate
              ? "New approver role"
              : "Edit approver role"
        }
        description={
          editing
            ? "The code is fixed once saved, because saved workflow sections and team memberships refer to it."
            : "Give the role a code and label, then choose which workflow steps it handles. The code is derived from the label when left blank."
        }
        onOpenChange={(open) => {
          if (!open) overlay.close();
        }}
        notFound={
          editing === undefined && !overlay.isCreate
            ? "That role is no longer in the list. It may have been deleted."
            : undefined
        }
      >
        <ApproverRoleForm
          role={editing}
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
