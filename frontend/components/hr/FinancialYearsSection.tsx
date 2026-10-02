"use client";

import { useRouter } from "next/navigation";

import { Plus } from "lucide-react";

import type { FinancialYear } from "@/lib/financial-years";
import { useOverlayParam } from "@/lib/hooks/useOverlayParam";
import { AdminFormOverlay } from "@/components/hr/AdminFormOverlay";
import { FinancialYearForm } from "@/components/hr/financial-year-form";
import { FinancialYearTable } from "@/components/hr/financial-year-table";
import { Button } from "@/components/ui/button";

/** Query key for the financial-year overlay. Shares the calendar page with `holiday`. */
export const FINANCIAL_YEAR_PARAM = "financialYear";

/**
 * The financial-years half of the leave calendar, as a create/edit overlay.
 *
 * The dialog description carries the one warning this form needs: activating a
 * period deactivates whichever one was active, and in a two-field dialog with
 * no surrounding context that is easy to toggle without meaning to. The form's
 * own help text says the same thing below the checkbox; it is repeated up top
 * because the dialog header is what is read before touching anything.
 *
 * The warning is attached to the rows where ticking the box actually causes a
 * side effect, which is the opposite of the intuitive test. Editing the period
 * that is already active has nothing to deactivate, so a warning there would be
 * noise; creating a period, or editing an inactive one, silently retires
 * whichever period is live.
 */
export function FinancialYearsSection({ years }: { years: FinancialYear[] }) {
  const router = useRouter();
  const overlay = useOverlayParam(FINANCIAL_YEAR_PARAM);

  const editing =
    overlay.target !== null && !overlay.isCreate
      ? years.find((row) => String(row.id) === overlay.target)
      : undefined;

  const canActivate = overlay.isCreate || (editing !== undefined && !editing.is_active);
  const activationWarning = !canActivate
    ? ""
    : overlay.isCreate
      ? " Exactly one financial year is active at a time; creating this one active deactivates the period that is active now."
      : " Exactly one financial year is active at a time; activating this period deactivates the one that is active now.";

  return (
    <>
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-text-primary">
            Financial years
          </h3>
          <p className="mt-1 text-sm text-text-secondary">
            Exactly one period is active at a time; future periods are
            scheduled by activating them.
          </p>
        </div>
        <Button variant="primary" onClick={overlay.openCreate} className="shrink-0">
          <Plus className="h-4 w-4" />
          New financial year
        </Button>
      </div>

      <FinancialYearTable years={years} onEdit={overlay.openEdit} />

      <AdminFormOverlay
        open={overlay.isOpen}
        title={
          editing
            ? `Edit financial year ${editing.start_date}`
            : overlay.isCreate
              ? "New financial year"
              : "Edit financial year"
        }
        description={
          (editing
            ? "Update the period. Periods must not overlap each other."
            : "Set the period the system validates leave applications against. Periods must not overlap each other.") +
          activationWarning
        }
        onOpenChange={(open) => {
          if (!open) overlay.close();
        }}
        notFound={
          editing === undefined && !overlay.isCreate
            ? "That financial year is no longer in the list. It may have been deleted."
            : undefined
        }
      >
        <FinancialYearForm
          financialYear={editing}
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
