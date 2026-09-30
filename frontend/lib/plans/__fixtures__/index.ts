import type {
  PlanApprovalDetail,
  PlanApprovalListItem,
  PlanApprovalListResponse,
  PlanBlock,
  PlanCapabilities,
  PlanDecision,
  PlanDetail,
  PlanListItem,
  PlanListResponse,
  PlanStage,
  PendingConfirmation,
} from "@/lib/plans/types";

const STAGES: PlanStage[] = [
  {
    id: "stage-1",
    stage_order: 1,
    role: "supervisor",
    role_label: "Supervisor",
    role_ref_id: 1,
    section_ref_id: 11,
    history_scope: "team",
    // Claimed: somebody acted first, so the stage names one person.
    assigned_approver_id: 101,
    approver_name: "Mphatso Kachale",
    eligible_approver_ids: [101, 102],
    eligible_approvers: [
      { id: 101, name: "Mphatso Kachale" },
      { id: 102, name: "Jane Phiri" },
    ],
    is_claimed: true,
    status: "approved",
    status_label: "Approved",
    is_final: false,
    decision_version: 2,
  },
  {
    id: "stage-2",
    stage_order: 2,
    role: "hod",
    role_label: "HOD",
    role_ref_id: 2,
    section_ref_id: 12,
    history_scope: "team",
    // Unclaimed: two candidates may still act, which is the normal case.
    assigned_approver_id: null,
    approver_name: "",
    eligible_approver_ids: [102, 103],
    eligible_approvers: [
      { id: 102, name: "Jane Phiri" },
      { id: 103, name: "Peter Banda" },
    ],
    is_claimed: false,
    status: "pending",
    status_label: "Pending action",
    is_final: false,
    decision_version: 1,
  },
  {
    id: "stage-3",
    stage_order: 3,
    role: "dvc",
    role_label: "DVC",
    role_ref_id: 3,
    section_ref_id: null,
    history_scope: "institution",
    assigned_approver_id: null,
    approver_name: "",
    eligible_approver_ids: [104],
    eligible_approvers: [{ id: 104, name: "Grace Nkhata" }],
    is_claimed: false,
    status: "waiting",
    status_label: "Waiting",
    is_final: true,
    decision_version: 0,
  },
];

const DECISIONS: PlanDecision[] = [
  {
    id: "decision-1",
    stage_order: 1,
    role_label: "Supervisor",
    approver_name: "Mphatso Kachale",
    action: "approve",
    comment: "Fine by me.",
    decided_at: "2026-09-22T10:00:00Z",
  },
];

const RESERVED_BLOCK: PlanBlock = {
  id: "block-1",
  leave_type_id: 1,
  leave_type_code: "annual",
  leave_type_name: "Annual leave",
  start_date: "2026-10-12",
  end_date: "2026-10-13",
  working_days: 2,
  status: "reserved",
  status_label: "Reserved",
  confirmation_window_start: "2026-09-27",
  confirmed_at: null,
  released_at: null,
  application_id: null,
  can_confirm: true,
  can_release: true,
};

const BASE_DETAIL: PlanDetail = {
  meta: {
    id: "plan-1",
    period_start: "2026-10-01",
    period_end: "2026-12-18",
    financial_year_label: "2026/2027",
    status: "submitted",
    status_label: "Submitted",
    submitted_at: "2026-09-21T09:12:00Z",
    decided_at: null,
    submission_cycle: 1,
  },
  employee: {
    id: 7,
    name: "Chikondi Mbewe",
    department: "Administration",
    team_id: 3,
    team_name: "Administration Team",
  },
  blocks: [RESERVED_BLOCK],
  stages: STAGES,
  decisions: DECISIONS,
  access: "owner",
  can_decide: false,
  can_submit: false,
  my_decision: null,
  peer_conflicts: [],
  pending_confirmations: [RESERVED_BLOCK],
};

export function makeStage(
  overrides: Partial<PlanStage> = {}
): PlanStage {
  return structuredClone({ ...STAGES[1], ...overrides });
}

export function makeBlock(overrides: Partial<PlanBlock> = {}): PlanBlock {
  return structuredClone({ ...RESERVED_BLOCK, ...overrides });
}

/** A block the owner already confirmed, so its application exists. */
export function makeConfirmedBlock(
  overrides: Partial<PlanBlock> = {}
): PlanBlock {
  return makeBlock({
    id: "block-2",
    start_date: "2026-11-09",
    end_date: "2026-11-11",
    working_days: 3,
    status: "confirmed",
    status_label: "Confirmed",
    confirmation_window_start: null,
    confirmed_at: "2026-09-25T08:30:00Z",
    application_id: "app-1",
    can_confirm: false,
    ...overrides,
  });
}

/** A reserved block still inside its confirmation window, with its plan period. */
export function makePendingConfirmation(
  overrides: Partial<PendingConfirmation> = {}
): PendingConfirmation {
  return {
    ...makeBlock(),
    plan_id: BASE_DETAIL.meta.id,
    plan_period_start: BASE_DETAIL.meta.period_start as string,
    plan_period_end: BASE_DETAIL.meta.period_end as string,
    ...overrides,
  };
}

export function makeDetail(overrides: Partial<PlanDetail> = {}): PlanDetail {
  return structuredClone({ ...BASE_DETAIL, ...overrides });
}

export function makeDraftDetail(
  overrides: Partial<PlanDetail> = {}
): PlanDetail {
  return makeDetail({
    meta: {
      ...BASE_DETAIL.meta,
      status: "draft",
      status_label: "Draft",
      submitted_at: null,
    },
    stages: [],
    decisions: [],
    blocks: [makeBlock({ status: "proposed", status_label: "Proposed" })],
    can_submit: true,
    ...overrides,
  });
}

export function makeListItem(
  overrides: Partial<PlanListItem> = {}
): PlanListItem {
  return {
    ...BASE_DETAIL.meta,
    employee_id: 7,
    employee_name: "Chikondi Mbewe",
    block_count: 1,
    working_days: 2,
    blocks: [makeBlock()],
    ...overrides,
  };
}

export function makeListResponse(
  rows: PlanListItem[],
  overrides: Partial<PlanListResponse> = {}
): PlanListResponse {
  return { scope: "mine", count: rows.length, results: rows, ...overrides };
}

export function makeApprovalListItem(
  overrides: Partial<PlanApprovalListItem> = {}
): PlanApprovalListItem {
  return {
    ...BASE_DETAIL.meta,
    employee_name: "Chikondi Mbewe",
    department: "Administration",
    team_name: "Administration Team",
    stage_role_label: "HOD",
    stage_candidate_count: 2,
    my_decision: null,
    blocks: [
      {
        leave_type_code: "annual",
        start_date: "2026-10-12",
        end_date: "2026-10-13",
        working_days: 2,
      },
    ],
    ...overrides,
  };
}

export function makeApprovalListResponse(
  rows: PlanApprovalListItem[],
  overrides: Partial<PlanApprovalListResponse> = {}
): PlanApprovalListResponse {
  return {
    tab: "pending",
    count: rows.length,
    next: null,
    previous: null,
    results: rows,
    ...overrides,
  };
}

export function makeApprovalDetail(
  overrides: Partial<PlanApprovalDetail> = {}
): PlanApprovalDetail {
  return {
    meta: BASE_DETAIL.meta,
    employee: BASE_DETAIL.employee,
    blocks: BASE_DETAIL.blocks,
    stages: STAGES,
    decisions: DECISIONS,
    can_decide: true,
    responsible_approver_id: null,
    decision_version: 1,
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
