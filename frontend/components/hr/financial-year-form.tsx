"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import type { FinancialYear } from "@/lib/financial-years";
import {
  createFinancialYear,
  updateFinancialYear,
} from "@/lib/financial-years-client";

export function FinancialYearForm({
  financialYear,
}: {
  financialYear?: FinancialYear;
}) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);

    const formData = new FormData(event.currentTarget);

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
      <div>
        <label
          htmlFor="start_date"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Start date
        </label>
        <input
          id="start_date"
          name="start_date"
          type="date"
          required
          defaultValue={financialYear?.start_date}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
        />
      </div>

      <div>
        <label
          htmlFor="end_date"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          End date
        </label>
        <input
          id="end_date"
          name="end_date"
          type="date"
          required
          defaultValue={financialYear?.end_date}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
        />
        <p className="mt-1 text-xs text-text-muted">
          Periods must not overlap each other.
        </p>
      </div>

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
        <div className="rounded-md bg-status-rejected-subtle p-3 text-sm text-status-rejected md:col-span-2">
          {error}
        </div>
      )}

      <div className="flex items-center gap-3 md:col-span-2">
        <button
          type="submit"
          disabled={loading}
          className="rounded-md bg-button-primary px-4 py-2 font-medium text-button-primary-foreground hover:bg-button-primary-hover focus:outline-none focus:ring-2 focus:ring-input-ring-focus disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Saving..." : financialYear ? "Save changes" : "Create financial year"}
        </button>
        <Link
          href="/dashboard/hr-admin/calendar"
          className="rounded-md border border-border-default bg-button-secondary px-4 py-2 font-medium text-text-secondary hover:bg-button-secondary-hover"
        >
          Cancel
        </Link>
      </div>
    </form>
  );
}