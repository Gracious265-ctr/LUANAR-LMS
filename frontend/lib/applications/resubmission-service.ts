import type {
  ResubmissionContext,
  ResubmissionValidationBody,
  ResubmittedApplication,
} from "./resubmission-types";

const API_PREFIX = "/api/applications";

/**
 * API failure carrying the HTTP status and the parsed JSON error payload so
 * the UI can distinguish 400 (validation) / 404 / 409 (conflicts) and render
 * the correct banner.
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

async function multipart<T>(
  path: string,
  body: FormData
): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    credentials: "include",
    body,
  });

  if (!res.ok) {
    const data = (await res.json().catch(() => null)) as unknown;
    throw new ApiError(res.status, data);
  }

  return (await res.json()) as T;
}

export interface SaveChangesInput {
  leave_type_id: number | null;
  start_date: string | null;
  end_date: string | null;
  reason: string;
  row_version: number;
}

export function getResubmissionContext(id: string): Promise<ResubmissionContext> {
  return request<ResubmissionContext>(`${API_PREFIX}/${encodeURIComponent(id)}/resubmission/`);
}

export function saveChanges(
  id: string,
  input: SaveChangesInput
): Promise<ResubmissionContext> {
  return request<ResubmissionContext>(
    `${API_PREFIX}/${encodeURIComponent(id)}/resubmission/`,
    { method: "PATCH", body: JSON.stringify(input) }
  );
}

export function addResubmissionDocument(
  id: string,
  file: File,
  rowVersion: number
): Promise<ResubmissionContext> {
  const form = new FormData();
  form.append("file", file, file.name);
  form.append("row_version", String(rowVersion));
  return multipart<ResubmissionContext>(
    `${API_PREFIX}/${encodeURIComponent(id)}/resubmission/documents/`,
    form
  );
}

export function replaceResubmissionDocument(
  id: string,
  documentId: string,
  file: File,
  rowVersion: number
): Promise<ResubmissionContext> {
  const form = new FormData();
  form.append("file", file, file.name);
  form.append("row_version", String(rowVersion));
  return multipart<ResubmissionContext>(
    `${API_PREFIX}/${encodeURIComponent(id)}/resubmission/documents/${encodeURIComponent(documentId)}/replace/`,
    form
  );
}

export function removeResubmissionDocument(
  id: string,
  documentId: string,
  rowVersion: number
): Promise<ResubmissionContext> {
  return request<ResubmissionContext>(
    `${API_PREFIX}/${encodeURIComponent(id)}/resubmission/documents/${encodeURIComponent(documentId)}/`,
    { method: "DELETE", body: JSON.stringify({ row_version: rowVersion }) }
  );
}

export function resubmitApplication(
  id: string,
  rowVersion: number
): Promise<ResubmittedApplication> {
  return request<ResubmittedApplication>(
    `${API_PREFIX}/${encodeURIComponent(id)}/resubmit/`,
    { method: "POST", body: JSON.stringify({ row_version: rowVersion }) }
  );
}

/** Extract ``errors: [{code, field, message}]`` from a 400 body, if present. */
export function parseValidationBody(data: unknown): {
  issues: ResubmissionValidationBody["errors"];
} {
  const body = (data ?? {}) as Partial<ResubmissionValidationBody>;
  return { issues: Array.isArray(body.errors) ? body.errors : [] };
}