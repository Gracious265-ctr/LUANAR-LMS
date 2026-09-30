import {
  Check,
  CheckCircle2,
  Clock,
  FileText,
  RotateCcw,
  X,
  XCircle,
  type LucideIcon,
} from "lucide-react";

import type { ApprovalAction, ApprovalStatus } from "./types";
import type { BadgeTone } from "@/components/ui/badge";

export interface StatusMeta {
  label: string;
  icon: LucideIcon;
  badgeTone: BadgeTone;
  textClass: string;
  dotClass: string;
}

export const STATUS_META: Record<ApprovalStatus, StatusMeta> = {
  pending: {
    label: "Pending Approval",
    icon: Clock,
    badgeTone: "pending",
    textClass: "text-status-pending",
    dotClass: "bg-status-pending",
  },
  approved: {
    label: "Approved",
    icon: CheckCircle2,
    badgeTone: "approved",
    textClass: "text-status-approved",
    dotClass: "bg-status-approved",
  },
  rejected: {
    label: "Rejected",
    icon: XCircle,
    badgeTone: "rejected",
    textClass: "text-status-rejected",
    dotClass: "bg-status-rejected",
  },
  correction_required: {
    label: "Correction Required",
    icon: RotateCcw,
    badgeTone: "correction",
    textClass: "text-status-correction",
    dotClass: "bg-status-correction",
  },
  cancelled: {
    label: "Cancelled",
    icon: XCircle,
    badgeTone: "cancelled",
    textClass: "text-status-cancelled",
    dotClass: "bg-status-cancelled",
  },
  draft: {
    label: "Draft",
    icon: FileText,
    badgeTone: "draft",
    textClass: "text-text-secondary",
    dotClass: "bg-text-muted",
  },
  submitted: {
    label: "Submitted",
    icon: Clock,
    badgeTone: "draft",
    textClass: "text-text-secondary",
    dotClass: "bg-text-muted",
  },
};

export interface ActionMeta {
  label: string;
  shortLabel: string;
  icon: LucideIcon;
  /** The `tone` key this action renders with on an <ActionBadge>. */
  badgeTone: BadgeTone;
  /** Solid button classes for the decision panel / dialog confirm. */
  buttonClass: string;
}

export const ACTION_META: Record<ApprovalAction, ActionMeta> = {
  approve: {
    label: "Approved",
    shortLabel: "Approve",
    icon: Check,
    badgeTone: "approved",
    buttonClass:
      "bg-[#009119] text-white hover:bg-[#008017] focus:ring-2 focus:ring-[#009119]/40",
  },
  reject: {
    label: "Rejected",
    shortLabel: "Reject",
    icon: X,
    badgeTone: "rejected",
    buttonClass:
      "border border-status-rejected bg-status-rejected-subtle text-status-rejected hover:bg-surface-hover",
  },
  return_for_correction: {
    label: "Returned for Correction",
    shortLabel: "Return for Correction",
    icon: RotateCcw,
    badgeTone: "correction",
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
    case "self_application":
      return "You cannot decide on your own application.";
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