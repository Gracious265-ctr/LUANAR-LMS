"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import type { Entitlement } from "@/lib/entitlements";
import { apiErrorMessage } from "@/lib/utils";
import { Input, Field } from "@/components/ui/input";
import { DatePicker } from "@/components/ui/date-picker";
import { Button, buttonVariants } from "@/components/ui/button";
import { FormError } from "@/components/ui/form-error";

export function EntitlementForm({
  entitlement,
  endpoint,
  method,
}: {
  entitlement?: Entitlement;
  endpoint: string;
  method: "POST" | "PATCH";
}) {
  const router = useRouter();
  const [effectiveFrom, setEffectiveFrom] = useState(entitlement?.effective_from ?? "");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);

    const formData = new FormData(event.currentTarget);

    // The picker is a popover trigger, so the browser can no longer enforce
    // `required` for it; check here instead of dropping the guarantee.
    if (!effectiveFrom) {
      setError("Choose an effective-from date.");
      setLoading(false);
      return;
    }

    try {
      const response = await fetch(endpoint, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          grade_start: formData.get("grade_start"),
          grade_end: formData.get("grade_end"),
          days: Number(formData.get("days")),
          effective_from: formData.get("effective_from"),
        }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        setError(apiErrorMessage(data));
        return;
      }

      router.push("/dashboard/hr-admin/entitlements");
      router.refresh();
    } catch {
      setError("An error occurred. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-4 md:grid-cols-2">
      <Field label="Grade start" htmlFor="grade_start">
        <Input
          id="grade_start"
          name="grade_start"
          required
          defaultValue={entitlement?.grade_start}
          placeholder="e.g. A"
        />
      </Field>

      <Field label="Grade end" htmlFor="grade_end">
        <Input
          id="grade_end"
          name="grade_end"
          required
          defaultValue={entitlement?.grade_end}
          placeholder="e.g. C"
        />
      </Field>

      <Field label="Annual days" htmlFor="days">
        <Input
          id="days"
          name="days"
          type="number"
          min={1}
          required
          defaultValue={entitlement?.days}
        />
      </Field>

      <Field label="Effective from" htmlFor="effective_from">
        <DatePicker
          id="effective_from"
          value={effectiveFrom}
          onChange={setEffectiveFrom}
        />
        {/* The trigger is a <button>, so the name still has to reach FormData. */}
        <input type="hidden" name="effective_from" value={effectiveFrom} />
      </Field>

      {error && (
        <FormError className="md:col-span-2">{error}</FormError>
      )}

      <div className="flex items-center gap-3 md:col-span-2">
        <Button type="submit" variant="primary" loading={loading}>
          {loading ? "Saving..." : entitlement ? "Save changes" : "Create entitlement"}
        </Button>
        <Link
          href="/dashboard/hr-admin/entitlements"
          className={buttonVariants({ variant: "secondary" })}
        >
          Cancel
        </Link>
      </div>
    </form>
  );
}