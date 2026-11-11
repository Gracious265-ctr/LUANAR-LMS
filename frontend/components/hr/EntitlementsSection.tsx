"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { Plus } from "lucide-react";

import type { Entitlement } from "@/lib/entitlements";
import { useOverlayParam } from "@/lib/hooks/useOverlayParam";
import { matchesSearch } from "@/lib/search";
import { AdminFormOverlay } from "@/components/hr/AdminFormOverlay";
import { EntitlementForm } from "@/components/hr/entitlement-form";
import { EntitlementTable } from "@/components/hr/entitlement-table";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/states";
import { ListSearch } from "@/components/ui/list-search";

/** Query key for the entitlement overlay on the list page. */
export const ENTITLEMENT_PARAM = "entitlement";

/**
 * The entitlement registry as a create/edit overlay.
 *
 * Edit mode resolves the record from the rows already on screen: the table
 * carries the whole grade band, so there is no per-record request.
 *
 * This list's own narrowing is the local search, which filters grades, day
 * counts, leave types, and effective dates in the browser. `?grade` on the page
 * remains a separate lookup that answers "what does this grade get", not a
 * narrowing of the table. Editing resolves against every rule rather than the
 * searched view, so a hidden row still opens from `?entitlement=<id>` and there
 * is no not-found case beyond an id that matches nothing at all.
 */
export function EntitlementsSection({
  entitlements,
  today,
  basePath,
}: {
  entitlements: Entitlement[];
  /**
   * Passed down from the server page rather than read at render time, so the
   * server stays the clock authority for "current" versus "scheduled" instead
   * of each visitor's browser deciding it.
   */
  today?: string;
  /**
   * Base route for a row's edit link, e.g. `/leave-config/annual-days`. Omitted
   * on the HR-admin page so its historical deep links keep working.
   */
  basePath?: string;
}) {
  const router = useRouter();
  const overlay = useOverlayParam(ENTITLEMENT_PARAM);
  const [search, setSearch] = useState("");

  const visible = useMemo(
    () =>
      entitlements.filter((rule) => {
        const current = today ? rule.effective_from <= today : true;
        return matchesSearch(search, [
          rule.grade_start,
          rule.grade_end,
          `${rule.grade_start}-${rule.grade_end}`,
          rule.days,
          rule.leave_type_name,
          rule.effective_from,
          current ? "current" : "scheduled",
        ]);
      }),
    [entitlements, search, today]
  );

  // Editing resolves against every rule, not the narrowed view: a filter must
  // not make a live `?entitlement=<id>` deep link read as a deleted record.
  const editing =
    overlay.target !== null && !overlay.isCreate
      ? entitlements.find((row) => String(row.id) === overlay.target)
      : undefined;

  const band = editing ? `${editing.grade_start}–${editing.grade_end}` : null;

  return (
    <Card>
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-text-primary">
            Entitlement rules
          </h3>
          <p className="mt-1 text-sm text-text-secondary">
            Grade ranges must not overlap. To change an existing band, edit its
            rule instead of adding a second one.
          </p>
        </div>
        <Button
          variant="primary"
          onClick={overlay.openCreate}
          className="shrink-0"
        >
          <Plus className="h-4 w-4" />
          New entitlement
        </Button>
      </div>

      <ListSearch
        value={search}
        onChange={setSearch}
        label="Search entitlement rules"
        placeholder="Search by grade, days, leave type, or date"
        className="mb-4 w-full sm:w-80"
      />

      <EntitlementTable
        entitlements={visible}
        today={today}
        onEdit={overlay.openEdit}
        basePath={basePath}
        empty={
          search ? (
            <EmptyState
              title="No entitlement rules match this search"
              description="Try a different grade, number of days, leave type, or date."
            />
          ) : undefined
        }
      />

      <AdminFormOverlay
        open={overlay.isOpen}
        targetKey={overlay.target}
        title={
          band ? `Edit ${band}` : overlay.isCreate ? "New entitlement" : "Edit entitlement"
        }
        description={
          band
            ? "Update the annual days or the date this band takes effect. Grade ranges must not overlap, so a change that collides with another band is rejected."
            : undefined
        }
        onOpenChange={(open) => {
          if (!open) overlay.close();
        }}
        notFound={
          editing === undefined && !overlay.isCreate
            ? "That entitlement rule is no longer in the list. It may have been deleted."
            : undefined
        }
      >
        {editing && (
          <EntitlementForm
            entitlement={editing}
            endpoint={`/api/hr/entitlements/${editing.id}`}
            method="PATCH"
            onSuccess={() => {
              overlay.close();
              router.refresh();
            }}
            onCancel={overlay.close}
          />
        )}
        {overlay.isCreate && (
          <EntitlementForm
            endpoint="/api/hr/entitlements"
            method="POST"
            onSuccess={() => {
              overlay.close();
              router.refresh();
            }}
            onCancel={overlay.close}
          />
        )}
      </AdminFormOverlay>
    </Card>
  );
}
