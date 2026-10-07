"use client";

import { FormEvent, ReactNode, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Check, X } from "lucide-react";

import type { Employee } from "@/lib/employees";
import type { Delegation } from "@/lib/delegations";
import {
  approveDelegation,
  approverRolePeople,
  cancelDelegation,
  delegationStateBadgeClass,
  delegationStateLabel,
  rejectDelegation,
} from "@/lib/delegations-client";

type DecisionKind = "approve" | "reject" | "cancel" | null;

function DetailRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-1 gap-1 py-2 sm:grid-cols-3 sm:gap-4">
      <dt className="text-sm font-medium text-text-secondary">{label}</dt>
      <dd className="text-sm text-text-primary sm:col-span-2">{children}</dd>
    </div>
  );
}

export function DelegationReview({
  delegation,
  employees,
  readOnly = false,
  backHref = "/dashboard/hr-admin/delegations",
  title = "Review delegation request",
}: {
  delegation: Delegation;
  /** Only used for the approve panel's delegate picker; ignored when readOnly. */
  employees: Employee[];
  /** Approver-side view: show the record, never the HR decision controls. */
  readOnly?: boolean;
  backHref?: string;
  title?: string;
}) {
  const router = useRouter();
  const [kind, setKind] = useState<DecisionKind>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const showApproveReject = !readOnly && delegation.state === "requested";
  const showCancel =
    !readOnly &&
    (delegation.state === "scheduled" || delegation.state === "active");
  const delegates = approverRolePeople(employees).filter(
    (employee) => employee.user_id !== delegation.approver
  );

  const period = delegation.ends_on
    ? `${delegation.starts_on} \u2192 ${delegation.ends_on}`
    : `From ${delegation.starts_on} (open-ended)`;

  function closePanel() {
    setKind(null);
    setError("");
  }

  function openKind(next: DecisionKind) {
    setKind((current) => (current === next ? null : next));
    setError("");
  }

  async function submitDecision(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    const formData = new FormData(event.currentTarget);
    const reason = String(formData.get("decision_reason") || "").trim();
    if (!reason) {
      setError("A decision reason is required.");
      return;
    }
    if (kind === "approve") {
      const delegate = String(formData.get("delegate") || "");
      if (!delegate) {
        setError("Select the delegate for the approved delegation.");
        return;
      }
    }

    setLoading(true);
    try {
      if (kind === "approve") {
        await approveDelegation(delegation.id, {
          delegate: Number(formData.get("delegate")),
          decision_reason: reason,
        });
      } else if (kind === "reject") {
        await rejectDelegation(delegation.id, reason);
      } else if (kind === "cancel") {
        await cancelDelegation(delegation.id, reason);
      }
      closePanel();
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

  const submitLabel =
    kind === "approve"
      ? "Confirm approval"
      : kind === "reject"
        ? "Confirm rejection"
        : "Confirm cancellation";

  return (
    <div className="space-y-6">
      <div>
        <Link
          href={backHref}
          className="inline-flex items-center gap-1 text-sm font-medium text-brand-primary hover:text-brand-primary-hover"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to delegations
        </Link>
        <div className="mt-2 flex items-center gap-3">
          <h2 className="text-2xl font-bold text-text-primary">{title}</h2>
          <span
            className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${delegationStateBadgeClass(delegation.state)}`}
          >
            {delegationStateLabel(delegation.state)}
          </span>
        </div>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <dl className="divide-y divide-border-default">
          <DetailRow label="Approver">
            <span className="font-medium">{delegation.approver_name}</span>
          </DetailRow>
          <DetailRow label="Approver role">
            {delegation.approver_role}
          </DetailRow>
          <DetailRow label="Delegate">
            {delegation.delegate_name || "Not yet assigned"}
          </DetailRow>
          <DetailRow label="Period">{period}</DetailRow>
          <DetailRow label="Request reason">
            {delegation.request_reason || "—"}
          </DetailRow>
          <DetailRow label="Requested by">
            {delegation.requested_by_name}
          </DetailRow>
          {delegation.decision_reason && (
            <DetailRow label="Decision reason">
              {delegation.decision_reason}
            </DetailRow>
          )}
          {delegation.decided_at && (
            <DetailRow label="Decision date">
              {delegation.decided_at.replace("T", " ").replace("Z", "")}
            </DetailRow>
          )}
        </dl>
      </div>

      {showApproveReject && (
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => openKind("approve")}
            className="inline-flex items-center gap-1.5 rounded-md bg-button-primary px-4 py-2 font-medium text-button-primary-foreground hover:bg-button-primary-hover"
          >
            <Check className="h-4 w-4" />
            Approve
          </button>
          <button
            type="button"
            onClick={() => openKind("reject")}
            className="inline-flex items-center gap-1.5 rounded-md border border-status-rejected bg-status-rejected-subtle px-4 py-2 font-medium text-status-rejected hover:bg-surface-hover"
          >
            <X className="h-4 w-4" />
            Reject
          </button>
        </div>
      )}

      {showCancel && (
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => openKind("cancel")}
            className="inline-flex items-center gap-1.5 rounded-md border border-status-rejected bg-status-rejected-subtle px-4 py-2 font-medium text-status-rejected hover:bg-surface-hover"
          >
            <X className="h-4 w-4" />
            Cancel delegation
          </button>
        </div>
      )}

      {kind !== null && (
        <form
          onSubmit={submitDecision}
          className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle"
        >
          <h3 className="text-lg font-semibold text-text-primary">
            {kind === "approve"
              ? "Confirm the delegate"
              : kind === "reject"
                ? "Reject this request"
                : "Cancel this delegation"}
          </h3>
          <p className="mt-1 text-sm text-text-secondary">
            {kind === "approve"
              ? "The selected person temporarily acts for the approver while the delegation is active."
              : "HR decisions require a reason. The reason is recorded on the delegation."}
          </p>

          {kind === "approve" && (
            <div className="mt-4">
              <label
                htmlFor="delegate"
                className="mb-1 block text-sm font-medium text-text-primary"
              >
                Delegate
              </label>
              <select
                id="delegate"
                name="delegate"
                defaultValue={delegation.delegate ?? ""}
                className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-sm text-text-primary focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
              >
                <option value="">Select the delegate</option>
                {delegates.map((employee) => (
                  <option key={employee.id} value={employee.user_id}>
                    {employee.full_name}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="mt-4">
            <label
              htmlFor="decision_reason"
              className="mb-1 block text-sm font-medium text-text-primary"
            >
              Decision reason
            </label>
            <textarea
              id="decision_reason"
              name="decision_reason"
              rows={3}
              className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-sm text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
              placeholder="Explain this HR decision."
            />
          </div>

          {error && (
            <div className="mt-4 rounded-md bg-status-rejected-subtle p-3 text-sm text-status-rejected">
              {error}
            </div>
          )}

          <div className="mt-4 flex items-center gap-3">
            <button
              type="submit"
              disabled={loading}
              className="rounded-md bg-button-primary px-4 py-2 font-medium text-button-primary-foreground hover:bg-button-primary-hover focus:outline-none focus:ring-2 focus:ring-input-ring-focus disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? "Saving..." : submitLabel}
            </button>
            <button
              type="button"
              onClick={closePanel}
              className="rounded-md border border-border-default bg-button-secondary px-4 py-2 font-medium text-text-secondary hover:bg-button-secondary-hover"
            >
              Close
            </button>
          </div>
        </form>
      )}
    </div>
  );
}