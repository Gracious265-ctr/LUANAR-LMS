"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Plus } from "lucide-react";

import type { LeaveRule, LeaveType } from "@/lib/leave-rules";
import {
  createLeaveRule,
  createLeaveType,
  updateLeaveRule,
} from "@/lib/leave-rules-client";
import { Field, Input } from "@/components/ui/input";
import { DatePicker } from "@/components/ui/date-picker";
import { Button, buttonVariants } from "@/components/ui/button";
import { FormError } from "@/components/ui/form-error";
import { Textarea } from "@/components/ui/textarea";

export function LeaveRuleForm({
  leaveRule,
  leaveTypes,
  onSuccess,
  onCancel,
}: {
  leaveRule?: LeaveRule;
  leaveTypes: LeaveType[];
  /**
   * When provided the form reports the saved record instead of navigating, so a
   * dialog can close and refresh its list without the page moving underneath it.
   * Defaults to the push-and-refresh the standalone pages rely on.
   */
  onSuccess?: (leaveRule: LeaveRule) => void;
  /** Replaces the Cancel link when the form is hosted in a dialog. */
  onCancel?: () => void;
}) {
  const router = useRouter();
  const [effectiveFrom, setEffectiveFrom] = useState(leaveRule?.effective_from ?? "");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  // The server-loaded options are the starting point, not the final word: HR can
  // create a leave type from this form, and the one they just made must appear in
  // the picker without leaving the page.
  const [leaveTypeOptions, setLeaveTypeOptions] =
    useState<LeaveType[]>(leaveTypes);
  const [selectedLeaveType, setSelectedLeaveType] = useState(
    leaveRule?.leave_type === undefined || leaveRule?.leave_type === null
      ? ""
      : String(leaveRule.leave_type)
  );
  const [showNewLeaveType, setShowNewLeaveType] = useState(false);
  const [newLeaveTypeName, setNewLeaveTypeName] = useState("");
  const [creatingLeaveType, setCreatingLeaveType] = useState(false);
  const [leaveTypeCreateError, setLeaveTypeCreateError] = useState("");

  async function handleCreateLeaveType() {
    const name = newLeaveTypeName.trim();
    if (name === "") return;
    setLeaveTypeCreateError("");
    setCreatingLeaveType(true);
    try {
      const created = await createLeaveType({ name });
      setLeaveTypeOptions((current) =>
        [...current, created].sort((a, b) => a.name.localeCompare(b.name))
      );
      setSelectedLeaveType(String(created.id));
      setNewLeaveTypeName("");
      setShowNewLeaveType(false);
    } catch (err) {
      setLeaveTypeCreateError(
        err instanceof Error ? err.message : "Could not create the leave type."
      );
    } finally {
      setCreatingLeaveType(false);
    }
  }

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
      const saved = leaveRule
        ? await updateLeaveRule(leaveRule.id, input)
        : await createLeaveRule(input);
      if (onSuccess) {
        onSuccess(saved);
      } else {
        router.push("/hr-admin/leave-rules");
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
      <Field
        label="Leave type"
        htmlFor="leave_type"
        hint={
          leaveTypeOptions.length === 0
            ? "Create a leave type before adding a rule."
            : undefined
        }
      >
        {/* Deliberately a native <select> rather than the shared Radix picker:
            creating a leave type here adds an option that has never been
            rendered, and Radix only learns an item by mounting it, so it resets
            the controlled value to "" and the new type can never show as
            selected while the list is closed. */}
        <select
          id="leave_type"
          name="leave_type"
          required
          value={selectedLeaveType}
          onChange={(event) => setSelectedLeaveType(event.target.value)}
          className="w-full rounded-control border border-input-border bg-input-background px-control-x-md py-control-y text-sm text-text-primary focus-ring"
        >
          <option value="">Choose a leave type…</option>
          {leaveTypeOptions.map((leaveType) => (
            <option key={leaveType.id} value={leaveType.id}>
              {leaveType.name}
            </option>
          ))}
        </select>

        {!showNewLeaveType ? (
          <Button
            type="button"
            variant="secondary"
            className="mt-2"
            onClick={() => setShowNewLeaveType(true)}
          >
            <Plus className="h-4 w-4" />
            Create leave type
          </Button>
        ) : (
          <div className="mt-2 rounded-md border border-border-default bg-surface-muted p-3">
            <Field label="New leave type name" htmlFor="new_leave_type_name">
              <Input
                id="new_leave_type_name"
                value={newLeaveTypeName}
                onChange={(event) => setNewLeaveTypeName(event.target.value)}
                placeholder="e.g. Study leave"
              />
            </Field>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <Button
                type="button"
                variant="primary"
                loading={creatingLeaveType}
                disabled={newLeaveTypeName.trim() === ""}
                onClick={() => void handleCreateLeaveType()}
              >
                {creatingLeaveType ? "Saving..." : "Save leave type"}
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setShowNewLeaveType(false);
                  setLeaveTypeCreateError("");
                }}
              >
                Cancel
              </Button>
            </div>
            {leaveTypeCreateError ? (
              <FormError className="mt-1">{leaveTypeCreateError}</FormError>
            ) : null}
          </div>
        )}
      </Field>

      <Field label="Maximum duration (days)" htmlFor="max_duration_days">
        <Input
          id="max_duration_days"
          name="max_duration_days"
          type="number"
          min={1}
          required
          defaultValue={leaveRule?.max_duration_days}
        />
      </Field>

      <Field
        label="Minimum notice (days)"
        htmlFor="min_notice_days"
        hint="0 means no advance notice is required."
      >
        <Input
          id="min_notice_days"
          name="min_notice_days"
          type="number"
          min={0}
          defaultValue={leaveRule?.min_notice_days ?? 0}
        />
      </Field>

      <Field
        label="Effective from"
        htmlFor="effective_from"
        hint="Future-dated rules only apply from this date; past rules stay intact."
      >
        <DatePicker
          id="effective_from"
          value={effectiveFrom}
          onChange={setEffectiveFrom}
        />
        {/* The trigger is a <button>, so the name still has to reach FormData. */}
        <input type="hidden" name="effective_from" value={effectiveFrom} />
      </Field>

      <Field
        label="Eligibility"
        htmlFor="eligibility"
        hint="A human-readable description of who qualifies for this leave type."
        className="md:col-span-2"
      >
        <Textarea
          id="eligibility"
          name="eligibility"
          rows={3}
          defaultValue={leaveRule?.eligibility}
          placeholder="e.g. Female employees at any grade"
        />
      </Field>

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
        <FormError className="md:col-span-2">{error}</FormError>
      )}

      <div className="flex items-center gap-3 md:col-span-2">
        <Button type="submit" variant="primary" loading={loading}>
          {loading ? "Saving..." : leaveRule ? "Save changes" : "Create rule"}
        </Button>
        {onCancel ? (
          <Button type="button" variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
        ) : (
          <Link
            href="/hr-admin/leave-rules"
            className={buttonVariants({ variant: "secondary" })}
          >
            Cancel
          </Link>
        )}
      </div>
    </form>
  );
}