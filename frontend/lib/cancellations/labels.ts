import { CheckCircle2, Clock, XCircle, type LucideIcon } from "lucide-react";

import type {
  CancellationAction,
  CancellationKind,
  CancellationStatus,
  EmployeeNotificationState,
} from "./types";
import type { BadgeTone } from "@/components/ui/badge";
import { STATUS_SOLID, STATUS_TEXT } from "@/lib/status-styles";

export interface StatusMeta {
  label: string;
  icon: LucideIcon;
  badgeTone: BadgeTone;
  textClass: string;
  dotClass: string;
}

export const REQUEST_STATUS_META: Record<CancellationStatus, StatusMeta> = {
  pending: {
    label: "Pending",
    icon: Clock,
    badgeTone: "pending",
    textClass: STATUS_TEXT.pending,
    dotClass: STATUS_SOLID.pending,
  },
  approved: {
    label: "Cancelled",
    icon: CheckCircle2,
    badgeTone: "approved",
    textClass: STATUS_TEXT.approved,
    dotClass: STATUS_SOLID.approved,
  },
  rejected: {
    label: "Rejected",
    icon: XCircle,
    badgeTone: "rejected",
    textClass: STATUS_TEXT.rejected,
    dotClass: STATUS_SOLID.rejected,
  },
};

export const NOTIFICATION_STATE_LABELS: Record<EmployeeNotificationState, string> = {
  pending: "Pending",
  sent: "Sent",
  failed: "Failed",
  not_required: "Not required",
};

export const KIND_LABELS: Record<CancellationKind, string> = {
  withdrawal: "Withdrawal",
  approved_leave: "Cancellation request",
};

export function actionLabel(action: CancellationAction): string {
  return action === "withdraw" ? "Withdraw application" : "Request cancellation";
}

export function confirmLabel(action: CancellationAction): string {
  return action === "withdraw"
    ? "Yes, withdraw application"
    : "Submit cancellation request";
}

export function blockedReasonLabel(reason: string | null): string | null {
  switch (reason) {
    case "not_cancellable_status":
      return "This application can no longer be cancelled.";
    case "leave_already_started":
      return "Leave has already started and cannot be cancelled.";
    case "open_request_exists":
      return "A cancellation request is still awaiting approval.";
    case "no_cancellation_approvers":
      return "No Supervisor or HOD is available to approve a cancellation.";
    default:
      return reason ? "This application cannot be cancelled right now." : null;
  }
}

export function consequenceLine(
  action: CancellationAction,
  estimatedDays: string | null,
  financialYear: string | null
): string {
  const base =
    action === "withdraw"
      ? "This application will be withdrawn immediately."
      : "Your Supervisor/HOD must approve this. Your leave stays active until then.";
  if (estimatedDays && Number(estimatedDays) > 0) {
    return `${base} About ${formatDayCount(estimatedDays)} annual leave will be restored to your ${financialYear ?? "FY"} balance if approved.`;
  }
  return base;
}

export function outcomeBanner(
  status: CancellationStatus,
  restoredDays: string,
  financialYear: string | null
): string | null {
  if (status === "approved") {
    if (Number(restoredDays) > 0) {
      return `Leave cancelled. ${formatDayCount(restoredDays)} annual days restored to FY ${financialYear ?? "—"} balance.`;
    }
    return "No annual leave balance was affected.";
  }
  if (status === "rejected") {
    return "Your leave remains approved.";
  }
  return null;
}

export function formatDayCount(days: string | number): string {
  const value = Number(days);
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}