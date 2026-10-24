"use client";

import type { ReactNode } from "react";
import { useState } from "react";
import { useRouter } from "next/navigation";

import { Plus } from "lucide-react";

import type { FinancialYear, Holiday } from "@/lib/financial-years";
import { useOverlayParam } from "@/lib/hooks/useOverlayParam";
import { AdminFormOverlay } from "@/components/hr/AdminFormOverlay";
import { Alert } from "@/components/ui/alert";
import { HolidayForm } from "@/components/hr/holiday-form";
import { HolidayTable } from "@/components/hr/holiday-table";
import { Button } from "@/components/ui/button";

/** Query key for the holiday overlay. Distinct from `?year` and `?event`. */
export const HOLIDAY_PARAM = "holiday";

/**
 * The holidays half of the calendar, as a create/edit overlay.
 *
 * This is the one host whose list is filtered. `?year` narrows the table, so two
 * states are reachable but unresolvable: deep-linking a holiday the active
 * filter excludes finds no row even though the record exists, and a holiday
 * created while filtered may not appear in the table afterwards. Neither is
 * papered over by silently clearing the filter — an admin who narrowed the view
 * would lose it without being asked. Both surface a message instead, and the
 * not-found state offers the way back.
 */
export function HolidaysSection({
  holidays,
  financialYears = [],
  yearFilter,
  filter,
}: {
  holidays: Holiday[];
  financialYears?: FinancialYear[];
  /** The page's active `?year` filter, used only to explain the not-found case. */
  yearFilter: string;
  /**
   * The page's year filter, rendered between the header and the table it
   * narrows. Passed in as a slot because the filter is a GET form the server
   * page owns, while the header, table, and overlay belong together here.
   */
  filter?: ReactNode;
}) {
  const router = useRouter();
  const overlay = useOverlayParam(HOLIDAY_PARAM);
  // The id of a holiday created in this session. Whether it is actually
  // invisible is decided from the list the server sends back, not from the
  // date the admin typed: `?year` is applied server-side, so this stays
  // correct if that filter ever widens.
  const [createdId, setCreatedId] = useState<number | null>(null);
  const createdHidden =
    createdId !== null && !holidays.some((row) => row.id === createdId);

  const editing =
    overlay.target !== null && !overlay.isCreate
      ? holidays.find((row) => String(row.id) === overlay.target)
      : undefined;

  const filteredOut =
    editing === undefined && !overlay.isCreate && yearFilter !== "";

  return (
    <>
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-text-primary">Holidays</h3>
          <p className="mt-1 text-sm text-text-secondary">
            Dates that should not count as working leave days.
          </p>
        </div>
        <Button variant="primary" onClick={overlay.openCreate} className="shrink-0">
          <Plus className="h-4 w-4" />
          New holiday
        </Button>
      </div>

      {filter}

      {createdHidden && (
        <Alert tone="info" className="mb-4 flex-col items-start">
          <p>
            Saved, but it is not in this table. The page is filtered to{" "}
            {yearFilter} and that date falls outside it.
          </p>
          <button
            type="button"
            onClick={() => router.push(overlay.hrefWithoutParam)}
            className="mt-2 rounded-md px-2 py-1.5 text-sm font-medium text-brand-primary hover:text-brand-primary-hover"
          >
            Show all years
          </button>
        </Alert>
      )}

      <HolidayTable
        holidays={holidays}
        financialYears={financialYears}
        onEdit={overlay.openEdit}
      />

      <AdminFormOverlay
        open={overlay.isOpen}
        title={
          editing
            ? `Edit ${editing.name}`
            : overlay.isCreate
              ? "New holiday"
              : "Edit holiday"
        }
        description={
          editing
            ? "Update the holiday, its recurrence, or its financial-year scope."
            : "Add a date that should not count as working leave days."
        }
        onOpenChange={(open) => {
          if (!open) overlay.close();
        }}
        notFound={
          filteredOut
            ? `This holiday is not in the ${yearFilter} view, because the page is filtered to that year.`
            : editing === undefined && !overlay.isCreate
              ? "That holiday is no longer in the list. It may have been deleted."
              : undefined
        }
        clearFiltersLabel="Show all years"
        onClearFilters={filteredOut ? () => router.push(overlay.hrefWithoutParam) : undefined}
      >
        <HolidayForm
          holiday={editing}
          financialYears={financialYears}
          onSuccess={(saved) => {
            setCreatedId(saved.id);
            overlay.close();
            router.refresh();
          }}
          onCancel={overlay.close}
        />
      </AdminFormOverlay>
    </>
  );
}
