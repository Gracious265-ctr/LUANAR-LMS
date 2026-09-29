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
import { Button, buttonVariants } from "@/components/ui/button";
import { FormError } from "@/components/ui/form-error";

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
        <Input
          id="date"
          name="date"
          type="date"
          required
          defaultValue={publicHoliday?.date}
        />
      </Field>

      {error && (
        <FormError className="md:col-span-2">{error}</FormError>
      )}

      <div className="flex items-center gap-3 md:col-span-2">
        <Button type="submit" variant="primary" loading={loading}>
          {loading ? "Saving..." : publicHoliday ? "Save changes" : "Create holiday"}
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