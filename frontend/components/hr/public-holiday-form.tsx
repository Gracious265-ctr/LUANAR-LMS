"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import type { PublicHoliday } from "@/lib/financial-years";
import {
  createPublicHoliday,
  updatePublicHoliday,
} from "@/lib/financial-years-client";
import { Input, Field } from "@/components/ui/input";
import { DatePicker } from "@/components/ui/date-picker";
import { Button, buttonVariants } from "@/components/ui/button";
import { FormError } from "@/components/ui/form-error";

export function PublicHolidayForm({
  publicHoliday,
  onSuccess,
  onCancel,
}: {
  publicHoliday?: PublicHoliday;
  /** Replaces the default `router.push(listRoute)` + `router.refresh()`. */
  onSuccess?: (publicHoliday: PublicHoliday) => void;
  /** Adds a dismiss action; an inline page form has nothing to dismiss to. */
  onCancel?: () => void;
}) {
  const router = useRouter();
  const [date, setDate] = useState(publicHoliday?.date ?? "");
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
      const input = {
        name: String(formData.get("name") || "").trim(),
        date: String(formData.get("date") || ""),
      };
      const saved = publicHoliday
        ? await updatePublicHoliday(publicHoliday.id, input)
        : await createPublicHoliday(input);
      if (onSuccess) {
        onSuccess(saved);
      } else {
        router.push("/dashboard/hr-admin/calendar");
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
          defaultValue={publicHoliday?.name}
          placeholder="e.g. Independence Day"
        />
      </Field>

      <Field
        label="Date"
        htmlFor="date"
        hint="Each date can hold at most one holiday."
      >
        <DatePicker id="date" value={date} onChange={setDate} />
        {/* The trigger is a <button>, so the name still has to reach FormData. */}
        <input type="hidden" name="date" value={date} />
      </Field>

      {error && (
        <FormError className="md:col-span-2">{error}</FormError>
      )}

      <div className="flex items-center gap-3 md:col-span-2">
        <Button type="submit" variant="primary" loading={loading}>
          {loading ? "Saving..." : publicHoliday ? "Save changes" : "Create holiday"}
        </Button>
        {onCancel ? (
          <Button type="button" variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
        ) : (
          <Link
            href="/dashboard/hr-admin/calendar"
            className={buttonVariants({ variant: "secondary" })}
          >
            Cancel
          </Link>
        )}
      </div>
    </form>
  );
}