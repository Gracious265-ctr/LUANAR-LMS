"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import type { DelegateCandidate } from "@/lib/delegations";
import { createDelegation } from "@/lib/delegations-client";
import { Alert } from "@/components/ui/alert";
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
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);

    const formData = new FormData(event.currentTarget);
    const delegateValue = String(formData.get("delegate") || "");
    const endsOn = String(formData.get("ends_on") || "");

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
      <div>
        <label
          htmlFor="cover_starts_on"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Starts on
        </label>
        <input
          id="cover_starts_on"
          name="starts_on"
          type="date"
          required
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
        />
      </div>

      <div>
        <label
          htmlFor="cover_ends_on"
          className="mb-1 block text-sm font-medium text-text-primary"
        >
          Ends on
        </label>
        <input
          id="cover_ends_on"
          name="ends_on"
          type="date"
          className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
        />
        <p className="mt-1 text-xs text-text-muted">
          Leave blank to stay open-ended until HR cancels it.
        </p>
      </div>

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
        <button
          type="submit"
          disabled={loading}
          className="rounded-md bg-button-primary px-4 py-2 font-medium text-button-primary-foreground hover:bg-button-primary-hover focus:outline-none focus:ring-2 focus:ring-input-ring-focus disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Submitting..." : "Request cover"}
        </button>
      </div>
    </form>
  );
}
