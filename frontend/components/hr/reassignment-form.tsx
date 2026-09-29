"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import { approverRolePeople } from "@/lib/delegations-client";
import type { Employee } from "@/lib/employees";
import { reassignApplication } from "@/lib/reassignments-client";
import type { PendingApplication } from "@/lib/reassignments";
import { Field, Select } from "@/components/ui/input";
import { Button, buttonVariants } from "@/components/ui/button";
import { FormError } from "@/components/ui/form-error";
import { Textarea } from "@/components/ui/textarea";

export function ReassignmentForm({
  application,
  employees,
}: {
  application: PendingApplication;
  employees: Employee[];
}) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const candidates = approverRolePeople(employees).filter(
    (employee) =>
      String(employee.id) !== String(application.employee) &&
      String(employee.id) !== String(application.current_approver)
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);

    const formData = new FormData(event.currentTarget);

    try {
      await reassignApplication({
        application: application.id,
        to_approver: Number(formData.get("to_approver")),
        reason: String(formData.get("reason") || ""),
      });
      router.push("/dashboard/hr-admin/reassignments");
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
    <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-4">
      <div className="rounded-lg bg-surface-muted p-3 text-sm text-text-secondary">
        <p className="font-medium text-text-primary">Reassigning</p>
        <p className="mt-1">
          {application.reference_number || "\u2014"} — {application.employee_name}
          {application.leave_type_name
            ? ` (${application.leave_type_name})`
            : ""}
        </p>
        <p className="mt-0.5 text-xs text-text-muted">
          {application.start_date ?? "—"}
          {application.end_date ? ` → ${application.end_date}` : ""} · Current
          approver: {application.current_approver_name || "Unassigned"}
        </p>
        {application.is_delegated && (
          /* Stated before the select, not after: cover is a query-time overlay,
             so handing this to the named approver would leave their delegate
             acting and the intervention would appear to do nothing. */
          <p className="mt-2 rounded-md bg-status-pending-subtle px-3 py-2 text-xs text-status-pending">
            {application.acting_approver_name} is currently acting as delegate
            for {application.current_approver_name}. Reassigning moves the record
            to your chosen approver; if you choose{" "}
            {application.current_approver_name}, their delegate keeps acting.
          </p>
        )}

      </div>

      <Field
        label="Replacement approver"
        htmlFor="to_approver"
        hint="An active user with an approver role, different from the current approver and the applicant."
      >
        <Select
          id="to_approver"
          name="to_approver"
          required
        >
          <option value="">Select the replacement approver</option>
          {candidates.map((employee) => (
            <option key={employee.id} value={employee.id}>
              {employee.full_name}
            </option>
          ))}
        </Select>
      </Field>

      <Field
        label="Reassignment reason"
        htmlFor="reason"
        hint="Mandatory. Recorded on the reassignment history row."
      >
        <Textarea
          id="reason"
          name="reason"
          rows={3}
          required
          placeholder="Why is the application being reassigned?"
        />
      </Field>

      {candidates.length === 0 && (
        <p className="rounded-lg bg-surface-muted p-3 text-sm text-text-secondary">
          No eligible replacement approvers are available. Create employee
          records with approver roles first.
        </p>
      )}

      {error && (
        <FormError>{error}</FormError>
      )}

      <div className="flex items-center gap-3">
        <Button type="submit" variant="primary" loading={loading}>
          {loading ? "Reassigning..." : "Reassign application"}
        </Button>
        <Link
          href="/dashboard/hr-admin/reassignments"
          className={buttonVariants({ variant: "secondary" })}
        >
          Cancel
        </Link>
      </div>
    </form>
  );
}