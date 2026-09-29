import type {
  PlanApprovalListItem,
  PlanApprovalListResponse,
  PlanBlock,
  PlanCapabilities,
  PlanDetail,
  PlanMeta,
  PlanRow,
  PendingConfirmationResponse,
} from "@/lib/plans/types";

export function makeMeta(overrides: Partial<PlanMeta> = {}): PlanMeta {
  return {
    id: "plan-1",
    period_start: "2026-07-01",
    period_end: "2027-06-30",
    financial_year_label: "FY 2026-27",
    status: "approved",
    status_label: "Approved",
    submitted_at: "2026-09-21T09:12:00Z",
    decided_at: "2026-09-22T10:00:00Z",
    submission_cycle: 1,
    ...overrides,
  };
}

export function makeBlock(overrides: Partial<PlanBlock> = {}): PlanBlock {
  return {
    id: "block-1",
    leave_type_id: 1,
    leave_type_code: "ANNUAL",
    leave_type_name: "Annual Leave",
    start_date: "2026-10-08",
    end_date: "2026-10-09",
    working_days: 2,
    status: "reserved",
    status_label: "Reserved",
    confirmation_window_start: "2026-09-24",
    confirmed_at: null,
    released_at: null,
    application_id: null,
    can_confirm: true,
    can_release: true,
    ...overrides,
  };
}

export function makePlanRow(overrides: Partial<PlanRow> = {}): PlanRow {
  return {
    id: "plan-1",
    period_start: "2026-07-01",
    period_end: "2027-06-30",
    financial_year_label: "FY 2026-27",
    status: "approved",
    status_label: "Approved",
    submitted_at: "2026-09-21T09:12:00Z",
    decided_at: "2026-09-22T10:00:00Z",
    submission_cycle: 1,
    employee_id: 2,
    employee_name: "Mphatso Kachale",
    block_count: 1,
    working_days: 2,
    blocks: [makeBlock()],
    ...overrides,
  };
}

export function makePlanDetail(overrides: Partial<PlanDetail> = {}): PlanDetail {
  return {
    meta: makeMeta(),
    employee: { id: 2, name: "Mphatso Kachale", department: "Registry" },
    blocks: [
      makeBlock(),
      makeBlock({
        id: "block-2",
        start_date: "2026-10-16",
        end_date: "2026-10-17",
        status: "confirmed",
        status_label: "Confirmed",
        can_confirm: false,
        can_release: true,
      }),
    ],
    stages: [
      {
        id: "stage-1",
        stage_order: 1,
        role: "supervisor",
        role_label: "Supervisor",
        assigned_approver_id: 9,
        approver_name: "Jane Phiri",
        status: "approved",
        status_label: "Approved",
        is_final: false,
        decision_version: 1,
      },
    ],
    decisions: [],
    access: "owner",
    can_decide: false,
    can_submit: false,
    my_decision: null,
    ...overrides,
  };
}

export function makeCapabilities(
  overrides: Partial<PlanCapabilities> = {}
): PlanCapabilities {
  return {
    is_approver: true,
    approver_pending_count: 2,
    pending_confirmation_count: 1,
    ...overrides,
  };
}

export function makePendingConfirmations(
  overrides: Partial<PendingConfirmationResponse> = {}
): PendingConfirmationResponse {
  return {
    count: 1,
    results: [
      {
        plan_id: "plan-1",
        plan_period_start: "2026-07-01",
        plan_period_end: "2027-06-30",
        ...makeBlock(),
      },
    ],
    ...overrides,
  };
}

export function makeApprovalItem(
  overrides: Partial<PlanApprovalListItem> = {}
): PlanApprovalListItem {
  return {
    id: "plan-1",
    period_start: "2026-07-01",
    period_end: "2027-06-30",
    financial_year_label: "FY 2026-27",
    status: "submitted",
    status_label: "Submitted",
    submitted_at: "2026-09-21T09:12:00Z",
    decided_at: null,
    submission_cycle: 1,
    employee_name: "Mphatso Kachale",
    department: "Registry",
    stage_role_label: "Supervisor",
    my_decision: null,
    blocks: [
      {
        leave_type_code: "ANNUAL",
        start_date: "2026-10-08",
        end_date: "2026-10-09",
        working_days: 2,
      },
    ],
    ...overrides,
  };
}

export function makeApprovalList(
  overrides: Partial<PlanApprovalListResponse> = {}
): PlanApprovalListResponse {
  return {
    tab: "pending",
    count: 1,
    next: null,
    previous: null,
    results: [makeApprovalItem()],
    ...overrides,
  };
}