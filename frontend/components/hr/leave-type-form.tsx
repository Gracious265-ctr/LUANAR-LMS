"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import type { LeaveType } from "@/lib/leave-rules";
import { createLeaveType, updateLeaveType } from "@/lib/leave-rules-client";
import { Input, Field } from "@/components/ui/input";
import { Button, buttonVariants } from "@/components/ui/button";
import { FormError } from "@/components/ui/form-error";

export function LeaveTypeForm({
  leaveType,
  onSuccess,
  onCancel,
}: {
  leaveType?: LeaveType;
  /**
   * Replaces the default `router.push(listRoute)` + `router.refresh()`. The
   * overlay passes this so it can close itself and refetch; with it omitted the
   * form navigates on its own, which is what a standalone page needs.
   */
  onSuccess?: (leaveType: LeaveType) => void;
  /** Adds a dismiss action. An inline page form has nothing to dismiss to. */
  onCancel?: () => void;
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
        code: String(formData.get("code") || "").trim() || undefined,
        is_active: formData.get("is_active") === "on",
      };
      const saved = leaveType
        ? await updateLeaveType(leaveType.id, input)
        : await createLeaveType(input);
      if (onSuccess) {
        onSuccess(saved);
      } else {
        router.push("/dashboard/hr-admin/leave-types");
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
          defaultValue={leaveType?.name}
          placeholder="e.g. Study leave"
        />
      </Field>

      <Field
        label="Code"
        htmlFor="code"
        hint="Short slug used to identify this type. Leave blank to derive it from the name."
      >
        <Input
          id="code"
          name="code"
          defaultValue={leaveType?.code}
          placeholder="Optional; derived from name"
        />
      </Field>

      <div className="flex items-center gap-2 md:col-span-2">
        <input
          id="is_active"
          name="is_active"
          type="checkbox"
          defaultChecked={leaveType?.is_active !== false}
          className="h-4 w-4 rounded border-input-border text-brand-primary focus:ring-input-ring-focus"
        />
        <label htmlFor="is_active" className="text-sm text-text-primary">
          Active (offered to employees with a matching entitlement)
        </label>
      </div>

      {error && (
        <FormError className="md:col-span-2">{error}</FormError>
      )}

      <div className="flex items-center gap-3 md:col-span-2">
        <Button type="submit" variant="primary" loading={loading}>
          {loading ? "Saving..." : leaveType ? "Save changes" : "Create leave type"}
        </Button>
        {onCancel ? (
          <Button type="button" variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
        ) : (
          <Link
            href="/dashboard/hr-admin/leave-types"
            className={buttonVariants({ variant: "secondary" })}
          >
            Cancel
          </Link>
        )}
      </div>
    </form>
  );
}