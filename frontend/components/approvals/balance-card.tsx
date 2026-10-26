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
          Requested days exceed the available balance.
        </p>
      )}
      <p className="mt-3 text-xs text-text-muted">
        Balance is displayed for information only and cannot be changed here.
      </p>
    </Panel>
  );
}