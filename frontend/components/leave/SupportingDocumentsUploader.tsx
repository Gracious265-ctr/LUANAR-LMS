"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useDropzone } from "react-dropzone";
import { Download, FileText, RefreshCw, Trash2, Upload } from "lucide-react";

import { cn } from "@/lib/utils";
import { formatFileSize } from "@/lib/documents/config";
import {
  DocumentRequestError,
  documentContentUrl,
  getDocumentConfig,
  removeDocument,
  replaceDocument,
  uploadDocument,
} from "@/lib/documents/service";
import type {
  DocumentUploadConfig,
  SupportingDocument,
} from "@/lib/documents/types";

interface SupportingDocumentsUploaderProps {
  applicationId: string | null;
  documents: SupportingDocument[];
  disabled?: boolean;
  mode?: "editable" | "readonly";
  onDocumentsChange: (docs: SupportingDocument[]) => void;
  onEnsureDraft?: () => Promise<string | null>;
}

export function SupportingDocumentsUploader({
  applicationId,
  documents,
  disabled,
  mode = "editable",
  onDocumentsChange,
  onEnsureDraft,
}: SupportingDocumentsUploaderProps) {
  const [uploading, setUploading] = useState(false);
  const [replacingId, setReplacingId] = useState<string | null>(null);
  const [config, setConfig] = useState<DocumentUploadConfig | null>(null);
  const [readOnlyMessage, setReadOnlyMessage] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const replaceInputs = useRef<Record<string, HTMLInputElement | null>>({});

  const isEditable = !disabled && mode === "editable";

  useEffect(() => {
    let active = true;
    getDocumentConfig().then((value) => {
      if (active) setConfig(value);
    });
    return () => {
      active = false;
    };
  }, []);

  const applyUpload = useCallback(
    async (id: string, file: File) => {
      setUploading(true);
      setReadOnlyMessage(null);
      setUploadError(null);
      try {
        const doc = await uploadDocument(id, file);
        onDocumentsChange([...documents, doc]);
      } catch (err) {
        if (err instanceof DocumentRequestError && err.status === 409) {
          setReadOnlyMessage(err.message);
        } else {
          setUploadError(
            err instanceof Error ? err.message : "The upload could not be completed."
          );
        }
      } finally {
        setUploading(false);
      }
    },
    [documents, onDocumentsChange]
  );

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      if (acceptedFiles.length === 0) return;
      let id = applicationId;
      if (!id && onEnsureDraft) {
        id = await onEnsureDraft();
      }
      if (!id) return;
      for (const file of acceptedFiles) {
        await applyUpload(id, file);
      }
    },
    [applicationId, onEnsureDraft, applyUpload]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    disabled: !isEditable || uploading,
    accept: config
      ? Object.fromEntries(config.allowed_content_types.map((type) => [type, []]))
      : undefined,
  });

  const handleRemove = useCallback(
    async (docId: string) => {
      if (!applicationId || !isEditable) return;
      setReadOnlyMessage(null);
      setUploadError(null);
      try {
        await removeDocument(applicationId, docId);
        onDocumentsChange(documents.filter((d) => d.id !== docId));
      } catch (err) {
        if (err instanceof DocumentRequestError && err.status === 409) {
          setReadOnlyMessage(err.message);
        } else {
          setUploadError(
            err instanceof Error ? err.message : "The document could not be removed."
          );
        }
      }
    },
    [applicationId, documents, isEditable, onDocumentsChange]
  );

  const handleReplace = useCallback(
    async (docId: string, file: File) => {
      if (!applicationId || !isEditable) return;
      setReplacingId(docId);
      setReadOnlyMessage(null);
      setUploadError(null);
      try {
        const replacement = await replaceDocument(applicationId, docId, file);
        onDocumentsChange(
          documents.map((d) => (d.id === docId ? replacement : d))
        );
      } catch (err) {
        if (err instanceof DocumentRequestError && err.status === 409) {
          setReadOnlyMessage(err.message);
        } else {
          setUploadError(
            err instanceof Error ? err.message : "The document could not be replaced."
          );
        }
      } finally {
        setReplacingId(null);
      }
    },
    [applicationId, documents, isEditable, onDocumentsChange]
  );

  return (
    <div>
      <label className="block text-sm font-medium text-text-secondary mb-1.5">
        Supporting Documents
      </label>

      {isEditable && (
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
          <Upload className="h-8 w-8 mx-auto text-text-muted mb-2" />
          <p className="text-sm text-text-secondary">
            {uploading
              ? "Uploading..."
              : "Drag & drop files here, or click to select"}
          </p>
          <p className="text-xs text-text-muted mt-1">
            Max file size: {formatFileSize(config?.max_size_bytes ?? 10 * 1024 * 1024)}
          </p>
        </div>
      )}

      {readOnlyMessage && (
        <p
          role="alert"
          className="mt-3 rounded-lg border border-border-warning bg-status-pending-subtle p-3 text-sm text-status-pending"
        >
          {readOnlyMessage}
        </p>
      )}

      {uploadError && (
        <p role="alert" className="mt-3 text-sm text-status-rejected">
          {uploadError}
        </p>
      )}

      {documents.length > 0 && (
        <div className="mt-3 space-y-2">
          {documents.map((doc) => (
            <div
              key={doc.id}
              className="flex items-center justify-between rounded-lg border border-border-default bg-surface-card p-3"
            >
              <div className="flex items-center gap-3 min-w-0">
                <FileText className="h-4 w-4 text-text-muted shrink-0" />
                <div className="min-w-0">
                  <p className="text-sm font-medium text-text-primary truncate">
                    {doc.file_name}
                  </p>
                  <p className="text-xs text-text-muted">
                    {formatFileSize(doc.file_size)}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                {applicationId && (
                  <a
                    href={documentContentUrl(applicationId, doc.id)}
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label={`Open ${doc.file_name}`}
                    className="p-1 rounded hover:bg-surface-hover text-text-muted hover:text-text-primary transition-colors"
                  >
                    <Download className="h-4 w-4" />
                  </a>
                )}
                {isEditable && (
                  <>
                    <input
                      ref={(node) => {
                        replaceInputs.current[doc.id] = node;
                      }}
                      type="file"
                      hidden
                      aria-label={`Replace ${doc.file_name}`}
                      onClick={(event) => {
                        event.currentTarget.value = "";
                      }}
                      onChange={(event) => {
                        const file = event.target.files?.[0];
                        if (file) handleReplace(doc.id, file);
                      }}
                    />
                    <button
                      type="button"
                      onClick={() => replaceInputs.current[doc.id]?.click()}
                      disabled={replacingId === doc.id}
                      aria-label={`Replace ${doc.file_name}`}
                      className="p-1 rounded hover:bg-surface-hover text-text-muted hover:text-text-primary transition-colors disabled:opacity-50"
                    >
                      <RefreshCw
                        className={cn("h-4 w-4", replacingId === doc.id && "animate-spin")}
                      />
                    </button>
                    <button
                      type="button"
                      onClick={() => handleRemove(doc.id)}
                      aria-label={`Remove ${doc.file_name}`}
                      className="p-1 rounded hover:bg-surface-hover text-text-muted hover:text-status-rejected transition-colors"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {documents.length === 0 && (
        <p className="mt-3 text-sm text-text-muted">
          {isEditable
            ? "No supporting documents yet."
            : "No supporting documents available."}
        </p>
      )}
    </div>
  );
}