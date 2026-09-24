import { DEFAULT_UPLOAD_CONFIG } from "./config";
import type {
  DocumentHistory,
  DocumentUploadConfig,
  SupportingDocument,
} from "./types";

/** Raised when the backend rejects a document mutation with a typed body. */
export class DocumentRequestError extends Error {
  readonly status: number;
  readonly code?: string;
  readonly field?: string;

  constructor(status: number, message: string, code?: string, field?: string) {
    super(message);
    this.name = "DocumentRequestError";
    this.status = status;
    this.code = code;
    this.field = field;
  }
}

function documentsPath(applicationId: string, suffix = ""): string {
  return `/api/leave/leave-applications/${applicationId}/documents/${suffix}`;
}

async function readDocumentError(res: Response): Promise<DocumentRequestError> {
  const body = await res.json().catch(() => ({}));
  const code: string | undefined =
    body?.code ??
    (Array.isArray(body?.errors) && typeof body.errors[0]?.code === "string"
      ? body.errors[0].code
      : undefined);
  const field: string | undefined =
    typeof body?.field === "string" ? body.field : undefined;
  const message: string =
    typeof body?.message === "string"
      ? body.message
      : typeof body?.detail === "string"
        ? body.detail
        : "Documents could not be updated.";
  return new DocumentRequestError(res.status, message, code, field);
}

export async function listDocuments(
  applicationId: string
): Promise<SupportingDocument[]> {
  const res = await fetch(documentsPath(applicationId), {
    credentials: "include",
  });
  if (!res.ok) throw await readDocumentError(res);
  const payload = await res.json();
  return Array.isArray(payload) ? payload : (payload.results ?? []);
}

export async function uploadDocument(
  applicationId: string,
  file: File
): Promise<SupportingDocument> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(documentsPath(applicationId), {
    method: "POST",
    credentials: "include",
    body: formData,
  });
  if (!res.ok) throw await readDocumentError(res);
  return res.json();
}

export async function removeDocument(
  applicationId: string,
  documentId: string
): Promise<void> {
  const res = await fetch(documentsPath(applicationId, `${documentId}/`), {
    method: "DELETE",
    credentials: "include",
  });
  if (!res.ok) throw await readDocumentError(res);
}

export async function replaceDocument(
  applicationId: string,
  documentId: string,
  file: File
): Promise<SupportingDocument> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(documentsPath(applicationId, `${documentId}/replace/`), {
    method: "POST",
    credentials: "include",
    body: formData,
  });
  if (!res.ok) throw await readDocumentError(res);
  return res.json();
}

export async function getDocumentHistory(
  applicationId: string
): Promise<DocumentHistory> {
  const res = await fetch(documentsPath(applicationId, "history/"), {
    credentials: "include",
  });
  if (!res.ok) throw await readDocumentError(res);
  return res.json();
}

/** Absolute path (behind the local proxy) to stream a document's bytes. */
export function documentContentUrl(
  applicationId: string,
  documentId: string,
  download = false
): string {
  const base = `/api/leave/leave-applications/${applicationId}/documents/${documentId}/content/`;
  return download ? `${base}?download=1` : base;
}

export async function getDocumentConfig(): Promise<DocumentUploadConfig> {
  const res = await fetch("/api/leave/leave-documents/config/", {
    credentials: "include",
  });
  if (!res.ok) return DEFAULT_UPLOAD_CONFIG;
  try {
    return await res.json();
  } catch {
    return DEFAULT_UPLOAD_CONFIG;
  }
}