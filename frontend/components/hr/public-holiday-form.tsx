"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import type { PublicHoliday } from "@/lib/financial-years";
import {
  createPublicHoliday,
  updatePublicHoliday,
} from "@/lib/financial-years-client";

export function PublicHolidayForm({
  publicHoliday,
}: {
  publicHoliday?: PublicHoliday;
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
        name: String(formData.get("name") || "").trim(),
        date: String(formData.get("date") || ""),
      };
      if (publicHoliday) {
        await updatePublicHoliday(publicHoliday.id, input);
      } else {
        await createPublicHoliday(input);
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
          htmlFor="name"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Name
        </label>
        <input
          id="name"
          name="name"
          required
          defaultValue={publicHoliday?.name}
          placeholder="e.g. Independence Day"
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
        />
      </div>

      <div>
        <label
          htmlFor="date"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Date
        </label>
        <input
          id="date"
          name="date"
          type="date"
          required
          defaultValue={publicHoliday?.date}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
        />
        <p className="mt-1 text-xs text-text-muted">
          Each date can hold at most one holiday.
        </p>
      </div>

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
          {loading ? "Saving..." : publicHoliday ? "Save changes" : "Create holiday"}
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