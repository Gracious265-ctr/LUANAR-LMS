import type {
  CancellationDetail,
  CancellationEligibility,
  CancellationListResponse,
  CancellationRequest,
  CancellationRow,
} from "@/lib/cancellations/types";

export function makeEligibility(
  overrides: Partial<CancellationEligibility> = {}
): CancellationEligibility {
  return {
    application_id: "app-1",
    reference: "LV-2026-27-800123",
    cancellation_action: "withdraw",
    cancellation_blocked_reason: null,
    estimated_restoration_days: null,
    restoration_financial_year: null,
    leave_started: false,
    starts_in_days: 12,
    ...overrides,
  };
}

export function makeRequest(
  overrides: Partial<CancellationRequest> = {}
): CancellationRequest {
  return {
    id: "canc-1",
    kind: "approved_leave",
    status: "pending",
    reason: "The university rescheduled my teaching block.",
    requested_at: "2026-10-12T07:15:03Z",
    decided_at: null,
    stage_version: 1,
    application_status_at_request: "approved",
    balance_restored_days: "0.0",
    restored_financial_year: null,
    employee_notification_state: "pending",
    stages: [
      {
        id: "stg-1",
        order: 1,
        role: "supervisor",
        role_label: "Supervisor",
        status: "pending",
        approver_name: "Mr. Chikondi Banda",
        decided_at: null,
        comment: null,
      },
      {
        id: "stg-2",
        order: 2,
        role: "hod",
        role_label: "HOD",
        status: "waiting",
        approver_name: "Dr. Grace Mwale",
        decided_at: null,
        comment: null,
      },
    ],
    ...overrides,
  };
}

export function makeApprovedRequest(
  overrides: Partial<CancellationRequest> = {}
): CancellationRequest {
  return makeRequest({
    status: "approved",
    decided_at: "2026-10-15T14:22:19Z",
    balance_restored_days: "10.0",
    restored_financial_year: "2026-27",
    employee_notification_state: "sent",
    stages: [
      {
        id: "stg-1",
        order: 1,
        role: "supervisor",
        role_label: "Supervisor",
        status: "approved",
        approver_name: "Mr. Chikondi Banda",
        decided_at: "2026-10-13T09:00:00Z",
        comment: "Approved.",
      },
      {
        id: "stg-2",
        order: 2,
        role: "hod",
        role_label: "HOD",
        status: "approved",
        approver_name: "Dr. Grace Mwale",
        decided_at: "2026-10-15T14:22:19Z",
        comment: "Approved.",
      },
    ],
    ...overrides,
  });
}

export function makeRejectedRequest(
  overrides: Partial<CancellationRequest> = {}
): CancellationRequest {
  return makeRequest({
    status: "rejected",
    decided_at: "2026-10-14T10:00:00Z",
    employee_notification_state: "sent",
    stages: [
      {
        id: "stg-1",
        order: 1,
        role: "supervisor",
        role_label: "Supervisor",
        status: "rejected",
        approver_name: "Mr. Chikondi Banda",
        decided_at: "2026-10-14T10:00:00Z",
        comment: "Cover has already been arranged for these dates.",
      },
      {
        id: "stg-2",
        order: 2,
        role: "hod",
        role_label: "HOD",
        status: "not_reached",
        approver_name: "Dr. Grace Mwale",
        decided_at: null,
        comment: null,
      },
    ],
    ...overrides,
  });
}

export function makeRow(overrides: Partial<CancellationRow> = {}): CancellationRow {
  return {
    request_id: "canc-1",
    application_id: "app-1",
    reference: "LV-2026-27-800123",
    employee_name: "Chikondi Mbewe",
    leave_type: { id: 1, code: "Annual", name: "Annual Leave" },
    start_date: "2026-12-07",
    end_date: "2026-12-18",
    working_days: 10,
    requested_at: "2026-10-12T07:15:03Z",
    current_stage_role: "supervisor",
    current_stage_role_label: "Supervisor",
    stage_version: 1,
    leave_started: false,
    starts_in_days: 12,
    ...overrides,
  };
}

export function makeListResponse(
  rows: CancellationRow[],
  overrides: Partial<CancellationListResponse> = {}
): CancellationListResponse {
  return {
    tab: "pending",
    count: rows.length,
    next: null,
    previous: null,
    results: rows,
    ...overrides,
  };
}

export function makeDetail(
  overrides: Partial<CancellationDetail> = {}
): CancellationDetail {
  return {
    request: makeRequest({ id: "canc-1" }),
    requested_by_name: "Chikondi Mbewe",
    stage_version: 1,
    my_decision: null,
    can_decide: true,
    application: {
      id: "app-1",
      reference: "LV-2026-27-800123",
      status: "approved",
      leave_type: { id: 1, code: "Annual", name: "Annual Leave" },
      start_date: "2026-12-07",
      end_date: "2026-12-18",
      working_days: 10,
      calendar_days: 12,
      reason: "Family visit",
      financial_year_label: "2026-27",
      submitted_at: "2026-10-12T07:15:03Z",
    },
    balance_impact: { restore_days: "0.0", restore_financial_year: null },
    leave_started: false,
    ...overrides,
  };
}