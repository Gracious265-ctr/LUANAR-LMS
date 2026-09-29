"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import type { DelegateCandidate } from "@/lib/delegations";
import { createDelegation } from "@/lib/delegations-client";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { DateRangePicker } from "@/components/ui/date-picker";
import { Field } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

/**
 * Self-service cover request for an approver.
 *
 * Deliberately has no approver field: the backend forces `approver` to the
 * authenticated caller and ignores any value sent, so asking the user to pick
 * themselves would be theatre. The delegate nomination is optional — HR confirms
 * or replaces it on approval.
 */
export function CoverRequestForm({ candidates }: { candidates: DelegateCandidate[] }) {
  const router = useRouter();
  const [startsOn, setStartsOn] = useState("");
  const [endsOn, setEndsOn] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);

    const formData = new FormData(event.currentTarget);
    const delegateValue = String(formData.get("delegate") || "");

    // The picker is a popover trigger, so the browser can no longer enforce
    // `required` for it; check here instead of dropping the guarantee.
    if (!startsOn) {
      setError("Choose a start date.");
      setLoading(false);
      return;
    }

    try {
      await createDelegation({
        delegate: delegateValue ? Number(delegateValue) : null,
        starts_on: String(formData.get("starts_on")),
        ends_on: endsOn || null,
        request_reason: String(formData.get("request_reason") || ""),
      });
      setLoading(false);
      router.refresh();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "An error occurred. Please try again."
      );
      setLoading(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      data-testid="cover-request-form"
      className="grid grid-cols-1 gap-4 md:grid-cols-2"
    >
      <Field
        label="Period"
        htmlFor="cover_starts_on"
        hint="Leave the end blank to stay open-ended until HR cancels it."
      >
        <DateRangePicker
          id="cover_starts_on"
          from={startsOn}
          to={endsOn}
          onRangeChange={(from, to) => {
            setStartsOn(from);
            setEndsOn(to);
          }}
        />
        {/* The trigger is a <button>, so the names still have to reach FormData. */}
        <input type="hidden" name="starts_on" value={startsOn} />
        <input type="hidden" name="ends_on" value={endsOn} />
      </Field>

      <div>
        <label
          htmlFor="cover_delegate"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Nominate a delegate
        </label>
        <Select name="delegate">
          <SelectTrigger id="cover_delegate" aria-label="Nominate a delegate">
            <SelectValue placeholder="No nomination" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="">No nomination</SelectItem>
            {candidates.map((candidate) => (
              <SelectItem key={candidate.id} value={String(candidate.id)}>
                {candidate.full_name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <p className="mt-1 text-xs text-text-muted">
          Optional. HR confirms the delegate or picks someone else on approval.
        </p>
      </div>

      <div className="md:col-span-2">
        <label
          htmlFor="cover_request_reason"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Reason
        </label>
        <textarea
          id="cover_request_reason"
          name="request_reason"
          rows={3}
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
          placeholder="Why are you unavailable to approve?"
        />
      </div>

      {error && (
        <Alert tone="rejected" className="md:col-span-2">
          {error}
        </Alert>
      )}

      <div className="md:col-span-2">
        <Button type="submit" disabled={loading} variant="primary">
          {loading ? "Submitting..." : "Request cover"}
        </Button>
      </div>
    </form>
  );
}
