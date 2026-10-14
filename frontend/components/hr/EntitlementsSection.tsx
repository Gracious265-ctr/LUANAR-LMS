"use client";

import { useRouter } from "next/navigation";

import { Plus } from "lucide-react";

import type { Entitlement } from "@/lib/entitlements";
import { useOverlayParam } from "@/lib/hooks/useOverlayParam";
import { AdminFormOverlay } from "@/components/hr/AdminFormOverlay";
import { EntitlementForm } from "@/components/hr/entitlement-form";
import { EntitlementTable } from "@/components/hr/entitlement-table";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

/** Query key for the entitlement overlay on the list page. */
export const ENTITLEMENT_PARAM = "entitlement";

/**
 * The entitlement registry as a create/edit overlay.
 *
 * Edit mode resolves the record from the rows already on screen: the table
 * carries the whole grade band, so there is no per-record request.
 *
 * This list has no filter of its own. `?grade` on the page is a lookup that
 * answers "what does this grade get", not a narrowing of the table, so no
 * row can be hidden out from under the overlay and there is no not-found case
 * beyond an id that matches nothing at all.
 */
export function EntitlementsSection({
  entitlements,
  today,
}: {
  entitlements: Entitlement[];
  /**
   * Passed down from the server page rather than read at render time, so the
   * server stays the clock authority for "current" versus "scheduled" instead
   * of each visitor's browser deciding it.
   */
  today?: string;
}) {
  const router = useRouter();
  const overlay = useOverlayParam(ENTITLEMENT_PARAM);

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

            <EntitlementTable
        entitlements={entitlements}
        today={today}
        onEdit={overlay.openEdit}
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
            : "Define an annual leave entitlement for a grade range that is not already covered. To change an existing band, edit that rule instead."
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
