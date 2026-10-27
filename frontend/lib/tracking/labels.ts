import {
  Ban,
  CheckCircle2,
  CircleDot,
  Clock,
  RefreshCw,
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
import type { BadgeTone } from "@/components/ui/badge";
import { STATUS_SOLID, STATUS_TEXT } from "@/lib/status-styles";

export interface StatusMeta {
  label: string;
  icon: LucideIcon;
  /** The `tone` key this status renders with on a <Badge>. */
  badgeTone: BadgeTone;
  /** Text colour classes for status text elsewhere. */
  textClass: string;
  /** Solid dot colour used by the stepper / timeline. */
  dotClass: string;
}

export const STATUS_META: Record<TrackingStatus, StatusMeta> = {
  pending: {
    label: "Pending Approval",
    icon: Clock,
    badgeTone: "pending",
    textClass: STATUS_TEXT.pending,
    dotClass: STATUS_SOLID.pending,
  },
  approved: {
    label: "Approved",
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
  cancelled: {
    label: "Cancelled",
    icon: Ban,
    badgeTone: "cancelled",
    textClass: STATUS_TEXT.cancelled,
    dotClass: STATUS_SOLID.cancelled,
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