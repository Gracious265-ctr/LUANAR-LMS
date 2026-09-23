import {
  Check,
  CheckCircle2,
  Clock,
  RotateCcw,
  X,
  XCircle,
  type LucideIcon,
} from "lucide-react";

import type { ApprovalAction, ApprovalStatus } from "./types";

export interface StatusMeta {
  label: string;
  icon: LucideIcon;
  badgeClass: string;
  textClass: string;
  dotClass: string;
}

export const STATUS_META: Record<ApprovalStatus, StatusMeta> = {
  pending: {
    label: "Pending Approval",
    icon: Clock,
    badgeClass: "bg-status-pending-subtle text-status-pending",
    textClass: "text-status-pending",
    dotClass: "bg-status-pending",
  },
  approved: {
    label: "Approved",
    icon: CheckCircle2,
    badgeClass: "bg-status-approved-subtle text-status-approved",
    textClass: "text-status-approved",
    dotClass: "bg-status-approved",
  },
  rejected: {
    label: "Rejected",
    icon: XCircle,
    badgeClass: "bg-status-rejected-subtle text-status-rejected",
    textClass: "text-status-rejected",
    dotClass: "bg-status-rejected",
  },
  correction_required: {
    label: "Correction Required",
    icon: RotateCcw,
    badgeClass: "bg-status-correction-subtle text-status-correction",
    textClass: "text-status-correction",
    dotClass: "bg-status-correction",
  },
  cancelled: {
    label: "Cancelled",
    icon: XCircle,
    badgeClass: "bg-status-cancelled-subtle text-status-cancelled",
    textClass: "text-status-cancelled",
    dotClass: "bg-status-cancelled",
  },
};

export interface ActionMeta {
  label: string;
  shortLabel: string;
  icon: LucideIcon;
  /** Classes used by the action buttons once a decision is recorded. */
  badgeClass: string;
  /** Solid button classes for the decision panel / dialog confirm. */
  buttonClass: string;
}

export const ACTION_META: Record<ApprovalAction, ActionMeta> = {
  approve: {
    label: "Approved",
    shortLabel: "Approve",
    icon: Check,
    badgeClass: "bg-status-approved-subtle text-status-approved",
    buttonClass:
      "bg-[#009119] text-white hover:bg-[#008017] focus:ring-2 focus:ring-[#009119]/40",
  },
  reject: {
    label: "Rejected",
    shortLabel: "Reject",
    icon: X,
    badgeClass: "bg-status-rejected-subtle text-status-rejected",
    buttonClass:
      "border border-status-rejected bg-status-rejected-subtle text-status-rejected hover:bg-surface-hover",
  },
  return_for_correction: {
    label: "Returned for Correction",
    shortLabel: "Return for Correction",
    icon: RotateCcw,
    badgeClass: "bg-status-correction-subtle text-status-correction",
    buttonClass:
      "border border-status-correction bg-status-correction-subtle text-status-correction hover:bg-surface-hover",
  },
};

export function restrictionLabel(
  reason: string | null,
  stageLabel: string | null,
  status: ApprovalStatus | null
): string {
  switch (reason) {
    case "already_decided":
      return "You have already made a decision on this application.";
    case "not_current_stage":
      return stageLabel
        ? `This application is currently with the ${stageLabel}.`
        : "This application has not reached your stage yet.";
    case "application_closed":
      return status
        ? `This application is ${STATUS_META[status]?.label.toLowerCase() ?? "closed"}.`
        : "This application is closed.";
    default:
      return "You are not allowed to decide on this application.";
  }
}

export function restrictionTitle(kind: ApprovalAction): string {
  switch (kind) {
    case "approve":
      return "Approve application";
    case "reject":
      return "Reject application";
    case "return_for_correction":
      return "Return for correction";
    default:
      return "Decision";
  }
}

export function decisionVerb(action: ApprovalAction): string {
  switch (action) {
    case "approve":
      return "approve";
    case "reject":
      return "reject";
    case "return_for_correction":
      return "return for correction";
  }
}

export function approvalVerb(status: ApprovalStatus): string {
  switch (status) {
    case "approved":
      return "approved";
    case "rejected":
      return "rejected";
    case "correction_required":
      return "returned for correction";
    default:
      return "updated";
  }
}