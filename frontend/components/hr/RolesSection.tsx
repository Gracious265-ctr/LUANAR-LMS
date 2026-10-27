"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { Plus } from "lucide-react";

import type {
  ApproverRole,
  CampusRoleAssignment,
  RoleAssignment,
  TeamRoleAssignment,
} from "@/lib/approver-roles";
import { useOverlayParam } from "@/lib/hooks/useOverlayParam";
import { matchesSearch } from "@/lib/search";
import { AdminFormOverlay } from "@/components/hr/AdminFormOverlay";
import { ApproverRoleForm } from "@/components/hr/approver-role-form";
import { ApproverRoleTable } from "@/components/hr/approver-role-table";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/states";
import { FilterChips } from "@/components/ui/filter-chips";
import { ListSearch } from "@/components/ui/list-search";

/** Query key for the approver-role overlay on the list page. */
export const APPROVER_ROLE_PARAM = "role";

/** State narrowing for the registry. Labels stay distinct from the row badge. */
const STATE_FILTERS = [
  { value: "", label: "All roles" },
  { value: "active", label: "Active only" },
  { value: "retired", label: "Retired only" },
] as const;

type StateFilter = (typeof STATE_FILTERS)[number]["value"];

/**
 * The approver-role registry as a create/edit overlay.
 *
 * Create and edit both resolve on the page rather than on a route of their own:
 * the table already carries every role, so there is no per-record request and
 * `?role=new` / `?role=<id>` is all the state the overlay needs. The old
 * `new` / `[id]/edit` routes survive as shims that redirect here, so a
 * bookmarked URL still lands on the form.
 *
 * Retired roles stay listed and stay editable — HR needs to see that a role
 * exists and why. The local search and state chips narrow what the table draws,
 * not what the overlay resolves against, so a `?role=<id>` deep link still opens
 * a row the current filter hides; the not-found case stays an id that matches
 * nothing at all.
 *
 * The institution-wide holder block below the table is deliberately not part of
 * this section: `RoleAssignmentForm` is a per-role widget rather than a
 * create/edit form, and it stays inline on the page. The team- and campus-wide
 * holdings are different: they are columns on the table, so they travel through
 * here to the table that reads them.
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
  const [search, setSearch] = useState("");
  const [state, setState] = useState<StateFilter>("");

  const visibleRoles = useMemo(
    () =>
      roles.filter((role) => {
        if (state === "active" && !role.is_active) return false;
        if (state === "retired" && role.is_active) return false;
        return matchesSearch(search, [
          role.label,
          role.code,
          role.description,
          role.is_active ? "active" : "retired",
          role.history_scope,
          role.is_institution_wide ? "institution-wide" : "team role",
          ...role.usage,
        ]);
      }),
    [roles, search, state]
  );

  // Editing resolves against the whole registry: narrowing the table must not
  // make a live `?role=<id>` deep link read as a row that no longer exists.
  const editing =
    overlay.target !== null && !overlay.isCreate
      ? roles.find((row) => String(row.id) === overlay.target)
      : undefined;

  return (
    <>
      <div className="mb-4 flex items-start justify-between gap-4">
        <h3 className="text-lg font-semibold text-text-primary">All roles</h3>
        <Button
          variant="primary"
          onClick={overlay.openCreate}
          className="shrink-0"
        >
          <Plus className="h-4 w-4" />
          New role
        </Button>
      </div>

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <ListSearch
          value={search}
          onChange={setSearch}
          label="Search approver roles"
          placeholder="Search by role, code, or description"
          className="w-full sm:w-80"
        />
        <FilterChips
          label="Filter approver roles by state"
          options={STATE_FILTERS}
          value={state}
          onChange={setState}
        />
      </div>

      <ApproverRoleTable
        roles={visibleRoles}
        assignments={assignments}
        teamHoldings={teamHoldings}
        campusHoldings={campusHoldings}
        teamNameById={teamNameById}
        campusNameById={campusNameById}
        onEdit={overlay.openEdit}
        empty={
          search || state ? (
            <EmptyState
              title="No roles match this search"
              description="Try a different role, code, description, or state."
            />
          ) : undefined
        }
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
    </>
  );
}
