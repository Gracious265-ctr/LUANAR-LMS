"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import type { FinancialYear, Holiday } from "@/lib/financial-years";
import { createHoliday, updateHoliday } from "@/lib/financial-years-client";
import { Input, Field } from "@/components/ui/input";
import { DatePicker } from "@/components/ui/date-picker";
import { Button, buttonVariants } from "@/components/ui/button";
import { FormError } from "@/components/ui/form-error";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export function HolidayForm({
  holiday,
  financialYears = [],
  onSuccess,
  onCancel,
}: {
  holiday?: Holiday;
  /** Options for scoping the holiday to a financial year. */
  financialYears?: FinancialYear[];
  /** Replaces the default `router.push(listRoute)` + `router.refresh()`. */
  onSuccess?: (holiday: Holiday) => void;
  /** Adds a dismiss action; an inline page form has nothing to dismiss to. */
  onCancel?: () => void;
}) {
  const router = useRouter();
  const [date, setDate] = useState(holiday?.date ?? "");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);

    const formData = new FormData(event.currentTarget);

    // The picker is a popover trigger, so the browser can no longer enforce
    // `required` for it; check here instead of dropping the guarantee.
    if (!date) {
      setError("Choose a date.");
      setLoading(false);
      return;
    }

    try {
      const year = String(formData.get("financial_year") || "");
      const input = {
        name: String(formData.get("name") || "").trim(),
        date: String(formData.get("date") || ""),
        is_recurring: formData.get("is_recurring") !== null,
        observed_shift: formData.get("observed_shift") !== null,
        financial_year: year ? Number(year) : null,
      };
      const saved = holiday
        ? await updateHoliday(holiday.id, input)
        : await createHoliday(input);
      if (onSuccess) {
        onSuccess(saved);
      } else {
        router.push("/dashboard/hr-admin/calendar?tab=holidays");
        router.refresh();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-4 md:grid-cols-2">
      <Field label="Name" htmlFor="name">
        <Input
          id="name"
          name="name"
          required
          defaultValue={holiday?.name}
          placeholder="e.g. Independence Day"
        />
      </Field>

      <Field
        label="Date"
        htmlFor="date"
        hint="For a recurring holiday this is the reference date."
      >
        <DatePicker id="date" value={date} onChange={setDate} />
        {/* The trigger is a <button>, so the name still has to reach FormData. */}
        <input type="hidden" name="date" value={date} />
      </Field>

      <Field
        label="Financial year"
        htmlFor="financial_year"
        hint="Leave blank for an institution-wide holiday."
      >
        <Select
          name="financial_year"
          defaultValue={
            holiday?.financial_year != null ? String(holiday.financial_year) : ""
          }
        >
          <SelectTrigger id="financial_year">
            <SelectValue placeholder="Institution-wide" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="">Institution-wide</SelectItem>
            {financialYears.map((year) => (
              <SelectItem key={year.id} value={String(year.id)}>
                {year.start_date} – {year.end_date}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>

      <div className="flex flex-col justify-center gap-2 text-sm text-text-primary">
        <label className="flex items-center gap-2">
          <input
            id="is_recurring"
            name="is_recurring"
            type="checkbox"
            defaultChecked={holiday?.is_recurring ?? true}
            className="h-4 w-4 rounded border-input-border text-brand-primary focus:ring-input-ring-focus"
          />
          Repeats every year on this date
        </label>
        <label className="flex items-center gap-2">
          <input
            id="observed_shift"
            name="observed_shift"
            type="checkbox"
            defaultChecked={holiday?.observed_shift ?? true}
            className="h-4 w-4 rounded border-input-border text-brand-primary focus:ring-input-ring-focus"
          />
          Shift to the nearest working day when it falls on a non-working day
        </label>
      </div>

      {error && (
        <FormError className="md:col-span-2">{error}</FormError>
      )}

      <div className="flex items-center gap-3 md:col-span-2">
        <Button type="submit" variant="primary" loading={loading}>
          {loading ? "Saving..." : holiday ? "Save changes" : "Create holiday"}
        </Button>
        {onCancel ? (
          <Button type="button" variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
        ) : (
          <Link
            href="/dashboard/hr-admin/calendar?tab=holidays"
            className={buttonVariants({ variant: "secondary" })}
          >
            Cancel
          </Link>
        )}
      </div>
    </form>
  );
}
