"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import type { Employee } from "@/lib/employees";
import {
  approverRolePeople,
  createDelegation,
} from "@/lib/delegations-client";
import { Field, Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Button, buttonVariants } from "@/components/ui/button";
import { FormError } from "@/components/ui/form-error";

export function DelegationForm({ employees }: { employees: Employee[] }) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [approverId, setApproverId] = useState("");
  const approvers = approverRolePeople(employees);
  const delegates = approverRolePeople(employees).filter(
    (employee) => String(employee.id) !== approverId
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);

    const formData = new FormData(event.currentTarget);
    const delegateValue = String(formData.get("delegate") || "");
    const endsOn = String(formData.get("ends_on") || "");

    try {
      await createDelegation({
        approver: Number(formData.get("approver")),
        delegate: delegateValue ? Number(delegateValue) : null,
        starts_on: String(formData.get("starts_on")),
        ends_on: endsOn || null,
        request_reason: String(formData.get("request_reason") || ""),
      });
      router.push("/dashboard/hr-admin/delegations");
      router.refresh();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "An error occurred. Please try again."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-4 md:grid-cols-2">
      <Field
        label="Approver"
        htmlFor="approver"
        hint="The person whose pending approvals will be delegated."
      >
        <Select
          name="approver"
          required
          value={approverId}
          onValueChange={setApproverId}
        >
          <SelectTrigger id="approver" aria-label="Approver">
            <SelectValue placeholder="Select the approver" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="">Select the approver</SelectItem>
            {approvers.map((employee) => (
              <SelectItem key={employee.id} value={String(employee.id)}>
                {employee.full_name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>

      <Field
        label="Delegate nomination"
        htmlFor="delegate"
        hint="Optional. HR confirms the delegate or picks someone else on approval."
      >
        <Select name="delegate">
          <SelectTrigger id="delegate" aria-label="Delegate nomination">
            <SelectValue placeholder="No nomination" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="">No nomination</SelectItem>
            {delegates.map((employee) => (
              <SelectItem key={employee.id} value={String(employee.id)}>
                {employee.full_name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>

      <Field label="Starts on" htmlFor="starts_on">
        <Input id="starts_on" name="starts_on" type="date" required />
      </Field>

      <Field
        label="Ends on"
        htmlFor="ends_on"
        hint="Leave blank to stay open-ended until HR cancels it."
      >
        <Input id="ends_on" name="ends_on" type="date" />
      </Field>

      <Field
        label="Request reason"
        htmlFor="request_reason"
        className="md:col-span-2"
      >
        <Textarea
          id="request_reason"
          name="request_reason"
          rows={3}
          placeholder="Why is the approver unavailable?"
        />
      </Field>

      {approvers.length === 0 && (
        <p className="rounded-lg bg-surface-muted p-3 text-sm text-text-secondary md:col-span-2">
          No active users with an approver role are available. Create employee
          records first.
        </p>
      )}

      {error && (
        <FormError className="md:col-span-2">{error}</FormError>
      )}

      <div className="flex items-center gap-3 md:col-span-2">
        <Button type="submit" variant="primary" loading={loading}>
          {loading ? "Submitting..." : "Create delegation request"}
        </Button>
        <Link
          href="/dashboard/hr-admin/delegations"
          className={buttonVariants({ variant: "secondary" })}
        >
          Cancel
        </Link>
      </div>
    </form>
  );
}