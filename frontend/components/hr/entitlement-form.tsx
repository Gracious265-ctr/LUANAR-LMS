"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import type { Entitlement } from "@/lib/entitlements";
import { apiErrorMessage } from "@/lib/utils";
import { listLeaveTypes } from "@/lib/leave-types-client";
import type { LeaveTypeListResponse } from "@/lib/leave-rules";

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
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [leaveTypes, setLeaveTypes] = useState<LeaveTypeListResponse | null>(null);
  const [ltError, setLtError] = useState("");

  useEffect(() => {
    listLeaveTypes()
      .then((data) => setLeaveTypes(data))
      .catch(() => setLtError("Unable to load leave types. Please try again."));
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);

    const formData = new FormData(event.currentTarget);
    const leaveTypeValue = formData.get("leave_type");

    try {
      const response = await fetch(endpoint, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          grade_start: formData.get("grade_start"),
          grade_end: formData.get("grade_end"),
          days: Number(formData.get("days")),
          effective_from: formData.get("effective_from"),
          leave_type: leaveTypeValue && leaveTypeValue !== "" ? Number(leaveTypeValue) : null,
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
      <div>
        <label
          htmlFor="grade_start"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Grade start
        </label>
        <input
          id="grade_start"
          name="grade_start"
          required
          defaultValue={entitlement?.grade_start}
          placeholder="e.g. A"
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
        />
      </div>

      <div>
        <label
          htmlFor="grade_end"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Grade end
        </label>
        <input
          id="grade_end"
          name="grade_end"
          required
          defaultValue={entitlement?.grade_end}
          placeholder="e.g. C"
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
        />
      </div>

      <div>
        <label
          htmlFor="days"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Annual days
        </label>
        <input
          id="days"
          name="days"
          type="number"
          min={1}
          required
          defaultValue={entitlement?.days}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
        />
      </div>

      <div>
        <label
          htmlFor="leave_type"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Leave type
        </label>
        <select
          id="leave_type"
          name="leave_type"
          defaultValue={entitlement?.leave_type ? String(entitlement.leave_type) : ""}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
        >
          <option value="">None (untype annual)</option>
          {leaveTypes?.results?.map((lt) => (
            <option key={lt.id} value={lt.id}>
              {lt.name}
            </option>
          ))}
        </select>
        {ltError && (
          <p className="mt-1 text-xs text-status-rejected">{ltError}</p>
        )}
        <p className="mt-1 text-xs text-text-muted">
          Granting a specific type makes it appear in the employee&apos;s leave-type selection.
        </p>
      </div>

      <div>
        <label
          htmlFor="effective_from"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Effective from
        </label>
        <input
          id="effective_from"
          name="effective_from"
          type="date"
          required
          defaultValue={entitlement?.effective_from}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
        />
      </div>

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
          {loading ? "Saving..." : entitlement ? "Save changes" : "Create entitlement"}
        </button>
        <Link
          href="/dashboard/hr-admin/entitlements"
          className="rounded-md border border-border-default bg-button-secondary px-4 py-2 font-medium text-text-secondary hover:bg-button-secondary-hover"
        >
          Cancel
        </Link>
      </div>
    </form>
  );
}