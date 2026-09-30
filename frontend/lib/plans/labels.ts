import {
  CalendarCheck,
  CalendarClock,
  CalendarX,
  CheckCircle2,
  CircleDashed,
  Clock,
  Hourglass,
  Undo2,
  XCircle,
  type LucideIcon,
} from "lucide-react";

import type { BadgeTone } from "@/components/ui/badge";
import type {
  BlockStatus,
  PlanAction,
  PlanStageStatus,
  PlanStatus,
} from "./types";

export interface StatusMeta {
  label: string;
  icon: LucideIcon;
  badgeTone: BadgeTone;
  textClass: string;
  dotClass: string;
}

/** The plan itself. A plan is a draft until it is submitted, then terminal. */
export const PLAN_STATUS_META: Record<PlanStatus, StatusMeta> = {
  draft: {
    label: "Draft",
    icon: CalendarClock,
    badgeTone: "draft",
    textClass: "text-text-secondary",
    dotClass: "bg-text-muted",
  },
  submitted: {
    label: "Awaiting approval",
    icon: Hourglass,
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
};

/**
 * A block inside an approved plan.
 *
 * `proposed` only ever appears on a draft. `reserved` is the state the final
 * approval puts a block into: the balance is held, but the owner still has to
 * confirm inside the lead window or it lapses. `confirmed` is a real booking.
 */
export const BLOCK_STATUS_META: Record<BlockStatus, StatusMeta> = {
  proposed: {
    label: "Proposed",
    icon: CircleDashed,
    badgeTone: "draft",
    textClass: "text-text-secondary",
    dotClass: "bg-text-muted",
  },
  reserved: {
    label: "Reserved",
    icon: CalendarClock,
    badgeTone: "pending",
    textClass: "text-status-pending",
    dotClass: "bg-status-pending",
  },
  confirmed: {
    label: "Confirmed",
    icon: CalendarCheck,
    badgeTone: "approved",
    textClass: "text-status-approved",
    dotClass: "bg-status-approved",
  },
  lapsed: {
    label: "Lapsed",
    icon: CalendarX,
    badgeTone: "cancelled",
    textClass: "text-status-cancelled",
    dotClass: "bg-status-cancelled",
  },
  released: {
    label: "Released",
    icon: Undo2,
    badgeTone: "neutral",
    textClass: "text-text-secondary",
    dotClass: "bg-text-muted",
  },
};

/** A section of the chain. Never `skipped`: a section is always decided. */
export const STAGE_STATUS_META: Record<PlanStageStatus, StatusMeta> = {
  waiting: {
    label: "Waiting",
    icon: Clock,
    badgeTone: "muted",
    textClass: "text-text-muted",
    dotClass: "bg-text-muted",
  },
  pending: {
    label: "Awaiting decision",
    icon: Hourglass,
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
};

export interface ActionMeta {
  label: string;
  shortLabel: string;
  icon: LucideIcon;
  badgeTone: BadgeTone;
  buttonClass: string;
}

/** A plan decision is approve or reject — a plan is never sent back for edits. */
export const ACTION_META: Record<PlanAction, ActionMeta> = {
  approve: {
    label: "Approved",
    shortLabel: "Approve",
    icon: CheckCircle2,
    badgeTone: "approved",
    buttonClass:
      "bg-[#009119] text-white hover:bg-[#008017] focus:ring-2 focus:ring-[#009119]/40",
  },
  reject: {
    label: "Rejected",
    shortLabel: "Reject",
    icon: XCircle,
    badgeTone: "rejected",
    buttonClass:
      "border border-status-rejected bg-status-rejected-subtle text-status-rejected hover:bg-surface-hover",
  },
};

/** Past-tense verb for a plan's terminal state, for toast copy. */
export function planVerb(status: PlanStatus): string {
  switch (status) {
    case "approved":
      return "approved";
    case "rejected":
      return "rejected";
    case "submitted":
      return "submitted for approval";
    default:
      return "saved";
  }
}

/**
 * Why the decision panel is read-only.
 *
 * The backend is the authority; these strings only explain its answer in the
 * caller's own terms, so a user is never left guessing why a button is off.
 */
export function restrictionLabel(
  reason: string | null,
  stageLabel: string | null,
  status: PlanStatus | null
): string {
  switch (reason) {
    case "self_plan":
      return "You cannot decide on your own plan.";
    case "already_decided":
      return "You have already made a decision on this plan.";
    case "not_current_stage":
      return stageLabel
        ? `This plan is currently with the ${stageLabel}.`
        : "This plan has not reached your stage yet.";
    case "plan_closed":
      return status
        ? `This plan is ${PLAN_STATUS_META[status]?.label.toLowerCase() ?? "closed"}.`
        : "This plan is closed.";
    default:
      return "You are not allowed to decide on this plan.";
  }
}

export function restrictionTitle(kind: PlanAction): string {
  return kind === "approve" ? "Approve plan" : "Reject plan";
}

/**
 * The names of the people who may still act on a stage.
 *
 * An unclaimed stage with several candidates is the normal case, so it is
 * phrased as a list rather than a single "waiting on". `assigned_approver`
 * is only populated once somebody has claimed the stage.
 */
export function candidateSummary(stage: {
  is_claimed: boolean;
  approver_name: string;
  eligible_approvers: { name: string }[];
}): string {
  if (stage.is_claimed) {
    return stage.approver_name;
  }
  const names = stage.eligible_approvers.map((approver) => approver.name);
  if (names.length === 0) {
    return "Nobody available";
  }
  if (names.length <= 2) {
    return names.join(" or ");
  }
  return `${names.slice(0, 2).join(", ")} and ${names.length - 2} more`;
}
