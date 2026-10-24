/** One row of the in-app notification feed (refinement unit 08 §2.2). */
export interface Notification {
  id: string;
  /** Dotted event name, e.g. `approval.assigned`. */
  event_type: string;
  message: string;
  /** Relative path inside the app, e.g. `/dashboard/approvals/abc`. */
  link: string;
  is_read: boolean;
  created_at: string;
}
