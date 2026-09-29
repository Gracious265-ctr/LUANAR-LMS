import {
  CheckCircle2,
  Clock,
  FileText,
  History,
  Lock,
  RotateCcw,
  XCircle,
  type LucideIcon,
} from "lucide-react";

import type { BlockStatus, PlanDecisionAction, PlanStatus, StageStatus } from "./types";

export interface StatusMeta {
  label: string;
  icon: LucideIcon;
  badgeClass: string;
  textClass: string;
  dotClass: string;
}

export const PLAN_STATUS_META: Record<PlanStatus, StatusMeta> = {
  draft: {
    label: "Draft",
    icon: FileText,
    badgeClass: "bg-surface-secondary text-text-secondary",
    textClass: "text-text-secondary",
    dotClass: "bg-text-muted",
  },
  submitted: {
    label: "Submitted",
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
};

export const BLOCK_STATUS_META: Record<BlockStatus, StatusMeta> = {
  proposed: {
    label: "Proposed",
    icon: Clock,
    badgeClass: "bg-surface-secondary text-text-secondary",
    textClass: "text-text-secondary",
    dotClass: "bg-text-muted",
  },
  reserved: {
    label: "Reserved",
    icon: Lock,
    badgeClass: "bg-status-pending-subtle text-status-pending",
    textClass: "text-status-pending",
    dotClass: "bg-status-pending",
  },
  confirmed: {
    label: "Confirmed",
    icon: CheckCircle2,
    badgeClass: "bg-status-approved-subtle text-status-approved",
    textClass: "text-status-approved",
    dotClass: "bg-status-approved",
  },
  lapsed: {
    label: "Lapsed",
    icon: Clock,
    badgeClass: "bg-surface-muted text-text-muted",
    textClass: "text-text-muted",
    dotClass: "bg-text-muted",
  },
  released: {
    label: "Released",
    icon: RotateCcw,
    badgeClass: "bg-status-cancelled-subtle text-status-cancelled",
    textClass: "text-status-cancelled",
    dotClass: "bg-status-cancelled",
  },
};

export const STAGE_STATUS_META: Record<StageStatus, StatusMeta> = {
  waiting: {
    label: "Waiting",
    icon: Clock,
    badgeClass: "bg-surface-muted text-text-muted",
    textClass: "text-text-muted",
    dotClass: "bg-text-muted",
  },
  pending: {
    label: "Pending",
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
  skipped: {
    label: "Skipped",
    icon: History,
    badgeClass: "bg-surface-muted text-text-muted",
    textClass: "text-text-muted",
    dotClass: "bg-text-muted",
  },
};

export interface ActionMeta {
  label: string;
  shortLabel: string;
  icon: LucideIcon;
  badgeClass: string;
  buttonClass: string;
}

export const PLAN_ACTION_META: Record<PlanDecisionAction, ActionMeta> = {
  approve: {
    label: "Approved",
    shortLabel: "Approve",
    icon: CheckCircle2,
    badgeClass: "bg-status-approved-subtle text-status-approved",
    buttonClass:
      "bg-[#009119] text-white hover:bg-[#008017] focus:ring-2 focus:ring-[#009119]/40",
  },
  reject: {
    label: "Rejected",
    shortLabel: "Reject",
    icon: XCircle,
    badgeClass: "bg-status-rejected-subtle text-status-rejected",
    buttonClass:
      "border border-status-rejected bg-status-rejected-subtle text-status-rejected hover:bg-surface-hover",
  },
};

export function planDecisionVerb(action: PlanDecisionAction): string {
  return action === "approve" ? "approve" : "reject";
}