"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import {
  WEEKDAYS,
  WEEKDAY_LABELS,
  type Weekday,
  type WorkingDayPattern,
} from "@/lib/calendar-weekdays";
import { updateWorkingDayPattern } from "@/lib/financial-years-client";
import { Button } from "@/components/ui/button";
import { FormError } from "@/components/ui/form-error";

/**
 * The single institution-wide working-day pattern (§3.4).
 *
 * Changing it re-derives the day count of every draft application that overlaps
 * the affected period (new day-counting is forward-looking, per the project's
 * "config changes are forward-looking only" invariant); already-submitted
 * applications keep the count they were submitted with.
 */
export function WorkingDaysSection({
  pattern,
}: {
  pattern: WorkingDayPattern;
}) {
  const router = useRouter();
  const [days, setDays] = useState<WorkingDayPattern>(pattern);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(false);

  const workingCount = WEEKDAYS.filter((day) => days[day]).length;

  function toggle(day: Weekday) {
    setSaved(false);
    setDays((current) => ({ ...current, [day]: !current[day] }));
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSaved(false);
    if (workingCount === 0) {
      setError("At least one weekday must be a working day.");
      return;
    }
    setLoading(true);
    try {
      const next = await updateWorkingDayPattern(days);
      setDays(next);
      setSaved(true);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="max-w-2xl space-y-4">
      <div>
        <h3 className="text-lg font-semibold text-text-primary">Working days</h3>
        <p className="mt-1 text-sm text-text-secondary">Leave day counts and notice periods exclude the days you clear here.</p>
      </div>

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {WEEKDAYS.map((day) => (
          <label
            key={day}
            className="flex items-center gap-2 rounded-md border border-border-default px-3 py-2 text-sm text-text-primary"
          >
            <input
              type="checkbox"
              checked={days[day]}
              onChange={() => toggle(day)}
              className="h-4 w-4 rounded border-input-border text-brand-primary focus:ring-input-ring-focus"
            />
            {WEEKDAY_LABELS[day]}
          </label>
        ))}
      </div>

      {error && <FormError>{error}</FormError>}
      {saved && !error && (
        <p className="text-sm text-status-approved">Working-day pattern saved.</p>
      )}

      <Button type="submit" variant="primary" loading={loading}>
        {loading ? "Saving..." : "Save working days"}
      </Button>
    </form>
  );
}
