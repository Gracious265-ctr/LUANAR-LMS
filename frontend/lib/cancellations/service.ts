import type {
  CancellationDetail,
  CancellationDecisionPayload,
  CancellationDecisionResult,
  CancellationEligibility,
  CancellationHistoryResponse,
  CancellationListResponse,
  CancellationRequest,
  CancellationTab,
  SubmitCancellationPayload,
  SubmitCancellationResult,
} from "./types";

export type CancellationEligibilityResult =
  | { ok: true; data: CancellationEligibility }
  | { ok: false; kind: "not_found" | "error"; message: string };

export type CancellationHistoryResult =
  | { ok: true; data: CancellationHistoryResponse }
  | { ok: false; kind: "error"; message: string };

export type CancellationListResult =
  | { ok: true; data: CancellationListResponse }
  | { ok: false; kind: "error"; message: string };

export type CancellationDetailResult =
  | { ok: true; data: CancellationDetail }
  | { ok: false; kind: "not_found" | "error"; message: string };

const FETCH_ERROR =
  "Could not reach the server. Check your connection and try again.";

async function readJson(res: Response): Promise<Record<string, unknown>> {
  return res.json().catch(() => ({}));
}

export async function fetchEligibility(
  applicationId: string
): Promise<CancellationEligibilityResult> {
  try {
    const res = await fetch(
      `/api/leave/leave-applications/${encodeURIComponent(applicationId)}/cancellation-eligibility/`,
      { credentials: "include" }
    );
    const data = await readJson(res);
    if (res.status === 404) {
      return { ok: false, kind: "not_found", message: "Application not found." };
    }
    if (!res.ok) {
      return {
        ok: false,
        kind: "error",
        message: (data.detail as string) || "Failed to load cancellation options.",
      };
    }
    return { ok: true, data: data as unknown as CancellationEligibility };
  } catch {
    return { ok: false, kind: "error", message: FETCH_ERROR };
  }
}

export async function submitCancellation(
  applicationId: string,
  payload: SubmitCancellationPayload
): Promise<SubmitCancellationResult> {
  try {
    const res = await fetch(
      `/api/leave/leave-applications/${encodeURIComponent(applicationId)}/cancel/`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        credentials: "include",
      }
    );
    const data = await readJson(res);
    if (res.ok) {
      return {
        ok: true,
        kind: (data.kind as "withdrawal" | "approved_leave") ?? "approved_leave",
        request: data.request as unknown as CancellationRequest,
      };
    }
    return {
      ok: false,
      kind: "error",
      code: (data.code as string) || "cancellation_error",
      message:
        (data.detail as string) || "The cancellation could not be submitted.",
      eligibility: (data.eligibility as CancellationEligibility | undefined) ?? null,
    };
  } catch {
    return {
      ok: false,
      kind: "error",
      code: "network",
      message: FETCH_ERROR,
      eligibility: null,
    };
  }
}

export async function fetchCancellationHistory(
  applicationId: string
): Promise<CancellationHistoryResult> {
  try {
    const res = await fetch(
      `/api/leave/leave-applications/${encodeURIComponent(applicationId)}/cancellations/`,
      { credentials: "include" }
    );
    const data = await readJson(res);
    if (!res.ok) {
      return {
        ok: false,
        kind: "error",
        message: (data.detail as string) || "Failed to load cancellation history.",
      };
    }
    return { ok: true, data: data as unknown as CancellationHistoryResponse };
  } catch {
    return { ok: false, kind: "error", message: FETCH_ERROR };
  }
}

export async function fetchCancellations(
  tab: CancellationTab,
  page: number
): Promise<CancellationListResult> {
  try {
    const params = new URLSearchParams({ tab, page: String(page) });
    const res = await fetch(`/api/approvals/cancellations/?${params.toString()}`, {
      credentials: "include",
    });
    const data = await readJson(res);
    if (!res.ok) {
      return {
        ok: false,
        kind: "error",
        message:
          (data.detail as string) || (data.error as string) || "Failed to load cancellation requests.",
      };
    }
    return { ok: true, data: data as unknown as CancellationListResponse };
  } catch {
    return { ok: false, kind: "error", message: FETCH_ERROR };
  }
}

export async function fetchCancellationDetail(
  requestId: string
): Promise<CancellationDetailResult> {
  try {
    const res = await fetch(
      `/api/approvals/cancellations/${encodeURIComponent(requestId)}/`,
      { credentials: "include" }
    );
    const data = await readJson(res);
    if (res.status === 404) {
      return {
        ok: false,
        kind: "not_found",
        message: (data.error as string) || "Cancellation request not found.",
      };
    }
    if (!res.ok) {
      return {
        ok: false,
        kind: "error",
        message:
          (data.error as string) || (data.detail as string) || "Failed to load the cancellation request.",
      };
    }
    return { ok: true, data: data as unknown as CancellationDetail };
  } catch {
    return { ok: false, kind: "error", message: FETCH_ERROR };
  }
}

export async function postCancellationDecision(
  requestId: string,
  payload: CancellationDecisionPayload
): Promise<CancellationDecisionResult> {
  try {
    const res = await fetch(
      `/api/approvals/cancellations/${encodeURIComponent(requestId)}/decision/`,
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
        code: (data.code as string) || "request_changed",
        message: (data.error as string) || "This request has changed since you opened it.",
      };
    }
    if (res.status === 403) {
      return {
        ok: false,
        kind: "forbidden",
        code: (data.code as string) || "not_current_approver",
        message: (data.error as string) || "This cancellation is not with you right now.",
      };
    }
    if (res.status === 404) {
      return {
        ok: false,
        kind: "not_found",
        message: (data.error as string) || "Cancellation request not found.",
      };
    }
    if (res.status === 400) {
      const fields: Record<string, string> = {};
      if (data.code === "comment_required") {
        fields.comment = "A comment is required when rejecting a cancellation.";
      }
      return {
        ok: false,
        kind: "validation",
        code: (data.code as string) || "validation_error",
        message: (data.error as string) || "The decision could not be submitted.",
        fields,
      };
    }
    if (!res.ok) {
      return {
        ok: false,
        kind: "error",
        code: (data.code as string) || null,
        message:
          (data.error as string) || (data.detail as string) || "The decision was not recorded.",
      };
    }
    return { ok: true, data: data as unknown as CancellationDetail };
  } catch {
    return {
      ok: false,
      kind: "error",
      code: null,
      message: FETCH_ERROR,
    };
  }
}