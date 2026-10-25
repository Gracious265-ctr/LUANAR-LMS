export type LeaveApplicationStatus =
  | "draft"
  | "pending"
  | "approved"
  | "rejected"
  | "cancelled";

/** One row of a dashboard list (needs-attention, drafts or recent). */
export interface LeaveApplicationSummary {
  id: string;
  leave_type: string | null;
  start_date: string | null;
  end_date: string | null;
  status: LeaveApplicationStatus;
  last_comment_excerpt: string | null;
  created_at: string;
  updated_at: string;
}

/** One balance ring: `used` out of `total` days for a leave type. */
export interface LeaveBalance {
  leave_type: string;
  used: number;
  total: number;
}

/** The employee's next approved, not-yet-started leave, if any. */
export interface UpcomingLeave {
  id: string;
  leave_type: string | null;
  start_date: string;
  end_date: string;
  /** Days from today until `start_date`; 0 means it starts today. */
  days_until: number;
}

export interface LeaveDashboardData {
  balances: LeaveBalance[];
  /** Applications awaiting a decision (submitted, still in the chain). */
  pending_count: number;
  upcoming_leave: UpcomingLeave | null;
  needs_attention: LeaveApplicationSummary[];
  drafts: LeaveApplicationSummary[];
  recent: LeaveApplicationSummary[];
}

export async function getLeaveDashboard(): Promise<LeaveDashboardData> {
  const res = await fetch("/api/leave/dashboard/", {
    credentials: "include",
  });
  if (!res.ok) throw new Error("Failed to load your dashboard");
  return res.json();
}
