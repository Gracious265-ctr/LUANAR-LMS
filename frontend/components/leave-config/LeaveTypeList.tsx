"use client";

import { useMemo, useState } from "react";

import {
  branchScopeLabel,
  type LeaveType,
} from "@/lib/leave-config";
import { matchesSearch } from "@/lib/search";
import { EmptyState } from "@/components/ui/states";
import { ListSearch } from "@/components/ui/list-search";

import { LeaveTypeTable } from "./LeaveTypeTable";

/**
 * The registry table with a local search.
 *
 * The page still owns the fetch and the active/retired navigation — this only
 * narrows what the server already sent. Keeping the search in the browser means
 * typing does not re-run the list query, and the "Show inactive" link stays the
 * one thing that changes what the server returns.
 */
export function LeaveTypeList({ leaveTypes }: { leaveTypes: LeaveType[] }) {
  const [search, setSearch] = useState("");

  const visible = useMemo(
    () =>
      leaveTypes.filter((leaveType) =>
        matchesSearch(search, [
          leaveType.name,
          leaveType.code,
          leaveType.description,
          branchScopeLabel(leaveType.branch_scope),
          leaveType.is_active ? "active" : "inactive",
        ])
      ),
    [leaveTypes, search]
  );

  return (
    <div className="space-y-4">
      <ListSearch
        value={search}
        onChange={setSearch}
        label="Search leave types"
        placeholder="Search by name, code, or branch scope"
        className="w-full sm:w-80"
      />
      <LeaveTypeTable
        leaveTypes={visible}
        empty={
          search ? (
            <EmptyState
              title="No leave types match this search"
              description="Try a different name, code, or branch scope."
            />
          ) : undefined
        }
      />
    </div>
  );
}
