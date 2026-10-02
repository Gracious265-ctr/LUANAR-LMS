"use client";

import { useCallback, useRef, useState } from "react";
import { useDropzone } from "react-dropzone";
import { FileText, RefreshCw, Trash2, Upload } from "lucide-react";

import {
  deleteDocument,
  listDocuments,
  replaceDocument,
  uploadDocument,
  type SupportingDocument,
} from "@/lib/leave-api";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

interface SupportingDocumentsUploaderProps {
  applicationId: string | null;
  documents: SupportingDocument[];
  editable?: boolean;
  /** Offer per-row Replace (true on a ``correction_required`` application only). */
  canReplace?: boolean;
  onDocumentsChange: (docs: SupportingDocument[]) => void;
  onEnsureDraft?: () => Promise<string | null>;
}

export function SupportingDocumentsUploader({
  applicationId,
  documents,
  editable = true,
  canReplace = false,
  onDocumentsChange,
  onEnsureDraft,
}: SupportingDocumentsUploaderProps) {
  const [uploading, setUploading] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pendingRemoval, setPendingRemoval] =
    useState<SupportingDocument | null>(null);
  const replaceInputs = useRef<Record<string, HTMLInputElement | null>>({});

  const refresh = useCallback(
    async (applicationIdToFetch: string) => {
      onDocumentsChange(await listDocuments(applicationIdToFetch));
    },
    [onDocumentsChange]
  );

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
        for (const file of acceptedFiles) {
          await uploadDocument(id, file);
        }
        await refresh(id);
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
    [applicationId, onEnsureDraft, refresh]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    disabled: !editable || uploading,
  });

  const handleRemove = useCallback(
    async (document: SupportingDocument) => {
      if (!applicationId || busyId) return;
      setBusyId(document.id);
      setError(null);
      try {
        await deleteDocument(applicationId, document.id);
        await refresh(applicationId);
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Could not remove this document. Please try again."
        );
      } finally {
        setBusyId(null);
      }
    },
    [applicationId, busyId, refresh]
  );

  const handleReplace = useCallback(
    async (document: SupportingDocument, file: File) => {
      if (!applicationId || busyId) return;
      setBusyId(document.id);
      setError(null);
      try {
        await replaceDocument(applicationId, document.id, file);
        await refresh(applicationId);
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Could not replace this document. Please try again."
        );
      } finally {
        setBusyId(null);
        const input = replaceInputs.current[document.id];
        if (input) input.value = "";
      }
    },
    [applicationId, busyId, refresh]
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

      {editable && (
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

      {canReplace && editable && documents.length > 0 && (
        <p className="mt-2 text-xs text-text-muted">
          This application was returned for correction. Replace a document to
          submit a corrected copy — the previous version stays in your history
          for the approvers to compare.
        </p>
      )}

      {documents.length > 0 && (
        <div className="mt-3 space-y-2">
          {documents.map((doc) => (
            <div
              key={doc.id}
              className="flex items-center justify-between rounded-lg border border-border-default bg-surface-card p-3 gap-3"
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
              {editable && (
                <div className="flex items-center gap-1 shrink-0">
                  {canReplace && (
                    <>
                      <input
                        ref={(el) => {
                          replaceInputs.current[doc.id] = el;
                        }}
                        type="file"
                        aria-label={`Replace document ${doc.file_name}`}
                        className="sr-only"
                        onChange={(e) => {
                          const file = e.target.files?.[0];
                          if (file) void handleReplace(doc, file);
                        }}
                      />
                      <Button
                        type="button"
                        onClick={() => replaceInputs.current[doc.id]?.click()}
                        disabled={busyId !== null}
                        variant="secondary"
                        size="sm"
                      >
                        <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
                        {busyId === doc.id ? "Replacing…" : "Replace"}
                      </Button>
                    </>
                  )}
                  <Button
                    type="button"
                    aria-label={`Remove document ${doc.file_name}`}
                    onClick={() => setPendingRemoval(doc)}
                    disabled={busyId !== null}
                    variant="ghost"
                    size="icon"
                    className="h-auto w-auto p-1.5 hover:text-status-rejected"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {!editable && documents.length === 0 && (
        <p className="text-sm text-text-secondary">
          No supporting documents were attached.
        </p>
      )}

      {error && editable && (
        <p role="alert" className="text-xs text-status-rejected mt-2">
          {error}
        </p>
      )}

      {/* An in-app dialog rather than `window.confirm`, which browsers suppress
          and cannot be styled to match the rest of the app. */}
      <AlertDialog
        open={pendingRemoval !== null}
        onOpenChange={(next) => {
          if (!next) setPendingRemoval(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              Remove {pendingRemoval?.file_name}?
            </AlertDialogTitle>
            <AlertDialogDescription>
              {canReplace
                ? "The file stays archived under the previous submission."
                : "This permanently deletes the file."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                const target = pendingRemoval;
                setPendingRemoval(null);
                if (target) void handleRemove(target);
              }}
            >
              Remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}