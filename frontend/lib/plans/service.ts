import type {
  PlanApprovalDetail,
  PlanApprovalListResponse,
  PlanCapabilities,
  PlanCreateInput,
  PlanDecisionAction,
  PlanDecisionPayload,
  PlanDetail,
  PlanListResponse,
  PlanScope,
  PlanSettings,
  PlanSubmitError,
  PendingConfirmationResponse,
} from "./types";

const FETCH_ERROR =
  "Could not reach the server. Check your connection and try again.";

async function readJson(res: Response): Promise<Record<string, unknown>> {
  return res.json().catch(() => ({}));
}

export type PlansListResult =
  | { ok: true; data: PlanListResponse }
  | { ok: false; kind: "forbidden" | "error"; message: string };

export type PlanDetailResult =
  | { ok: true; data: PlanDetail }
  | { ok: false; kind: "not_found" | "forbidden" | "error"; message: string };

export type PlanCreateResult =
  | { ok: true; data: PlanDetail }
  | { ok: false; kind: "validation" | "error"; message: string };

export type PlanSubmitResult =
  | { ok: true; data: PlanDetail }
  | {
      ok: false;
      kind: "validation" | "conflict" | "not_found" | "error";
      message: string;
      errors?: PlanSubmitError[];
      warnings?: string[];
    };

export type PlanBlockResult =
  | { ok: true; data: { id: string; status: string } }
  | { ok: false; kind: "conflict" | "not_found" | "error"; message: string };

export type PlanDecisionResult =
  | { ok: true; data: PlanDetail }
  | {
      ok: false;
      kind:
        | "validation"
        | "forbidden"
        | "conflict"
        | "not_found"
        | "error";
      message: string;
      reason?: string | null;
      fields?: Record<string, string>;
    };

export type PlanAdminListResult =
  | { ok: true; data: PlanListResponse & { next: string | null; previous: string | null } }
  | { ok: false; kind: "error"; message: string };

export type PlanSettingsResult =
  | { ok: true; data: PlanSettings }
  | { ok: false; kind: "forbidden" | "error"; message: string };

export type PlanCapabilitiesResult = PlanCapabilities;

export type PendingConfirmationsResult =
  | { ok: true; data: PendingConfirmationResponse }
  | { ok: false; kind: "error"; message: string };

function scopeQuery(scope: PlanScope): string {
  const params = new URLSearchParams({ scope });
  return `?${params.toString()}`;
}

export async function fetchMyPlans(
  scope: PlanScope
): Promise<PlansListResult> {
  try {
    const res = await fetch(
      `/api/plans/${scope === "mine" ? "" : scopeQuery(scope)}`,
      { credentials: "include" }
    );
    const data = await readJson(res);
    if (res.status === 403) {
      return {
        ok: false,
        kind: "forbidden",
        message: (data.error as string) || "You cannot view these plans.",
      };
    }
    if (!res.ok) {
      return {
        ok: false,
        kind: "error",
        message: (data.error as string) || (data.detail as string) || "Failed to load plans.",
      };
    }
    return { ok: true, data: data as unknown as PlanListResponse };
  } catch {
    return { ok: false, kind: "error", message: FETCH_ERROR };
  }
}

export async function fetchPlanDetail(id: string): Promise<PlanDetailResult> {
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
        message: (data.error as string) || "You cannot view this plan.",
      };
    }
    if (!res.ok) {
      return {
        ok: false,
        kind: "error",
        message: (data.error as string) || (data.detail as string) || "Failed to load the plan.",
      };
    }
    return { ok: true, data: data as unknown as PlanDetail };
  } catch {
    return { ok: false, kind: "error", message: FETCH_ERROR };
  }
}

export async function createPlan(input: PlanCreateInput): Promise<PlanCreateResult> {
  try {
    const res = await fetch("/api/plans/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
      credentials: "include",
    });
    const data = await readJson(res);
    if (res.status === 400) {
      return {
        ok: false,
        kind: "validation",
        message: (data.error as string) || "The plan could not be created.",
      };
    }
    if (!res.ok) {
      return {
        ok: false,
        kind: "error",
        message: (data.error as string) || (data.detail as string) || "The plan could not be created.",
      };
    }
    return { ok: true, data: data as unknown as PlanDetail };
  } catch {
    return { ok: false, kind: "error", message: FETCH_ERROR };
  }
}

export async function submitPlan(id: string): Promise<PlanSubmitResult> {
  try {
    const res = await fetch(
      `/api/plans/${encodeURIComponent(id)}/submit/`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
        credentials: "include",
      }
    );
    const data = await readJson(res);
    if (res.status === 422) {
      const rawErrors = data.errors as Record<string, unknown>[] | undefined;
      const rawWarnings = data.warnings as string[] | undefined;
      return {
        ok: false,
        kind: "validation",
        message: "The plan could not be submitted.",
        errors: Array.isArray(rawErrors)
          ? (rawErrors as unknown as PlanSubmitError[])
          : undefined,
        warnings: Array.isArray(rawWarnings) ? rawWarnings : undefined,
      };
    }
    if (res.status === 409) {
      return {
        ok: false,
        kind: "conflict",
        message: (data.error as string) || "Only a draft plan can be submitted.",
      };
    }
    if (res.status === 404) {
      return { ok: false, kind: "not_found", message: "Plan not found." };
    }
    if (!res.ok) {
      return {
        ok: false,
        kind: "error",
        message: (data.error as string) || (data.detail as string) || "The plan could not be submitted.",
      };
    }
    return { ok: true, data: data as unknown as PlanDetail };
  } catch {
    return { ok: false, kind: "error", message: FETCH_ERROR };
  }
}

async function planBlockAction(
  path: string,
  verb: string
): Promise<PlanBlockResult> {
  try {
    const res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
      credentials: "include",
    });
    const data = await readJson(res);
    if (res.status === 409) {
      return {
        ok: false,
        kind: "conflict",
        message: (data.error as string) || "This block is not in a state that allows this action.",
      };
    }
    if (res.status === 404) {
      return { ok: false, kind: "not_found", message: "Plan or block not found." };
    }
    if (!res.ok) {
      return {
        ok: false,
        kind: "error",
        message: (data.error as string) || (data.detail as string) || `The block could not be ${verb}d.`,
      };
    }
    return { ok: true, data: data as unknown as { id: string; status: string } };
  } catch {
    return { ok: false, kind: "error", message: FETCH_ERROR };
  }
}

export function confirmBlock(planId: string, blockId: string): Promise<PlanBlockResult> {
  return planBlockAction(
    `/api/plans/${encodeURIComponent(planId)}/blocks/${encodeURIComponent(blockId)}/confirm/`,
    "confirm"
  );
}

export function releaseBlock(planId: string, blockId: string): Promise<PlanBlockResult> {
  return planBlockAction(
    `/api/plans/${encodeURIComponent(planId)}/blocks/${encodeURIComponent(blockId)}/release/`,
    "release"
  );
}

export async function fetchCapabilities(): Promise<PlanCapabilitiesResult> {
  try {
    const res = await fetch("/api/plans/capabilities/", {
      credentials: "include",
    });
    const data = await readJson(res);
    return {
      is_approver: Boolean(data.is_approver),
      approver_pending_count: Number(data.approver_pending_count) || 0,
      pending_confirmation_count: Number(data.pending_confirmation_count) || 0,
    };
  } catch {
    return { is_approver: false, approver_pending_count: 0, pending_confirmation_count: 0 };
  }
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
        message: (data.error as string) || (data.detail as string) || "Failed to load confirmations.",
      };
    }
    return { ok: true, data: data as unknown as PendingConfirmationResponse };
  } catch {
    return { ok: false, kind: "error", message: FETCH_ERROR };
  }
}

function approvalsQuery(tab: "pending" | "decided", page: number): string {
  const params = new URLSearchParams({ tab, page: String(page) });
  return `?${params.toString()}`;
}

export type PlanApprovalListResult =
  | { ok: true; data: PlanApprovalListResponse }
  | { ok: false; kind: "error"; message: string };

export async function fetchApprovalsList(
  tab: "pending" | "decided",
  page: number
): Promise<PlanApprovalListResult> {
  try {
    const res = await fetch(
      `/api/plans/approvals/${approvalsQuery(tab, page)}`,
      { credentials: "include" }
    );
    const data = await readJson(res);
    if (!res.ok) {
      return {
        ok: false,
        kind: "error",
        message: (data.error as string) || (data.detail as string) || "Failed to load plan approvals.",
      };
    }
    return { ok: true, data: data as unknown as PlanApprovalListResponse };
  } catch {
    return { ok: false, kind: "error", message: FETCH_ERROR };
  }
}

export type PlanApprovalDetailResult =
  | { ok: true; data: PlanApprovalDetail }
  | { ok: false; kind: "not_found" | "error"; message: string };

export async function fetchApprovalDetail(id: string): Promise<PlanApprovalDetailResult> {
  try {
    const res = await fetch(`/api/plans/approvals/${encodeURIComponent(id)}/`, {
      credentials: "include",
    });
    const data = await readJson(res);
    if (res.status === 404) {
      return { ok: false, kind: "not_found", message: "Plan not found." };
    }
    if (!res.ok) {
      return {
        ok: false,
        kind: "error",
        message: (data.error as string) || (data.detail as string) || "Failed to load the plan.",
      };
    }
    return { ok: true, data: data as unknown as PlanApprovalDetail };
  } catch {
    return { ok: false, kind: "error", message: FETCH_ERROR };
  }
}

export async function postPlanDecision(
  id: string,
  payload: PlanDecisionPayload
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
        message:
          (data.error as string) || "This plan has already been decided. Refresh to see the latest state.",
        reason: (data.reason as string) || "stage_changed",
      };
    }
    if (res.status === 403) {
      return {
        ok: false,
        kind: "forbidden",
        message: (data.error as string) || "You are not allowed to decide on this plan.",
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
        message: "The decision could not be submitted.",
        fields: extractFieldErrors(data),
      };
    }
    if (!res.ok) {
      return {
        ok: false,
        kind: "error",
        message: (data.error as string) || (data.detail as string) || "The decision was not recorded.",
      };
    }
    return { ok: true, data: data as unknown as PlanDetail };
  } catch {
    return { ok: false, kind: "error", message: FETCH_ERROR };
  }
}

export async function fetchAdminPlans(options: {
  status?: string;
  blockStatus?: string;
  page?: number;
} = {}): Promise<PlanAdminListResult> {
  try {
    const params = new URLSearchParams();
    if (options.status) params.set("status", options.status);
    if (options.blockStatus) params.set("block_status", options.blockStatus);
    params.set("page", String(options.page ?? 1));
    const res = await fetch(`/api/plans/admin/?${params.toString()}`, {
      credentials: "include",
    });
    const data = await readJson(res);
    if (!res.ok) {
      return {
        ok: false,
        kind: "error",
        message: (data.error as string) || (data.detail as string) || "Failed to load plans.",
      };
    }
    return {
      ok: true,
      data: data as unknown as PlanListResponse & { next: string | null; previous: string | null },
    };
  } catch {
    return { ok: false, kind: "error", message: FETCH_ERROR };
  }
}

export async function fetchPlanSettings(): Promise<PlanSettingsResult> {
  try {
    const res = await fetch("/api/plans/settings/", { credentials: "include" });
    const data = await readJson(res);
    if (res.status === 403) {
      return {
        ok: false,
        kind: "forbidden",
        message: (data.error as string) || (data.detail as string) || "Only HR can view plan settings.",
      };
    }
    if (!res.ok) {
      return {
        ok: false,
        kind: "error",
        message: (data.error as string) || (data.detail as string) || "Failed to load plan settings.",
      };
    }
    return { ok: true, data: data as unknown as PlanSettings };
  } catch {
    return { ok: false, kind: "error", message: FETCH_ERROR };
  }
}

export async function updatePlanSettings(
  confirmation_lead_days: number
): Promise<PlanSettingsResult> {
  try {
    const res = await fetch("/api/plans/settings/", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirmation_lead_days }),
      credentials: "include",
    });
    const data = await readJson(res);
    if (!res.ok) {
      return {
        ok: false,
        kind: "error",
        message: (data.error as string) || (data.detail as string) || "The settings could not be saved.",
      };
    }
    return { ok: true, data: data as unknown as PlanSettings };
  } catch {
    return { ok: false, kind: "error", message: FETCH_ERROR };
  }
}

export function planScopeTitle(scope: PlanScope): string {
  switch (scope) {
    case "mine":
      return "My plans";
    case "team":
      return "Team plans";
    case "department":
      return "Department plans";
    case "all":
      return "All plans";
  }
}

function extractFieldErrors(data: Record<string, unknown>): Record<string, string> {
  const raw = (data.errors as Record<string, unknown>) ?? data;
  const fields: Record<string, string> = {};
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

export type { PlanDecisionAction };