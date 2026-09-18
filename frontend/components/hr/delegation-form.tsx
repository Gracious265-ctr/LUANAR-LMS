"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import type { Employee } from "@/lib/employees";
import {
  approverRolePeople,
  createDelegation,
} from "@/lib/delegations-client";

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
      <div>
        <label
          htmlFor="approver"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Approver
        </label>
        <select
          id="approver"
          name="approver"
          required
          value={approverId}
          onChange={(event) => setApproverId(event.target.value)}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
        >
          <option value="">Select the approver</option>
          {approvers.map((employee) => (
            <option key={employee.id} value={employee.id}>
              {employee.full_name}
            </option>
          ))}
        </select>
        <p className="mt-1 text-xs text-text-muted">
          The person whose pending approvals will be delegated.
        </p>
      </div>

      <div>
        <label
          htmlFor="delegate"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Delegate nomination
        </label>
        <select
          id="delegate"
          name="delegate"
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
        >
          <option value="">No nomination</option>
          {delegates.map((employee) => (
            <option key={employee.id} value={employee.id}>
              {employee.full_name}
            </option>
          ))}
        </select>
        <p className="mt-1 text-xs text-text-muted">
          Optional. HR confirms the delegate or picks someone else on approval.
        </p>
      </div>

      <div>
        <label
          htmlFor="starts_on"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Starts on
        </label>
        <input
          id="starts_on"
          name="starts_on"
          type="date"
          required
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
        />
      </div>

      <div>
        <label
          htmlFor="ends_on"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Ends on
        </label>
        <input
          id="ends_on"
          name="ends_on"
          type="date"
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
        />
        <p className="mt-1 text-xs text-text-muted">
          Leave blank to stay open-ended until HR cancels it.
        </p>
      </div>

      <div className="md:col-span-2">
        <label
          htmlFor="request_reason"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Request reason
        </label>
        <textarea
          id="request_reason"
          name="request_reason"
          rows={3}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
          placeholder="Why is the approver unavailable?"
        />
      </div>

      {approvers.length === 0 && (
        <p className="rounded-md bg-surface-muted p-3 text-sm text-text-secondary md:col-span-2">
          No active users with an approver role are available. Create employee
          records first.
        </p>
      )}

      {error && (
        <div className="rounded-md bg-status-rejected-subtle p-3 text-sm text-status-rejected md:col-span-2">
          {error}
        </div>
      )}

      <div className="flex items-center gap-3 md:col-span-2">
        <button
          type="submit"
          disabled={loading}
          className="rounded-md bg-button-primary px-4 py-2 font-medium text-button-primary-foreground hover:bg-button-primary-hover focus:outline-none focus:ring-2 focus:ring-input-ring-focus disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Submitting..." : "Create delegation request"}
        </button>
        <Link
          href="/dashboard/hr-admin/delegations"
          className="rounded-md border border-border-default bg-button-secondary px-4 py-2 font-medium text-text-secondary hover:bg-button-secondary-hover"
        >
          Cancel
        </Link>
      </div>
    </form>
  );
}