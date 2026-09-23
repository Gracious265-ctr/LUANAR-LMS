"use client";

import { useCallback, useRef, useState } from "react";
import { useDropzone } from "react-dropzone";
import { FileText, History, Loader2, RefreshCw, Trash2, Upload } from "lucide-react";

import { cn } from "@/lib/utils";

import { formatDateTime } from "@/lib/tracking/format";
import type {
  ActiveDocument,
  RetiredDocument,
} from "@/lib/applications/resubmission-types";

/**
 * Active + retired supporting documents for the resubmission edit page. Adds
 * attach new files; Replace/Remove retire the current file (it is kept in the
 * application history) — the backend returns the refreshed edit context.
 */
export function ResubmissionDocuments({
  documents,
  retired,
  readOnly,
  busy,
  onAdd,
  onReplace,
  onRemove,
}: {
  documents: ActiveDocument[];
  retired: RetiredDocument[];
  readOnly?: boolean;
  busy?: boolean;
  onAdd: (file: File) => Promise<void>;
  onReplace: (documentId: string, file: File) => Promise<void>;
  onRemove: (documentId: string) => Promise<void>;
}) {
  const [uploading, setUploading] = useState(false);
  const replaceInputRef = useRef<HTMLInputElement>(null);
  const pendingReplaceRef = useRef<string | null>(null);

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      setUploading(true);
      try {
        for (const file of acceptedFiles) {
          await onAdd(file);
        }
      } finally {
        setUploading(false);
      }
    },
    [onAdd]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    disabled: readOnly || busy || uploading,
    multiple: true,
  });

  const handleRemoveClick = useCallback(
    async (document: ActiveDocument) => {
      const ok = window.confirm(
        `Remove "${document.name}"? The file is kept in the application history.`
      );
      if (!ok) return;
      await onRemove(document.id);
    },
    [onRemove]
  );

  const handleReplacePick = useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      event.target.value = "";
      if (!file) return;
      const documentId = pendingReplaceRef.current;
      if (!documentId) return;
      pendingReplaceRef.current = null;
      await onReplace(documentId, file);
    },
    [onReplace]
  );

  return (
    <div>
      <label className="mb-1.5 block text-sm font-medium text-text-secondary">
        Supporting Documents
      </label>

      {!readOnly && (
        <div
          {...getRootProps()}
          className={cn(
            "border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors",
            isDragActive
              ? "border-brand-primary bg-brand-primary-subtle"
              : "border-border-default hover:border-border-strong"
          )}
        >
          <input {...getInputProps()} />
          <Upload className="mx-auto mb-2 h-8 w-8 text-text-muted" aria-hidden="true" />
          <p className="text-sm text-text-secondary">
            {uploading || busy
              ? "Uploading..."
              : "Drag & drop files here, or click to add"}
          </p>
          <p className="mt-1 text-xs text-text-muted">Max file size: 10MB</p>
        </div>
      )}

      {documents.length > 0 && (
        <ul className="mt-3 space-y-2">
          {documents.map((document) => (
            <li
              key={document.id}
              className="flex items-center justify-between gap-3 rounded-lg border border-border-default bg-surface-card p-3"
            >
              <div className="flex min-w-0 items-center gap-3">
                <FileText
                  className="h-4 w-4 shrink-0 text-text-muted"
                  aria-hidden="true"
                />
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-text-primary">
                    {document.name}
                  </p>
                  <p className="text-xs text-text-muted">
                    {formatBytes(document.size_bytes)}
                    {document.uploaded_at && (
                      <>
                        {" · "}
                        {formatDateTime(document.uploaded_at)}
                      </>
                    )}
                  </p>
                </div>
              </div>
              {!readOnly && (
                <div className="flex shrink-0 items-center gap-1">
                  <ActionButton
                    label={`Replace ${document.name}`}
                    onClick={() => {
                      pendingReplaceRef.current = document.id;
                      replaceInputRef.current?.click();
                    }}
                    disabled={busy}
                    title="Replace"
                  >
                    <RefreshCw className="h-4 w-4" aria-hidden="true" />
                  </ActionButton>
                  <ActionButton
                    label={`Remove ${document.name}`}
                    onClick={() => void handleRemoveClick(document)}
                    disabled={busy}
                    title="Remove"
                    danger
                  >
                    <Trash2 className="h-4 w-4" aria-hidden="true" />
                  </ActionButton>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {!readOnly && (
        <input
          ref={replaceInputRef}
          type="file"
          className="sr-only"
          tabIndex={-1}
          aria-hidden="true"
          onChange={(event) => void handleReplacePick(event)}
        />
      )}

      {busy && (
        <p role="status" className="mt-2 flex items-center gap-2 text-sm text-text-muted">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          Saving documents…
        </p>
      )}

      {retired.length > 0 && (
        <div className="mt-4">
          <h4 className="flex items-center gap-1.5 text-xs font-medium text-text-muted uppercase tracking-wide">
            <History className="h-3.5 w-3.5" aria-hidden="true" />
            Previous versions (kept in history)
          </h4>
          <ul className="mt-2 space-y-1">
            {retired.map((document) => (
              <li
                key={document.id}
                className="flex items-center justify-between gap-3 text-sm"
              >
                <span className="min-w-0 truncate text-text-secondary">
                  {document.name}
                </span>
                <span className="shrink-0 text-xs text-text-muted">
                  {retiredReasonLabel(document)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function ActionButton({
  label,
  onClick,
  disabled,
  title,
  danger,
  children,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  title: string;
  danger?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={title}
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "rounded p-1.5 text-text-muted transition-colors hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary disabled:cursor-not-allowed disabled:opacity-50",
        danger ? "hover:text-status-rejected" : "hover:text-text-primary"
      )}
    >
      {children}
    </button>
  );
}

function retiredReasonLabel(document: RetiredDocument): string {
  if (document.retire_reason === "replaced" && document.replaced_by_name) {
    return `Replaced by ${document.replaced_by_name}`;
  }
  if (document.replaced_by_name) {
    return `Replaced by ${document.replaced_by_name}`;
  }
  return "Removed";
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}