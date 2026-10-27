"use client";

import { useMemo, useState } from "react";

import type { Reassignment } from "@/lib/reassignments";
import { matchesSearch } from "@/lib/search";
import { EmptyState } from "@/components/ui/states";
import { ListSearch } from "@/components/ui/list-search";

import { ReassignmentTable } from "./reassignment-table";

/**
 * The reassignment history with a local search.
 *
 * The page still owns the fetch; this only narrows what it already sent, so
 * typing costs no request. Reach for a reference or a person, which is what
 * HR actually remembers about a transfer, and both the old and new approver
 * are searchable — "who did this go to?" is the other half of the question.
 */
export function ReassignmentHistory({
  reassignments,
}: {
  reassignments: Reassignment[];
}) {
  const [search, setSearch] = useState("");

  const visible = useMemo(
    () =>
      reassignments.filter((row) =>
        matchesSearch(search, [
          row.reference_number,
          row.employee_name,
          row.from_approver_name,
          row.to_approver_name,
          row.reason,
          row.decided_by_name,
        ])
      ),
    [reassignments, search]
  );

  return (
    <div className="space-y-4">
      <ListSearch
        value={search}
        onChange={setSearch}
        label="Search reassignment history"
        placeholder="Search by reference, employee, approver, or reason"
        className="w-full sm:w-80"
      />
      <ReassignmentTable
        reassignments={visible}
        empty={
          search ? (
            <EmptyState
              title="No reassignments match this search"
              description="Try a different reference, employee, approver, or reason."
            />
          ) : undefined
        }
      />
    </div>
  );
}
