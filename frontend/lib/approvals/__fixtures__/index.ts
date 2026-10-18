import type {
  ApprovalCapabilities,
  ApprovalListItem,
  ApprovalListResponse,
  ApprovalReview,
  DecisionBriefing,
  DecisionPayload,
} from "@/lib/approvals/types";

const STAGES = [
  {
    order: 1,
    role: "supervisor",
    role_label: "Supervisor",
    status: "approved",
    decision_version: 2,
    assigned_approver: "Mphatso Kachale",
    assigned_at: "2026-09-21T09:12:00Z",
    decided_at: "2026-09-22T10:00:00Z",
    comment: "Looks good.",
    skip_reason: null,
  },
  {
    order: 2,
    role: "hod",
    role_label: "HOD",
    status: "pending",
    decision_version: 1,
    assigned_approver: "Jane Phiri",
    assigned_at: "2026-09-22T10:00:00Z",
    decided_at: null,
    comment: null,
    skip_reason: null,
  },
  {
    order: 3,
    role: "registrar",
    role_label: "Registrar",
    status: "waiting",
    decision_version: 0,
    assigned_approver: "Peter Banda",
    assigned_at: null,
    decided_at: null,
    comment: null,
    skip_reason: null,
  },
  {
    order: 4,
    role: "dvc",
    role_label: "DVC",
    status: "waiting",
    decision_version: 0,
    assigned_approver: "Grace Nkhata",
    assigned_at: null,
    decided_at: null,
    comment: null,
    skip_reason: null,
  },
] as const;

const BASE_REVIEW: ApprovalReview = {
  application: {
    id: "app-1",
    reference: "LV-2026-000123",
    submission_cycle: 1,
    start_date: "2026-09-28",
    end_date: "2026-10-02",
    working_days: 5,
    calendar_days: 5,
    submitted_at: "2026-09-21T09:12:00Z",
    reason: "Family visit",
    financial_year_label: "2026/2027",
  },
  employee_info: {
    name: "Chikondi Mbewe",
    designation: "Lecturer",
    team: "Computer Science Team",
    faculty: "Faculty of Agriculture",
    staff_id: null,
    grade: "C",
    category: "academic",
    appointment_date: "2021-05-01",
  },
  rules: {
    leave_type: { id: 1, code: "Annual", name: "Annual Leave" },
    holidays: ["2026-09-30"],
    working_days: 5,
    calendar_days: 5,
    min_notice: { value: 2, unit: "WEEK" },
    requires_document: false,
    available_balance: 14,
    balance_after_if_approved: 9,
  },
  balance: {
    entitlement: "24",
    used: "10",
    available: "14",
    financial_year_label: "2026/2027",
  },
  documents: [
    {
      id: "doc-1",
      name: "Evidence letter.pdf",
      size: 2048,
      content_type: "application/pdf",
      uploaded_at: "2026-09-20T10:00:00Z",
    },
  ],
  history: {
    leave_history: {
      available: true,
      scope: "all",
      entries: [
        {
          id: "h1",
          reference: "LV-2026-000045",
          leave_type: { id: 1, code: "Annual", name: "Annual Leave" },
          start_date: "2026-03-01",
          end_date: "2026-03-05",
          working_days: 4,
          status: "approved",
          submitted_at: "2026-02-20T08:00:00Z",
        },
      ],
    },
    audit_history: [
      {
        id: 1,
        action: "submitted",
        occurred_at: "2026-09-21T09:12:00Z",
        actor: "Chikondi Mbewe",
        reason: null,
      },
    ],
  },
  workflow: {
    state: "pending",
    current_stage: {
      order: 2,
      role: "hod",
      role_label: "HOD",
      is_final: false,
      next_role_label: "Registrar",
    },
    stages: [...STAGES],
    current_decision: {
      action: "approve",
      role_label: "Supervisor",
      approver_name: "Mphatso Kachale",
      comment: "Looks good.",
      decided_at: "2026-09-22T10:00:00Z",
    },
  },
  my_decision: null,
  can_decide: true,
  decision_restriction: null,
};

export function makeReview(overrides: Partial<ApprovalReview> = {}): ApprovalReview {
  return structuredClone({ ...BASE_REVIEW, ...overrides });
}

export function makeDecidedReview(): ApprovalReview {
  return makeReview({
    can_decide: false,
    decision_restriction: "already_decided",
    my_decision: {
      action: "approve",
      role_label: "HOD",
      comment: "Seen",
      decided_at: "2026-09-23T08:00:00Z",
    },
    workflow: {
      ...BASE_REVIEW.workflow,
      current_stage: { order: 3, role: "registrar", role_label: "Registrar", is_final: false, next_role_label: "DVC" },
    },
  });
}

/**
 * The applicant sat on the HOD section alongside a colleague, so the chain did
 * not stop there: the applicant is removed from the section's eligibility at
 * submission and the colleague decided it. Nothing is skipped -- a section whose
 * only approver is the applicant is skipped instead (Unit 30), which
 * `makeSkippedReview` shows.
 */
export function makeApplicantExcludedReview(): ApprovalReview {
  return makeReview({
    workflow: {
      ...BASE_REVIEW.workflow,
      current_stage: {
        order: 3,
        role: "registrar",
        role_label: "Registrar",
        is_final: false,
        next_role_label: "DVC",
      },
      stages: [
        STAGES[0],
        { ...STAGES[1], status: "approved", decided_at: "2026-09-22T11:00:00Z" },
        { ...STAGES[2], status: "pending" },
        STAGES[3],
      ],
    },
  });
}

/**
 * The applicant was the HOD, so that stage was skipped and the chain opened at
 * the Registrar above it (Unit 30). The skipped stage stays in the history with
 * the reason attached -- a reader has to be able to tell a deliberate skip from
 * a stage that was quietly dropped.
 */
export function makeSkippedReview(): ApprovalReview {
  return makeReview({
    workflow: {
      ...BASE_REVIEW.workflow,
      current_stage: {
        order: 3,
        role: "registrar",
        role_label: "Registrar",
        is_final: false,
        next_role_label: "DVC",
      },
      stages: [
        STAGES[0],
        {
          ...STAGES[1],
          status: "skipped",
          assigned_approver: "",
          assigned_at: null,
          decided_at: null,
          comment: null,
          skip_reason: "Applicant cannot approve their own application.",
        },
        { ...STAGES[2], status: "pending" },
        STAGES[3],
      ],
    },
  });
}

export function makeListItem(
  overrides: Partial<ApprovalListItem> = {}
): ApprovalListItem {
  return {
    id: "app-1",
    reference: "LV-2026-000123",
    employee_name: "Chikondi Mbewe",
    team: "Computer Science Team",
    leave_type: { id: 1, code: "Annual", name: "Annual Leave" },
    start_date: "2026-09-28",
    end_date: "2026-10-02",
    working_days: 5,
    submitted_at: "2026-09-21T09:12:00Z",
    status: "pending",
    stage_version: 1,
    my_decision: null,
    ...overrides,
  };
}

export function makeListResponse(
  rows: ApprovalListItem[],
  overrides: Partial<ApprovalListResponse> = {}
): ApprovalListResponse {
  return {
    tab: "pending",
    count: rows.length,
    next: null,
    previous: null,
    results: rows,
    ...overrides,
  };
}

export function makeCapabilities(
  overrides: Partial<ApprovalCapabilities> = {}
): ApprovalCapabilities {
  return { is_approver: true, pending_count: 3, ...overrides };
}

export function makeBriefing(overrides: Partial<DecisionBriefing> = {}): DecisionBriefing {
  return {
    status: "approved",
    reference: "LV-2026-000123",
    current_stage: null,
    my_decision: {
      action: "approve",
      role_label: "DVC",
      comment: null,
      decided_at: "2026-09-24T08:00:00Z",
    },
    ...overrides,
  };
}

export function makeDecisionPayload(overrides: Partial<DecisionPayload> = {}): DecisionPayload {
  return { action: "approve", comment: "", stage_version: 1, ...overrides };
}