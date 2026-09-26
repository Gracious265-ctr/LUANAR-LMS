import { apiClient } from "./api-client";

export interface TimelineActor {
  id: number;
  name: string;
}

export interface TimelineStateTransition {
  from: string;
  to: string;
}

export interface TimelineEntry {
  id: number;
  kind: string;
  action: string;
  action_label: string;
  occurred_at: string;
  actor: TimelineActor | null;
  target_type: string;
  state_transition: TimelineStateTransition;
  summary: string;
  metadata: Record<string, unknown>;
  stage_order: number | null;
  resubmission_number: number | null;
}

export interface TimelineApplication {
  id: string;
  reference_number: string;
  status: string;
  leave_type_name: string;
  start_date: string | null;
  end_date: string | null;
  working_days: number | null;
  employee_name?: string;
}

export interface ApplicationTimeline {
  application: TimelineApplication;
  entries: TimelineEntry[];
}

export async function getApplicationTimeline(
  id: string
): Promise<ApplicationTimeline> {
  return apiClient<ApplicationTimeline>(
    `/api/v1/applications/${id}/history/`
  );
}

export async function getMyLeaveHistory(): Promise<ApplicationTimeline[]> {
  return apiClient<ApplicationTimeline[]>("/api/v1/leave/my/history/");
}