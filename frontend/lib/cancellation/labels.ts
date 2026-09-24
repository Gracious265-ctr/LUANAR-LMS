import type {
  CancellationBlockedReason,
  CancellationRequestStatus,
  CancellationStageStatus,
  EmployeeNotificationState,
} from "./types";

export const BLOCKED_REASON_TEXT: Record<CancellationBlockedReason, string> = {
  not_cancellable_status:
    "This application cannot be cancelled in its current state.",
  leave_already_started: "Leave has already started.",
  open_request_exists: "A cancellation request is already pending.",
  no_cancellation_approvers:
    "No Supervisor or HOD approval chain exists for this application.",
};

export const REQUEST_STATUS_LABEL: Record<CancellationRequestStatus, string> = {
  pending: "Pending",
  approved: "Approved",
  rejected: "Rejected",
};

export const REQUEST_STATUS_BADGE: Record<
  CancellationRequestStatus,
  string
> = {
  pending: "bg-status-pending-subtle text-status-pending",
  approved: "bg-status-approved-subtle text-status-approved",
  rejected: "bg-status-rejected-subtle text-status-rejected",
};

export const NOTIFICATION_LABEL: Record<EmployeeNotificationState, string> = {
  pending: "Pending",
  sent: "Sent",
  failed: "Failed",
  not_required: "Not required",
};

export const STAGE_STATUS_LABEL: Record<CancellationStageStatus, string> = {
  waiting: "Waiting",
  pending: "Pending",
  approved: "Approved",
  rejected: "Rejected",
  not_reached: "Not reached",
};