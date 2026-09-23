import type {
  ApprovalDetail,
  ApprovalListResponse,
  Capabilities,
  DecisionInput,
  DocumentDownload,
} from "./types";

const API_PREFIX = "/api/approvals";

/**
 * API failure carrying the HTTP status and the parsed JSON error payload so
 * the UI can distinguish 400 / 403 / 404 / 409 and render field errors.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly data: unknown;

  constructor(status: number, data: unknown, message?: string) {
    super(message ?? `Request failed with status ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

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

export function fetchCapabilities(): Promise<Capabilities> {
  return request<Capabilities>(`${API_PREFIX}/capabilities/`);
}

export interface ApprovalsListParams {
  tab?: "pending" | "decided";
  q?: string;
  page?: number;
  pageSize?: number;
}

export function fetchApprovalsList(
  params: ApprovalsListParams = {}
): Promise<ApprovalListResponse> {
  const url = new URL(`${API_PREFIX}/`, window.location.origin);
  if (params.tab) url.searchParams.set("tab", params.tab);
  if (params.q) url.searchParams.set("q", params.q);
  if (params.page && params.page > 1) {
    url.searchParams.set("page", String(params.page));
  }
  if (params.pageSize) {
    url.searchParams.set("page_size", String(params.pageSize));
  }
  return request<ApprovalListResponse>(url.toString());
}

export function fetchApprovalDetail(id: string): Promise<ApprovalDetail> {
  return request<ApprovalDetail>(`${API_PREFIX}/${encodeURIComponent(id)}/`);
}

export function submitDecision(
  id: string,
  input: DecisionInput
): Promise<ApprovalDetail> {
  return request<ApprovalDetail>(`${API_PREFIX}/${encodeURIComponent(id)}/decision/`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function fetchDocumentDownload(
  id: string,
  documentId: string
): Promise<DocumentDownload> {
  return request<DocumentDownload>(
    `${API_PREFIX}/${encodeURIComponent(id)}/documents/${encodeURIComponent(documentId)}/download-url/`
  );
}