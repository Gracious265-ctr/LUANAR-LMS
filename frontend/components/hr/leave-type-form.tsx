"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import type { LeaveType } from "@/lib/leave-rules";
import { createLeaveType, updateLeaveType } from "@/lib/leave-rules-client";
import { Input, Field } from "@/components/ui/input";
import { Button, buttonVariants } from "@/components/ui/button";
import { FormError } from "@/components/ui/form-error";

export function LeaveTypeForm({ leaveType }: { leaveType?: LeaveType }) {
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
      };
      if (leaveType) {
        await updateLeaveType(leaveType.id, input);
      } else {
        await createLeaveType(input);
      }
      router.push("/dashboard/hr-admin/leave-types");
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

      {error && (
        <FormError className="md:col-span-2">{error}</FormError>
      )}

      <div className="flex items-center gap-3 md:col-span-2">
        <Button type="submit" variant="primary" loading={loading}>
          {loading ? "Saving..." : leaveType ? "Save changes" : "Create leave type"}
        </Button>
        <Link
          href="/dashboard/hr-admin/leave-types"
          className={buttonVariants({ variant: "secondary" })}
        >
          Cancel
        </Link>
      </div>
    </form>
  );
}