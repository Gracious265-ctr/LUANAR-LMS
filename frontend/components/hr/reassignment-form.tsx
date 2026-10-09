"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import { approverRolePeople } from "@/lib/delegations-client";
import type { Employee } from "@/lib/employees";
import { reassignApplication } from "@/lib/reassignments-client";
import { STATUS_STYLES } from "@/lib/status-styles";
import type { PendingApplication } from "@/lib/reassignments";
import { Field } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button, buttonVariants } from "@/components/ui/button";
import { FormError } from "@/components/ui/form-error";
import { Textarea } from "@/components/ui/textarea";

/** Where the standalone form returns to, and what Cancel links back to. */
const LIST_ROUTE = "/dashboard/hr-admin/reassignments";

export function ReassignmentForm({
  application,
  employees,
  onSuccess,
  onCancel,
}: {
  application: PendingApplication;
  employees: Employee[];
  /**
   * Replaces the default `router.push(listRoute)` + `router.refresh()`. The
   * overlay passes this so it can close itself and refetch; with it omitted the
   * form navigates on its own, which is what the standalone page needs.
   */
  onSuccess?: () => void;
  /** Adds a dismiss action. An inline page form has nothing to dismiss to. */
  onCancel?: () => void;
}) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const candidates = approverRolePeople(employees).filter(
    (employee) =>
      String(employee.user_id) !== String(application.employee) &&
      String(employee.user_id) !== String(application.current_approver)
  );

  /** Close-and-refresh when hosted, navigate when standalone. */
  function done() {
    if (onSuccess) {
      onSuccess();
      return;
    }
    router.push(LIST_ROUTE);
    router.refresh();
  }

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
      done();
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
          <p
            className={`mt-2 rounded-md px-3 py-2 text-xs ${STATUS_STYLES.pending}`}
          >
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
        <Select name="to_approver" required>
          <SelectTrigger id="to_approver" aria-label="Replacement approver">
            <SelectValue placeholder="Select the replacement approver" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="">Select the replacement approver</SelectItem>
            {candidates.map((employee) => (
              <SelectItem key={employee.id} value={String(employee.user_id)}>
                {employee.full_name}
              </SelectItem>
            ))}
          </SelectContent>
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
        {onCancel ? (
          <Button type="button" variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
        ) : (
          <Link
            href={LIST_ROUTE}
            className={buttonVariants({ variant: "secondary" })}
          >
            Cancel
          </Link>
        )}
      </div>
    </form>
  );
}