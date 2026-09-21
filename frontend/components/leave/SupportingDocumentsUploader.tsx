"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, Trash2, FileText } from "lucide-react";

import { uploadDocument, deleteDocument, type SupportingDocument } from "@/lib/leave-api";
import { cn } from "@/lib/utils";

interface SupportingDocumentsUploaderProps {
  applicationId: string | null;
  documents: SupportingDocument[];
  disabled?: boolean;
  onDocumentsChange: (docs: SupportingDocument[]) => void;
  onEnsureDraft?: () => Promise<string | null>;
}

export function SupportingDocumentsUploader({
  applicationId,
  documents,
  disabled,
  onDocumentsChange,
  onEnsureDraft,
}: SupportingDocumentsUploaderProps) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      if (acceptedFiles.length === 0) return;
      let id = applicationId;
      if (!id && onEnsureDraft) {
        id = await onEnsureDraft();
      }
      if (!id) {
        setError("Could not create a draft to attach the document. Please try again.");
        return;
      }
      setUploading(true);
      setError(null);
      try {
        let updated = [...documents];
        for (const file of acceptedFiles) {
          const doc = await uploadDocument(id, file);
          updated = [...updated, doc];
        }
        onDocumentsChange(updated);
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Upload failed. Check the file and try again."
        );
      } finally {
        setUploading(false);
      }
    },
    [applicationId, documents, onDocumentsChange, onEnsureDraft]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    disabled: disabled || uploading,
  });

  const handleRemove = useCallback(
    async (docId: string) => {
      if (!applicationId) return;
      setError(null);
      try {
        await deleteDocument(applicationId, docId);
        onDocumentsChange(documents.filter((d) => d.id !== docId));
      } catch {
        setError("Could not remove this document. Please try again.");
      }
    },
    [applicationId, documents, onDocumentsChange]
  );

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div>
      <label className="block text-sm font-medium text-text-secondary mb-1.5">
        Supporting Documents
      </label>

      {!disabled && (
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
            Max file size: 10MB
          </p>
        </div>
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
              {!disabled && (
                <button
                  type="button"
                  aria-label={`Remove document ${doc.file_name}`}
                  onClick={() => handleRemove(doc.id)}
                  className="shrink-0 p-1 rounded hover:bg-surface-hover text-text-muted hover:text-status-rejected transition-colors"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {error && !disabled && (
        <p role="alert" className="text-xs text-status-rejected mt-2">
          {error}
        </p>
      )}
    </div>
  );
}
