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
  );
}