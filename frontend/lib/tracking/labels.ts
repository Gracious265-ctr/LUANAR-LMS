import {
  Ban,
  CheckCircle2,
  CircleDot,
  Clock,
  RefreshCw,
  RotateCcw,
  Send,
  UserCheck,
  XCircle,
  type LucideIcon,
} from "lucide-react";

import type {
  EventType,
  TrackingEvent,
  TrackingStage,
  TrackingStatus,
} from "./types";

export interface StatusMeta {
  label: string;
  icon: LucideIcon;
  /** Badge classes (subtle fill + text), e.g. "bg-status-pending-subtle text-status-pending". */
  badgeClass: string;
  /** Text colour classes for status text elsewhere. */
  textClass: string;
  /** Solid dot colour used by the stepper / timeline. */
  dotClass: string;
}

export const STATUS_META: Record<TrackingStatus, StatusMeta> = {
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
    icon: Ban,
    badgeClass: "bg-status-cancelled-subtle text-status-cancelled",
    textClass: "text-status-cancelled",
    dotClass: "bg-status-cancelled",
  },
};

export interface EventMeta {
  label: string;
  icon: LucideIcon;
}

const EVENT_ICONS: Record<string, LucideIcon> = {
  submitted: Send,
  approved: CheckCircle2,
  rejected: XCircle,
  correction_requested: RotateCcw,
  resubmitted: RefreshCw,
  reassigned: UserCheck,
};

/**
 * Display title for a timeline event. Stage-role labels are resolved from the
 * stage they reference (falling back to the acting role). Unknown event types
 * get a neutral "Workflow update" fallback rather than a missing label.
 */
export function eventTitle(event: TrackingEvent, stages: TrackingStage[]): string {
  const stageLabel = stages.find((s) => s.order === event.stage_order)?.role_label;
  const roleLabel = stageLabel || event.actor.role_label;

  switch (event.type as EventType) {
    case "submitted":
      return "Application submitted";
    case "approved":
      return `${roleLabel} approved`;
    case "rejected":
      return `${roleLabel} rejected`;
    case "correction_requested":
      return `${roleLabel} returned for correction`;
    case "resubmitted":
      return event.resubmission_number
        ? `You resubmitted (#${event.resubmission_number})`
        : "You resubmitted";
    case "reassigned":
      return "Application reassigned";
    default:
      return "Workflow update";
  }
}

export function eventIcon(type: string): LucideIcon {
  return EVENT_ICONS[type] ?? CircleDot;
}