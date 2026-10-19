import type {
  ApprovalCapabilities,
  ApprovalListResponse,
  ApprovalReview,
  ApprovalTab,
  BulkApprovalItem,
  BulkApprovalResponse,
  DecisionBriefing,
  DecisionPayload,
  DocumentDownload,
} from "./types";

export type ApprovalsListResult =
  | { ok: true; data: ApprovalListResponse }
  | { ok: false; kind: "error"; message: string };

export type ApprovalDetailResult =
  | { ok: true; data: ApprovalReview }
  | { ok: false; kind: "not_found" | "error"; message: string };

export type DecisionResult =
  | { ok: true; data: DecisionBriefing }
  | {
      ok: false;
      kind: "validation" | "forbidden" | "conflict" | "blocked" | "not_found" | "error";
      message: string;
      reason?: string | null;
      fields?: Record<string, string>;
    };

export type ApprovalCapabilitiesResult = ApprovalCapabilities;

export type BulkApprovalResult =
  | { ok: true; data: BulkApprovalResponse }
  | { ok: false; message: string };

const FETCH_ERROR = "Could not reach the server. Check your connection and try again.";

async function readJson(res: Response): Promise<Record<string, unknown>> {
  return res.json().catch(() => ({}));
}

function listQuery(tab: ApprovalTab, q: string, page: number): string {
  const params = new URLSearchParams({ tab, page: String(page) });
  if (q) params.set("q", q);
  return params.toString();
}

export async function fetchApprovals(
  tab: ApprovalTab,
  q: string,
  page: number
): Promise<ApprovalsListResult> {
  try {
    const res = await fetch(`/api/approvals/?${listQuery(tab, q, page)}`, {
      credentials: "include",
    });
    const data = await readJson(res);
    if (!res.ok) {
      return {
        ok: false,
        kind: "error",
        message: (data.detail as string) || "Failed to load approvals.",
      };
    }
    return { ok: true, data: data as unknown as ApprovalListResponse };
  } catch {
    return { ok: false, kind: "error", message: FETCH_ERROR };
  }
}

export async function fetchApproval(id: string): Promise<ApprovalDetailResult> {
  try {
    const res = await fetch(
      `/api/approvals/${encodeURIComponent(id)}/`,
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
        message: (data.detail as string) || "Failed to load the application.",
      };
    }
    return { ok: true, data: data as unknown as ApprovalReview };
  } catch {
    return { ok: false, kind: "error", message: FETCH_ERROR };
  }
}

export async function postDecision(
  id: string,
  payload: DecisionPayload
): Promise<DecisionResult> {
  try {
    const res = await fetch(
      `/api/approvals/${encodeURIComponent(id)}/decision/`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        credentials: "include",
      }
    );
    const data = await readJson(res);

    if (res.status === 409) {
      const reason = (data.reason as string) || "stage_changed";
      // `workflow_unavailable` is not a stale read: no approver remains for the
      // application, so reloading will never unblock this decision. It is a
      // blocked state, not a conflict, and must not offer a Refresh that
      // cannot help.
      if (reason === "workflow_unavailable") {
        return {
          ok: false,
          kind: "blocked",
          message:
            (data.error as string) ||
            "This application has no approver available: the only remaining approver is the applicant themself.",
          reason,
        };
      }
      return {
        ok: false,
        kind: "conflict",
        message: (data.error as string) || "This application has changed since you opened it.",
        reason,
      };
    }
    if (res.status === 403) {
      return {
        ok: false,
        kind: "forbidden",
        message: (data.error as string) || "You are not allowed to decide on this application.",
        reason: (data.reason as string) || null,
      };
    }
    if (res.status === 404) {
      return {
        ok: false,
        kind: "not_found",
        message: (data.error as string) || "Application not found.",
      };
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
    return { ok: true, data: data as unknown as DecisionBriefing };
  } catch {
    return { ok: false, kind: "error", message: FETCH_ERROR };
  }
}

/**
 * Approve a batch of applications in one request (UI/UX Phase 2, spec 3.11).
 *
 * The batch is approve-only and capped server-side. A batch can part-succeed:
 * `ok` only reflects whether the request was accepted, so read `data.approved`
 * and `data.failed` for the outcome.
 */
export async function approveApprovals(
  items: BulkApprovalItem[],
  comment = ""
): Promise<BulkApprovalResult> {
  try {
    const res = await fetch("/api/approvals/bulk-decision/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "approve", comment, items }),
      credentials: "include",
    });
    const data = await readJson(res);
    if (!res.ok) {
      return {
        ok: false,
        message:
          (data.error as string) ||
          (data.detail as string) ||
          "The batch could not be approved.",
      };
    }
    return { ok: true, data: data as unknown as BulkApprovalResponse };
  } catch {
    return { ok: false, message: FETCH_ERROR };
  }
}

export async function fetchDocumentDownload(
  id: string,
  documentId: string
): Promise<DocumentDownload> {
  const res = await fetch(
    `/api/approvals/${encodeURIComponent(id)}/documents/${encodeURIComponent(documentId)}/download-url/`,
    { credentials: "include" }
  );
  const data = await readJson(res);
  if (!res.ok) {
    throw new Error(
      (data.error as string) || (data.detail as string) || "Could not open the document."
    );
  }
  return data as unknown as DocumentDownload;
}

export async function fetchCapabilities(): Promise<ApprovalCapabilitiesResult> {
  try {
    const res = await fetch("/api/approvals/capabilities/", {
      credentials: "include",
    });
    const data = await readJson(res);
    return {
      is_approver: Boolean(data.is_approver),
      pending_count: Number(data.pending_count) || 0,
    };
  } catch {
    return { is_approver: false, pending_count: 0 };
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