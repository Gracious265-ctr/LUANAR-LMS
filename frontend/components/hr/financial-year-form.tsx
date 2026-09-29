"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import type { FinancialYear } from "@/lib/financial-years";
import {
  createFinancialYear,
  updateFinancialYear,
} from "@/lib/financial-years-client";
import { Field } from "@/components/ui/input";
import { DateRangePicker } from "@/components/ui/date-picker";
import { Button, buttonVariants } from "@/components/ui/button";
import { FormError } from "@/components/ui/form-error";

export function FinancialYearForm({
  financialYear,
}: {
  financialYear?: FinancialYear;
}) {
  const router = useRouter();
  const [startDate, setStartDate] = useState(financialYear?.start_date ?? "");
  const [endDate, setEndDate] = useState(financialYear?.end_date ?? "");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);

    const formData = new FormData(event.currentTarget);

    // The picker is a popover trigger, so the browser can no longer enforce
    // `required` for it; check here instead of dropping the guarantee.
    if (!startDate || !endDate) {
      setError("Choose the full period.");
      setLoading(false);
      return;
    }

    try {
      const input = {
        start_date: String(formData.get("start_date") || ""),
        end_date: String(formData.get("end_date") || ""),
        is_active: Boolean(formData.get("is_active")),
      };
      if (financialYear) {
        await updateFinancialYear(financialYear.id, input);
      } else {
        await createFinancialYear(input);
      }
      router.push("/dashboard/hr-admin/calendar");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-4 md:grid-cols-2">
      <Field
        label="Period"
        htmlFor="start_date"
        hint="Periods must not overlap each other."
      >
        <DateRangePicker
          id="start_date"
          from={startDate}
          to={endDate}
          onRangeChange={(from, to) => {
            setStartDate(from);
            setEndDate(to);
          }}
        />
        {/* The trigger is a <button>, so the names still have to reach FormData. */}
        <input type="hidden" name="start_date" value={startDate} />
        <input type="hidden" name="end_date" value={endDate} />
      </Field>

      <div className="flex items-center gap-2 md:col-span-2">
        <input
          id="is_active"
          name="is_active"
          type="checkbox"
          defaultChecked={financialYear?.is_active ?? false}
          className="h-4 w-4 rounded border-input-border text-brand-primary focus:ring-input-ring-focus"
        />
        <label
          htmlFor="is_active"
          className="text-sm font-medium text-text-primary"
        >
          Active financial year
        </label>
      </div>
      <p className="text-xs text-text-muted md:col-span-2">
        Exactly one financial year is active at a time. Checking this deactivates
        the currently active period. Unchecking it leaves no active period; the
        system uses the active financial year when validating leave applications.
      </p>

      {error && (
        <FormError className="md:col-span-2">{error}</FormError>
      )}

      <div className="flex items-center gap-3 md:col-span-2">
        <Button type="submit" variant="primary" loading={loading}>
          {loading ? "Saving..." : financialYear ? "Save changes" : "Create financial year"}
        </Button>
        <Link
          href="/dashboard/hr-admin/calendar"
          className={buttonVariants({ variant: "secondary" })}
        >
          Cancel
        </Link>
      </div>
    </form>
  );
}