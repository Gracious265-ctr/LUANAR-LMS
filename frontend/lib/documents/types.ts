export type DocumentStatus = "active" | "retired";

export type DocumentRetireReason = "replaced" | "removed" | null;

export type DocumentAction =
  | "document_uploaded"
  | "document_removed"
  | "document_replaced";

export interface SupportingDocument {
  id: string;
  file_path: string;
  file_url: string;
  file_name: string;
  file_size: number;
  content_type: string;
  uploaded_at: string;
  status: DocumentStatus;
  retired_at: string | null;
  retired_by: number | null;
  retire_reason: DocumentRetireReason;
  replaced_by: string | null;
  replaced_by_name: string | null;
}

export interface DocumentHistoryEvent {
  id: string;
  action: DocumentAction;
  actor_name: string;
  occurred_at: string;
  metadata: Record<string, unknown>;
}

export interface DocumentHistory {
  active: SupportingDocument[];
  retired: SupportingDocument[];
  events: DocumentHistoryEvent[];
}

export interface DocumentUploadConfig {
  max_size_bytes: number;
  allowed_content_types: string[];
}