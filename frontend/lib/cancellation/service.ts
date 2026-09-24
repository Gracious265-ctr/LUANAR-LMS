import { ApiError } from "@/lib/approvals/service";

import type {
  CancellationApprovalDetail,
  CancellationApprovalListResponse,
  CancellationDecisionInput,
  CancellationDecisionResult,
  CancellationEligibility,
  CancellationRequestSummary,
  SubmitCancellationInput,
  SubmitCancellationResult,
} from "./types";

const APPLICATIONS_PREFIX = "/api/applications";
const APPROVALS_PREFIX = "/api/approvals/cancellations";

/**
 * Shared fetch wrapper for the cancellation endpoints. Reuses the existing
 * ``ApiError`` from the approvals service so the two domains surface failures
 * identically (the proxy routes share the same backend error format).
 */
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    credentials: "include",
    ...init,
    headers: init?.body
      ? { "Content-Type": "application/json", ...init.headers }
      : init?.headers,
  });

  if (!res.ok) {
    const data = (await res.json().catch(() => null)) as unknown;
    throw new ApiError(res.status, data);
  }

  return (await res.json()) as T;
}

export function fetchCancellationEligibility(
  applicationId: string
): Promise<CancellationEligibility> {
  return request<CancellationEligibility>(
    `${APPLICATIONS_PREFIX}/${encodeURIComponent(applicationId)}/cancellation-eligibility/`
  );
}

export function submitCancellation(
  applicationId: string,
  input: SubmitCancellationInput
): Promise<SubmitCancellationResult> {
  return request<SubmitCancellationResult>(
    `${APPLICATIONS_PREFIX}/${encodeURIComponent(applicationId)}/cancel/`,
    { method: "POST", body: JSON.stringify(input) }
  );
}

export function fetchCancellations(
  applicationId: string
): Promise<CancellationRequestSummary[]> {
  return request<CancellationRequestSummary[]>(
    `${APPLICATIONS_PREFIX}/${encodeURIComponent(applicationId)}/cancellations/`
  );
}

export function fetchCancellationApprovalsList(
  tab: "pending" | "decided",
  page = 1,
  pageSize?: number
): Promise<CancellationApprovalListResponse> {
  const url = new URL(
    `${APPROVALS_PREFIX}/`,
    window.location.origin
  );
  url.searchParams.set("tab", tab);
  if (page > 1) url.searchParams.set("page", String(page));
  if (pageSize) url.searchParams.set("page_size", String(pageSize));
  return request<CancellationApprovalListResponse>(url.toString());
}

export function fetchCancellationApprovalDetail(
  requestId: string
): Promise<CancellationApprovalDetail> {
  return request<CancellationApprovalDetail>(
    `${APPROVALS_PREFIX}/${encodeURIComponent(requestId)}/`
  );
}

export function submitCancellationDecision(
  requestId: string,
  input: CancellationDecisionInput
): Promise<CancellationDecisionResult> {
  return request<CancellationDecisionResult>(
    `${APPROVALS_PREFIX}/${encodeURIComponent(requestId)}/decision/`,
    { method: "POST", body: JSON.stringify(input) }
  );
}

export { ApiError };