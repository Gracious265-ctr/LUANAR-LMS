"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import { approverRolePeople } from "@/lib/delegations-client";
import type { Employee } from "@/lib/employees";
import { reassignApplication } from "@/lib/reassignments-client";
import type { PendingApplication } from "@/lib/reassignments";

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
      <div className="rounded-md bg-surface-muted p-3 text-sm text-text-secondary">
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

      <div>
        <label
          htmlFor="to_approver"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Replacement approver
        </label>
        <select
          id="to_approver"
          name="to_approver"
          required
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
        >
          <option value="">Select the replacement approver</option>
          {candidates.map((employee) => (
            <option key={employee.id} value={employee.id}>
              {employee.full_name}
            </option>
          ))}
        </select>
        <p className="mt-1 text-xs text-text-muted">
          An active user with an approver role, different from the current
          approver and the applicant.
        </p>
      </div>

      <div>
        <label
          htmlFor="reason"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Reassignment reason
        </label>
        <textarea
          id="reason"
          name="reason"
          rows={3}
          required
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
          placeholder="Why is the application being reassigned?"
        />
        <p className="mt-1 text-xs text-text-muted">
          Mandatory. Recorded on the reassignment history row.
        </p>
      </div>

      {candidates.length === 0 && (
        <p className="rounded-md bg-surface-muted p-3 text-sm text-text-secondary">
          No eligible replacement approvers are available. Create employee
          records with approver roles first.
        </p>
      )}

      {error && (
        <div className="rounded-md bg-status-rejected-subtle p-3 text-sm text-status-rejected">
          {error}
        </div>
      )}

      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={loading}
          className="rounded-md bg-button-primary px-4 py-2 font-medium text-button-primary-foreground hover:bg-button-primary-hover focus:outline-none focus:ring-2 focus:ring-input-ring-focus disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Reassigning..." : "Reassign application"}
        </button>
        <Link
          href="/dashboard/hr-admin/reassignments"
          className="rounded-md border border-border-default bg-button-secondary px-4 py-2 font-medium text-text-secondary hover:bg-button-secondary-hover"
        >
          Cancel
        </Link>
      </div>
    </form>
  );
}