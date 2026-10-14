<<<<<<< HEAD
import { AlertTriangle, Wallet } from "lucide-react";

import type { ApprovalDetail } from "@/lib/approvals/types";

import { Card } from "./primitives";

export function BalanceCard({ detail }: { detail: ApprovalDetail }) {
  const { balance, application } = detail;
  const requested = application.working_days;
  const exceedsBalance =
    balance.available !== null && requested > balance.available;

  return (
    <Card title="Leave balance" icon={<Wallet className="h-4 w-4" />}>
      <div className="flex items-end justify-between">
        <div>
          <p className="text-3xl font-bold text-text-primary">
            {balance.available ?? "Unknown"}
            {balance.available !== null && (
              <span className="ml-1 text-base font-medium text-text-muted">
                days
              </span>
            )}
          </p>
          <p className="text-sm text-text-secondary">Available for this leave</p>
        </div>
      </div>

      <dl className="mt-4 space-y-2">
        <div className="flex justify-between text-sm">
          <dt className="text-text-secondary">Annual entitlement</dt>
          <dd className="font-medium text-text-primary">
            {balance.entitlement === null
              ? "Unknown"
              : `${balance.entitlement} days`}
          </dd>
        </div>
        <div className="flex justify-between text-sm">
          <dt className="text-text-secondary">Used so far</dt>
          <dd className="font-medium text-text-primary">
            {balance.used === null ? "Unknown" : `${balance.used} days`}
          </dd>
        </div>
        <div className="flex justify-between text-sm">
          <dt className="text-text-secondary">Requested (this leave)</dt>
          <dd className="font-medium text-text-primary">{requested} days</dd>
        </div>
      </dl>

      {exceedsBalance && (
        <p className="mt-4 flex items-start gap-2 rounded-lg bg-status-rejected-subtle px-3 py-2 text-sm text-status-rejected">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          The requested days exceed the employee&apos;s available balance.
        </p>
      )}
    </Card>
=======
import { AlertTriangle } from "lucide-react";

import type { ApprovalReview } from "@/lib/approvals/types";
import { STATUS_STYLES } from "@/lib/status-styles";

import { DetailRow, Panel } from "./panel";

function isAnnual(data: ApprovalReview): boolean {
  return (data.rules.leave_type.code || "").toUpperCase().includes("ANNUAL");
}

export function BalanceCard({ data }: { data: ApprovalReview }) {
  const balance = data.balance;
  const available = Number(balance.available) || 0;
  const afterIfApproved = data.rules.balance_after_if_approved;
  const requested =
    afterIfApproved != null ? Math.max(0, available - afterIfApproved) : null;
  const requestedExceeds =
    requested != null && requested > available && requested > 0;

  return (
    <Panel title="Leave balance">
      <dl className="divide-y divide-border-default">
        <DetailRow label="Entitlement">
          {balance.entitlement != null ? balance.entitlement : "—"} days
        </DetailRow>
        <DetailRow label="Used">
          {balance.used != null ? balance.used : "—"} days
        </DetailRow>
        <DetailRow label="Available">{available} days</DetailRow>
        {isAnnual(data) && requested != null && (
          <DetailRow label="Requested">{requested} days</DetailRow>
        )}
      </dl>
      {requestedExceeds && (
        <p
          role="status"
          className={`mt-3 flex items-start gap-2 rounded-lg p-3 text-sm ${STATUS_STYLES.pending}`}
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          Requested days exceed the available balance. This is shown for
          information only and does not change the decision options.
        </p>
      )}
      <p className="mt-3 text-xs text-text-muted">
        Balance is displayed for information only and cannot be changed here.
      </p>
    </Panel>
>>>>>>> feature/plans-teams
  );
}