"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import type { LeaveRule, LeaveType } from "@/lib/leave-rules";
import { createLeaveRule, updateLeaveRule } from "@/lib/leave-rules-client";
import { Field, Input } from "@/components/ui/input";
import { DatePicker } from "@/components/ui/date-picker";
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

export function LeaveRuleForm({
  leaveRule,
  leaveTypes,
}: {
  leaveRule?: LeaveRule;
  leaveTypes: LeaveType[];
}) {
  const router = useRouter();
  const [effectiveFrom, setEffectiveFrom] = useState(leaveRule?.effective_from ?? "");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

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
      <Field label="Leave type" htmlFor="leave_type">
        <Select name="leave_type" required defaultValue={leaveRule?.leave_type ? String(leaveRule.leave_type) : ""}>
          <SelectTrigger id="leave_type" aria-label="Leave type">
            <SelectValue placeholder="No leave types available" />
          </SelectTrigger>
          <SelectContent>
            {leaveTypes.map((leaveType) => (
              <SelectItem key={leaveType.id} value={String(leaveType.id)}>
                {leaveType.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {leaveTypes.length === 0 && (
          <p className="text-xs text-text-muted">
            Create a leave type before adding a rule.
          </p>
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
        <Link
          href="/dashboard/hr-admin/leave-rules"
          className={buttonVariants({ variant: "secondary" })}
        >
          Cancel
        </Link>
      </div>
    </form>
  );
}