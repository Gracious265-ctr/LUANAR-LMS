"use client";

<<<<<<< HEAD
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
=======
import { useCallback, useRef, useState } from "react";
import { useDropzone } from "react-dropzone";
import { FileText, FileX, RefreshCw, Trash2, Upload } from "lucide-react";

import {
  deleteDocument,
  listDocuments,
  replaceDocument,
  uploadDocument,
  type SupportingDocument,
} from "@/lib/leave-api";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/states";
import { useToast } from "@/components/ui/toast";
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
>>>>>>> feature/plans-teams

interface SupportingDocumentsUploaderProps {
  applicationId: string | null;
  documents: SupportingDocument[];
<<<<<<< HEAD
  disabled?: boolean;
  mode?: "editable" | "readonly";
=======
  editable?: boolean;
  /** Offer per-row Replace (true on a ``correction_required`` application only). */
  canReplace?: boolean;
>>>>>>> feature/plans-teams
  onDocumentsChange: (docs: SupportingDocument[]) => void;
  onEnsureDraft?: () => Promise<string | null>;
}

export function SupportingDocumentsUploader({
  applicationId,
  documents,
<<<<<<< HEAD
  disabled,
  mode = "editable",
=======
  editable = true,
  canReplace = false,
>>>>>>> feature/plans-teams
  onDocumentsChange,
  onEnsureDraft,
}: SupportingDocumentsUploaderProps) {
  const [uploading, setUploading] = useState(false);
<<<<<<< HEAD
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
=======
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pendingRemoval, setPendingRemoval] =
    useState<SupportingDocument | null>(null);
  const replaceInputs = useRef<Record<string, HTMLInputElement | null>>({});
  const { showToast } = useToast();

  const refresh = useCallback(
    async (applicationIdToFetch: string) => {
      onDocumentsChange(await listDocuments(applicationIdToFetch));
    },
    [onDocumentsChange]
>>>>>>> feature/plans-teams
  );

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      if (acceptedFiles.length === 0) return;
      let id = applicationId;
      if (!id && onEnsureDraft) {
        id = await onEnsureDraft();
      }
<<<<<<< HEAD
      if (!id) return;
      for (const file of acceptedFiles) {
        await applyUpload(id, file);
      }
    },
    [applicationId, onEnsureDraft, applyUpload]
=======
      if (!id) {
        setError("Could not create a draft to attach the document. Please try again.");
        return;
      }
      setUploading(true);
      setError(null);
      // Rows for the chosen files appear immediately, keyed by a client token;
      // the refresh below replaces them with the server's own records.
      const snapshot = documents;
      const placeholders: SupportingDocument[] = acceptedFiles.map(
        (file, index) => ({
          id: `pending-${Date.now()}-${index}`,
          file_url: "",
          file_name: file.name,
          file_size: file.size,
          content_type: file.type || "application/octet-stream",
          uploaded_at: new Date().toISOString(),
          status: "active",
          retired_at: null,
          retire_reason: null,
          retired_by: null,
          replaced_by: null,
        })
      );
      onDocumentsChange([...documents, ...placeholders]);
      try {
        for (const file of acceptedFiles) {
          await uploadDocument(id, file);
        }
        await refresh(id);
        showToast(
          acceptedFiles.length > 1
            ? `${acceptedFiles.length} documents uploaded.`
            : "Document uploaded."
        );
      } catch (err) {
        // Server truth for whatever landed; fall back to the pre-upload list
        // if even the refresh fails.
        try {
          await refresh(id);
        } catch {
          onDocumentsChange(snapshot);
        }
        const message =
          err instanceof Error
            ? err.message
            : "Upload failed. Check the file and try again.";
        setError(message);
        showToast(message, "error");
      } finally {
        setUploading(false);
      }
    },
    [applicationId, documents, onEnsureDraft, onDocumentsChange, refresh, showToast]
>>>>>>> feature/plans-teams
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
<<<<<<< HEAD
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
=======
    disabled: !editable || uploading,
  });

  const handleRemove = useCallback(
    async (document: SupportingDocument) => {
      if (!applicationId || busyId) return;
      setBusyId(document.id);
      setError(null);
      // The row leaves the list before the request; failure puts it back.
      onDocumentsChange(documents.filter((doc) => doc.id !== document.id));
      try {
        await deleteDocument(applicationId, document.id);
        await refresh(applicationId);
        showToast("Document removed.");
      } catch (err) {
        onDocumentsChange(documents);
        const message =
          err instanceof Error
            ? err.message
            : "Could not remove this document. Please try again.";
        setError(message);
        showToast(message, "error");
      } finally {
        setBusyId(null);
      }
    },
    [applicationId, busyId, documents, onDocumentsChange, refresh, showToast]
  );

  const handleReplace = useCallback(
    async (document: SupportingDocument, file: File) => {
      if (!applicationId || busyId) return;
      setBusyId(document.id);
      setError(null);
      // The row renames to the chosen file immediately; failure restores the
      // previous name and size.
      const snapshot = documents;
      onDocumentsChange(
        documents.map((doc) =>
          doc.id === document.id
            ? { ...doc, file_name: file.name, file_size: file.size }
            : doc
        )
      );
      try {
        await replaceDocument(applicationId, document.id, file);
        await refresh(applicationId);
        showToast("Document replaced.");
      } catch (err) {
        onDocumentsChange(snapshot);
        const message =
          err instanceof Error
            ? err.message
            : "Could not replace this document. Please try again.";
        setError(message);
        showToast(message, "error");
      } finally {
        setBusyId(null);
        const input = replaceInputs.current[document.id];
        if (input) input.value = "";
      }
    },
    [applicationId, busyId, documents, onDocumentsChange, refresh, showToast]
>>>>>>> feature/plans-teams
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

<<<<<<< HEAD
      {isEditable && (
=======
      {editable && (
>>>>>>> feature/plans-teams
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

<<<<<<< HEAD
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
=======
      {canReplace && editable && documents.length > 0 && (
        <p className="mt-2 text-xs text-text-muted">
          This application was returned for correction. Replace a document to
          submit a corrected copy — the previous version stays in your history
          for the approvers to compare.
>>>>>>> feature/plans-teams
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
<<<<<<< HEAD
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
=======
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
                        disabled={busyId !== null || uploading}
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
                    disabled={busyId !== null || uploading}
                    variant="ghost"
                    size="icon"
                    className="h-auto w-auto p-1.5 hover:text-status-rejected"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              )}
>>>>>>> feature/plans-teams
            </div>
          ))}
        </div>
      )}

<<<<<<< HEAD
      {documents.length === 0 && (
        <p className="mt-3 text-sm text-text-muted">
          {isEditable
            ? "No supporting documents yet."
            : "No supporting documents available."}
        </p>
      )}
=======
      {!editable && documents.length === 0 && (
        <EmptyState
          className="py-6"
          icon={<FileX className="h-8 w-8" />}
          title="No supporting documents attached"
          description="Files attached to this application will show up here."
        />
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
>>>>>>> feature/plans-teams
    </div>
  );
}