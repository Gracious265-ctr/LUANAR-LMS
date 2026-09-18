"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import type { LeaveRule, LeaveType } from "@/lib/leave-rules";
import { createLeaveRule, updateLeaveRule } from "@/lib/leave-rules-client";

export function LeaveRuleForm({
  leaveRule,
  leaveTypes,
}: {
  leaveRule?: LeaveRule;
  leaveTypes: LeaveType[];
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
        leave_type: Number(formData.get("leave_type")),
        max_duration_days: Number(formData.get("max_duration_days")),
        min_notice_days: Number(formData.get("min_notice_days") || 0),
        eligibility: String(formData.get("eligibility") || ""),
        requires_supporting_document:
          formData.get("requires_supporting_document") === "on",
        consumes_annual_entitlement:
          formData.get("consumes_annual_entitlement") === "on",
        effective_from: String(formData.get("effective_from") || ""),
      };
      if (leaveRule) {
        await updateLeaveRule(leaveRule.id, input);
      } else {
        await createLeaveRule(input);
      }
      router.push("/dashboard/hr-admin/leave-rules");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="grid grid-cols-1 gap-4 md:grid-cols-2">
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
          required
          defaultValue={leaveRule?.leave_type ?? ""}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
        >
          {leaveTypes.length === 0 && <option value="">No leave types available</option>}
          {leaveTypes.map((leaveType) => (
            <option key={leaveType.id} value={leaveType.id}>
              {leaveType.name}
            </option>
          ))}
        </select>
        {leaveTypes.length === 0 && (
          <p className="mt-1 text-xs text-text-muted">
            Create a leave type before adding a rule.
          </p>
        )}
      </div>

      <div>
        <label
          htmlFor="max_duration_days"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Maximum duration (days)
        </label>
        <input
          id="max_duration_days"
          name="max_duration_days"
          type="number"
          min={1}
          required
          defaultValue={leaveRule?.max_duration_days}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
        />
      </div>

      <div>
        <label
          htmlFor="min_notice_days"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Minimum notice (days)
        </label>
        <input
          id="min_notice_days"
          name="min_notice_days"
          type="number"
          min={0}
          defaultValue={leaveRule?.min_notice_days ?? 0}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
        />
        <p className="mt-1 text-xs text-text-muted">
          0 means no advance notice is required.
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
          defaultValue={leaveRule?.effective_from}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
        />
        <p className="mt-1 text-xs text-text-muted">
          Future-dated rules only apply from this date; past rules stay intact.
        </p>
      </div>

      <div className="md:col-span-2">
        <label
          htmlFor="eligibility"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Eligibility
        </label>
        <textarea
          id="eligibility"
          name="eligibility"
          rows={3}
          defaultValue={leaveRule?.eligibility}
          placeholder="e.g. Female employees at any grade"
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
        />
        <p className="mt-1 text-xs text-text-muted">
          A human-readable description of who qualifies for this leave type.
        </p>
      </div>

      <label className="flex items-center gap-2 md:col-span-2">
        <input
          type="checkbox"
          name="requires_supporting_document"
          defaultChecked={leaveRule?.requires_supporting_document ?? false}
          className="size-4 rounded border-input-border text-brand-primary focus:ring-input-ring-focus"
        />
        <span className="text-sm font-medium text-text-primary">
          Requires a supporting document
        </span>
      </label>

      <label className="flex items-center gap-2 md:col-span-2">
        <input
          type="checkbox"
          name="consumes_annual_entitlement"
          defaultChecked={leaveRule?.consumes_annual_entitlement ?? false}
          className="size-4 rounded border-input-border text-brand-primary focus:ring-input-ring-focus"
        />
        <span className="text-sm font-medium text-text-primary">
          Consumes annual leave entitlement
        </span>
      </label>

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
          {loading ? "Saving..." : leaveRule ? "Save changes" : "Create rule"}
        </button>
        <Link
          href="/dashboard/hr-admin/leave-rules"
          className="rounded-md border border-border-default bg-button-secondary px-4 py-2 font-medium text-text-secondary hover:bg-button-secondary-hover"
        >
          Cancel
        </Link>
      </div>
    </form>
  );
}