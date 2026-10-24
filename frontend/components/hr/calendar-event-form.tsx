"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import type { CalendarEvent } from "@/lib/financial-years";
import {
  createCalendarEvent,
  updateCalendarEvent,
} from "@/lib/financial-years-client";
import { Input, Field } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { DateRangePicker } from "@/components/ui/date-picker";
import { Button, buttonVariants } from "@/components/ui/button";
import { FormError } from "@/components/ui/form-error";

export function CalendarEventForm({
  event,
  onSuccess,
  onCancel,
}: {
  event?: CalendarEvent;
  /** Replaces the default `router.push(listRoute)` + `router.refresh()`. */
  onSuccess?: (event: CalendarEvent) => void;
  /** Adds a dismiss action; an inline page form has nothing to dismiss to. */
  onCancel?: () => void;
}) {
  const router = useRouter();
  const [startDate, setStartDate] = useState(event?.start_date ?? "");
  const [endDate, setEndDate] = useState(event?.end_date ?? "");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(eventSubmit: FormEvent<HTMLFormElement>) {
    eventSubmit.preventDefault();
    setError("");
    setLoading(true);

    const formData = new FormData(eventSubmit.currentTarget);

    // The picker is a popover trigger, so the browser can no longer enforce
    // `required` for it; check here instead of dropping the guarantee.
    if (!startDate || !endDate) {
      setError("Choose the full period.");
      setLoading(false);
      return;
    }

    try {
      const input = {
        title: String(formData.get("title") || "").trim(),
        start_date: String(formData.get("start_date") || ""),
        end_date: String(formData.get("end_date") || ""),
        description: String(formData.get("description") || "").trim(),
        affects_leave_calculation:
          formData.get("affects_leave_calculation") !== null,
      };
      const saved = event
        ? await updateCalendarEvent(event.id, input)
        : await createCalendarEvent(input);
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
      <Field label="Title" htmlFor="title" className="md:col-span-2">
        <Input
          id="title"
          name="title"
          required
          defaultValue={event?.title}
          placeholder="e.g. Graduation week"
        />
      </Field>

      <Field
        label="Period"
        htmlFor="start_date"
        hint="The event spans these dates, inclusive."
        className="md:col-span-2"
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

      <Field label="Description" htmlFor="description" className="md:col-span-2">
        <Textarea
          id="description"
          name="description"
          rows={3}
          defaultValue={event?.description}
          placeholder="What happens during this event?"
        />
      </Field>

      <label className="flex items-center gap-2 text-sm text-text-primary md:col-span-2">
        <input
          id="affects_leave_calculation"
          name="affects_leave_calculation"
          type="checkbox"
          defaultChecked={event?.affects_leave_calculation ?? false}
          className="h-4 w-4 rounded border-input-border text-brand-primary focus:ring-input-ring-focus"
        />
        Block or warn on leave that overlaps this event
      </label>
      <p className="text-xs text-text-muted md:col-span-2">
        Leave this off for a purely informational entry. Turning it on promotes
        the event to a period that affects leave calculations.
      </p>

      {error && (
        <FormError className="md:col-span-2">{error}</FormError>
      )}

      <div className="flex items-center gap-3 md:col-span-2">
        <Button type="submit" variant="primary" loading={loading}>
          {loading ? "Saving..." : event ? "Save changes" : "Create event"}
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
