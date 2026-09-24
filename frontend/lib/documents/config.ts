import type { DocumentUploadConfig } from "./types";

/**
 * Fallback values mirroring the backend defaults. The backend
 * (``/api/v1/leave-documents/config/``) is the source of truth; these are only
 * used when the config endpoint is unreachable so the UI can still render.
 */
export const DEFAULT_UPLOAD_CONFIG: DocumentUploadConfig = {
  max_size_bytes: 10 * 1024 * 1024,
  allowed_content_types: [
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/gif",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
  ],
};

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}