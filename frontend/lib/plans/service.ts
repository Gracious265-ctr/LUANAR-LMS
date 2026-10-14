import type {
  AdminListResponse,
  BlockStateResponse,
  PendingConfirmationsResponse,
  PlanApprovalDetail,
  PlanApprovalListResponse,
  PlanCreateInput,
  PlanDecisionInput,
  PlanDetail,
  PlanListResponse,
  PlanScope,
  PlanSettings,
  PlanTab,
  PlanValidationIssue,
  PeerConflict,
} from "./types";

const FETCH_ERROR =
  "Could not reach the server. Check your connection and try again.";

export type PlanListResult =
  | { ok: true; data: PlanListResponse }
  | { ok: false; kind: "forbidden" | "error"; message: string };

export type PlanDetailResult =
  | { ok: true; data: PlanDetail }
  | { ok: false; kind: "not_found" | "forbidden" | "error"; message: string };

export type PlanApprovalListResult =
  | { ok: true; data: PlanApprovalListResponse }
  | { ok: false; kind: "not_found" | "error"; message: string };

export type PlanApprovalDetailResult =
  | { ok: true; data: PlanApprovalDetail }
  | { ok: false; kind: "not_found" | "error"; message: string };

/**
 * A submission the backend refused.
 *
 * `errors` are block-level issues that must be fixed; `warnings` are the
 * peer overlaps the owner may submit through. Both are returned rather than
 * thrown away, because a submission can be blocked *and* carry a warning the
 * owner has to acknowledge.
 */
export type SubmitPlanResult =
  | { ok: true; data: PlanDetail }
  | {
      ok: false;
      kind: "conflict" | "not_found" | "validation" | "error";
      message: string;
      errors: PlanValidationIssue[];
      warnings: PeerConflict[];
    };

export type PlanDecisionResult =
  | { ok: true; data: PlanDetail }
  | {
      ok: false;
      kind: "validation" | "forbidden" | "conflict" | "not_found" | "error";
      message: string;
      reason?: string | null;
      fields?: Record<string, string>;
    };

export type BlockStateResult =
  | { ok: true; data: BlockStateResponse }
  | { ok: false; kind: "conflict" | "not_found" | "error"; message: string };

export type PendingConfirmationsResult =
  | { ok: true; data: PendingConfirmationsResponse }
  | { ok: false; kind: "error"; message: string };

export type PlanSettingsResult =
  | { ok: true; data: PlanSettings }
  | { ok: false; kind: "error"; message: string };

export type AdminListResult =
  | { ok: true; data: AdminListResponse }
  | { ok: false; kind: "error"; message: string };

async function readJson(res: Response): Promise<Record<string, unknown>> {
  return res.json().catch(() => ({}));
}

function messageFrom(
  data: Record<string, unknown>,
  fallback: string
): string {
  const error = data.error ?? data.detail;
  return typeof error === "string" && error ? error : fallback;
}

function issueList(value: unknown): PlanValidationIssue[] {
  if (!Array.isArray(value)) return [];
  return value.filter(
    (item): item is PlanValidationIssue =>
      item !== null && typeof item === "object"
  );
}

function conflictList(value: unknown): PeerConflict[] {
  return Array.isArray(value) ? (value as PeerConflict[]) : [];
}

/** Field errors keyed by field name, from either `{field: msg}` or `{errors}`. */
function extractFieldErrors(
  data: Record<string, unknown>
): Record<string, string> {
  const raw = (data.errors as Record<string, unknown>) ?? data;
  const fields: Record<string, string> = {};
  if (raw === null || typeof raw !== "object" || Array.isArray(raw)) {
    return fields;
  }
  for (const key of Object.keys(raw)) {
    const value = raw[key];
    if (Array.isArray(value)) {
      fields[key] = String(value[0]);
    } else if (typeof value === "string") {
      fields[key] = value;
    }
  }
  return fields;
}

export async function fetchPlans(
  scope: PlanScope
): Promise<PlanListResult> {
  try {
    const res = await fetch(
      `/api/plans/?scope=${encodeURIComponent(scope)}`,
      { credentials: "include" }
    );
    const data = await readJson(res);
    if (res.status === 403) {
      return {
        ok: false,
        kind: "forbidden",
        message: messageFrom(
          data,
          "You do not have access to this view."
        ),
      };
    }
    if (!res.ok) {
      return { ok: false, kind: "error", message: messageFrom(data, "Failed to load plans.") };
    }
    return { ok: true, data: data as unknown as PlanListResponse };
  } catch {
    return { ok: false, kind: "error", message: FETCH_ERROR };
  }
}

export async function fetchPlan(id: string): Promise<PlanDetailResult> {
  try {
    const res = await fetch(`/api/plans/${encodeURIComponent(id)}/`, {
      credentials: "include",
    });
    const data = await readJson(res);
    if (res.status === 404) {
      return { ok: false, kind: "not_found", message: "Plan not found." };
    }
    if (res.status === 403) {
      return {
        ok: false,
        kind: "forbidden",
        message: messageFrom(data, "You cannot view this plan."),
      };
    }
    if (!res.ok) {
      return {
        ok: false,
        kind: "error",
        message: messageFrom(data, "Failed to load the plan."),
      };
    }
    return { ok: true, data: data as unknown as PlanDetail };
  } catch {
    return { ok: false, kind: "error", message: FETCH_ERROR };
  }
}

export async function createPlan(
  input: PlanCreateInput
): Promise<SubmitPlanResult> {
  try {
    const res = await fetch("/api/plans/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
      credentials: "include",
    });
    const data = await readJson(res);
    if (!res.ok) {
      return {
        ok: false,
        kind: "error",
        message: messageFrom(data, "The plan could not be saved."),
        errors: [],
        warnings: [],
      };
    }
    return { ok: true, data: data as unknown as PlanDetail };
  } catch {
    return {
      ok: false,
      kind: "error",
      message: FETCH_ERROR,
      errors: [],
      warnings: [],
    };
  }
}

export async function submitPlan(id: string): Promise<SubmitPlanResult> {
  try {
    const res = await fetch(`/api/plans/${encodeURIComponent(id)}/submit/`, {
      method: "POST",
      credentials: "include",
    });
    const data = await readJson(res);
    if (res.status === 404) {
      return {
        ok: false,
        kind: "not_found",
        message: "Plan not found.",
        errors: [],
        warnings: [],
      };
    }
    if (res.status === 409) {
      return {
        ok: false,
        kind: "conflict",
        message: messageFrom(data, "This plan has already been submitted."),
        errors: [],
        warnings: [],
      };
    }
    if (res.status === 422) {
      return {
        ok: false,
        kind: "validation",
        message: "This plan cannot be submitted yet.",
        errors: issueList(data.errors),
        warnings: conflictList(data.warnings),
      };
    }
    if (!res.ok) {
      return {
        ok: false,
        kind: "error",
        message: messageFrom(data, "The plan could not be submitted."),
        errors: [],
        warnings: [],
      };
    }
    return { ok: true, data: data as unknown as PlanDetail };
  } catch {
    return {
      ok: false,
      kind: "error",
      message: FETCH_ERROR,
      errors: [],
      warnings: [],
    };
  }
}

async function postBlockAction(
  id: string,
  blockId: string,
  action: "confirm" | "release"
): Promise<BlockStateResult> {
  try {
    const res = await fetch(
      `/api/plans/${encodeURIComponent(id)}/blocks/${encodeURIComponent(blockId)}/${action}/`,
      { method: "POST", credentials: "include" }
    );
    const data = await readJson(res);
    if (res.status === 404) {
      return {
        ok: false,
        kind: "not_found",
        message: "Plan or block not found.",
      };
    }
    if (res.status === 409) {
      return {
        ok: false,
        kind: "conflict",
        message: messageFrom(
          data,
          "This block can no longer be changed."
        ),
      };
    }
    if (!res.ok) {
      return {
        ok: false,
        kind: "error",
        message: messageFrom(
          data,
          action === "confirm"
            ? "The block could not be confirmed."
            : "The block could not be released."
        ),
      };
    }
    return { ok: true, data: data as unknown as BlockStateResponse };
  } catch {
    return { ok: false, kind: "error", message: FETCH_ERROR };
  }
}

export function confirmBlock(
  planId: string,
  blockId: string
): Promise<BlockStateResult> {
  return postBlockAction(planId, blockId, "confirm");
}

export function releaseBlock(
  planId: string,
  blockId: string
): Promise<BlockStateResult> {
  return postBlockAction(planId, blockId, "release");
}

export async function fetchPendingConfirmations(): Promise<PendingConfirmationsResult> {
  try {
    const res = await fetch("/api/plans/pending-confirmations/", {
      credentials: "include",
    });
    const data = await readJson(res);
    if (!res.ok) {
      return {
        ok: false,
        kind: "error",
        message: messageFrom(
          data,
          "Failed to load blocks awaiting confirmation."
        ),
      };
    }
    return {
      ok: true,
      data: data as unknown as PendingConfirmationsResponse,
    };
  } catch {
    return { ok: false, kind: "error", message: FETCH_ERROR };
  }
}

export async function fetchPlanApprovals(
  tab: PlanTab,
  page: number
): Promise<PlanApprovalListResult> {
  try {
    const res = await fetch(
      `/api/plans/approvals/?tab=${encodeURIComponent(tab)}&page=${page}`,
      { credentials: "include" }
    );
    const data = await readJson(res);
    if (res.status === 404) {
      return {
        ok: false,
        kind: "not_found",
        message: "You cannot review plans.",
      };
    }
    if (!res.ok) {
      return {
        ok: false,
        kind: "error",
        message: messageFrom(data, "Failed to load plans for approval."),
      };
    }
    return { ok: true, data: data as unknown as PlanApprovalListResponse };
  } catch {
    return { ok: false, kind: "error", message: FETCH_ERROR };
  }
}

export async function fetchPlanApproval(
  id: string
): Promise<PlanApprovalDetailResult> {
  try {
    const res = await fetch(
      `/api/plans/approvals/${encodeURIComponent(id)}/`,
      { credentials: "include" }
    );
    const data = await readJson(res);
    if (res.status === 404) {
      return {
        ok: false,
        kind: "not_found",
        message: "You cannot review this plan.",
      };
    }
    if (!res.ok) {
      return {
        ok: false,
        kind: "error",
        message: messageFrom(data, "Failed to load the plan."),
      };
    }
    return { ok: true, data: data as unknown as PlanApprovalDetail };
  } catch {
    return { ok: false, kind: "error", message: FETCH_ERROR };
  }
}

export async function postPlanDecision(
  id: string,
  payload: PlanDecisionInput
): Promise<PlanDecisionResult> {
  try {
    const res = await fetch(
      `/api/plans/approvals/${encodeURIComponent(id)}/decision/`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        credentials: "include",
      }
    );
    const data = await readJson(res);
    if (res.status === 409) {
      return {
        ok: false,
        kind: "conflict",
        message: messageFrom(
          data,
          "This plan has already been decided. Refresh to see the latest state."
        ),
        reason: (data.reason as string) || "stage_changed",
      };
    }
    if (res.status === 403) {
      return {
        ok: false,
        kind: "forbidden",
        message: messageFrom(data, "You cannot decide on this plan."),
        reason: (data.reason as string) || null,
      };
    }
    if (res.status === 404) {
      return { ok: false, kind: "not_found", message: "Plan not found." };
    }
    if (res.status === 400) {
      return {
        ok: false,
        kind: "validation",
        message: "The decision could not be recorded.",
        fields: extractFieldErrors(data),
      };
    }
    if (!res.ok) {
      return {
        ok: false,
        kind: "error",
        message: messageFrom(data, "The decision was not recorded."),
      };
    }
    return { ok: true, data: data as unknown as PlanDetail };
  } catch {
    return { ok: false, kind: "error", message: FETCH_ERROR };
  }
}

export async function fetchPlanSettings(): Promise<PlanSettingsResult> {
  try {
    const res = await fetch("/api/plans/settings/", { credentials: "include" });
    const data = await readJson(res);
    if (!res.ok) {
      return {
        ok: false,
        kind: "error",
        message: messageFrom(data, "Failed to load plan settings."),
      };
    }
    return { ok: true, data: data as unknown as PlanSettings };
  } catch {
    return { ok: false, kind: "error", message: FETCH_ERROR };
  }
}

export async function savePlanSettings(
  input: PlanSettings
): Promise<PlanSettingsResult> {
  try {
    const res = await fetch("/api/plans/settings/", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
      credentials: "include",
    });
    const data = await readJson(res);
    if (!res.ok) {
      return {
        ok: false,
        kind: "error",
        message: messageFrom(data, "Failed to save plan settings."),
      };
    }
    return { ok: true, data: data as unknown as PlanSettings };
  } catch {
    return { ok: false, kind: "error", message: FETCH_ERROR };
  }
}

export async function fetchAdminPlans(
  filters: { status?: string; blockStatus?: string; page: number }
): Promise<AdminListResult> {
  try {
    const params = new URLSearchParams({ page: String(filters.page) });
    if (filters.status) params.set("status", filters.status);
    if (filters.blockStatus) {
      params.set("block_status", filters.blockStatus);
    }
    const res = await fetch(`/api/plans/admin/?${params.toString()}`, {
      credentials: "include",
    });
    const data = await readJson(res);
    if (!res.ok) {
      return {
        ok: false,
        kind: "error",
        message: messageFrom(data, "Failed to load plans."),
      };
    }
    return { ok: true, data: data as unknown as AdminListResponse };
  } catch {
    return { ok: false, kind: "error", message: FETCH_ERROR };
  }
}
