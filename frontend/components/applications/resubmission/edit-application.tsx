"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";

import {
  getResubmissionContext,
  saveChanges,
  addResubmissionDocument,
  replaceResubmissionDocument,
  removeResubmissionDocument,
  resubmitApplication,
} from "@/lib/applications/resubmission-service";
import { useLeaveValidation } from "@/lib/hooks/useLeaveValidation";
import { useUnsavedChangesGuard } from "@/components/applications/resubmission/use-unsaved-changes-guard";

import { ResubmissionForm } from "@/components/applications/resubmission/resubmission-form";
import { ResubmissionDocuments } from "@/components/applications/resubmission/resubmission-documents";
import { ResubmitConfirmDialog } from "@/components/applications/resubmission/resubmit-confirm-dialog";
import { ValidationErrorsPanel } from "@/components/applications/resubmission/validation-errors-panel";
import { ApproverFeedbackCard } from "@/components/applications/resubmission/approver-feedback-card";
import { StatusBadge } from "@/components/tracking/StatusBadge";

import type { TrackingStatus } from "@/lib/tracking/types";
import type { ResubmissionContext, ResubmissionContent } from "@/lib/applications/resubmission-types";
import type { ResubmissionValidationIssue } from "@/lib/applications/resubmission-types";

export function EditApplicationContent({
  applicationId,
}: {
  applicationId: string;
}) {
  const router = useRouter();
  const [context, setContext] = useState<ResubmissionContext | null>(null);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [conflictMessage, setConflictMessage] = useState<string | null>(null);
  const [validationIssues, setValidationIssues] = useState<
    ResubmissionValidationIssue[]
  >([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [currentRowVersion, setCurrentRowVersion] = useState<number>(0);

  const content = context?.content;

  // Fetch edit context on mount
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const ctx = await getResubmissionContext(applicationId);
        if (cancelled) return;
        setContext(ctx);
        setCurrentRowVersion(ctx.row_version);
        setLoading(false);
      } catch (err: unknown) {
        if (cancelled) return;
        const e = err as { status?: number; message?: string };
        if (e.status === 404 || e.status === 401) {
          router.push(`/applications/${applicationId}`);
          return;
        }
        setFetchError(e.message ?? "Failed to load application.");
        setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [applicationId, router]);

  // If not editable, redirect
  useEffect(() => {
    if (context && !context.can_edit) {
      router.push(`/applications/${applicationId}`);
    }
  }, [context, applicationId, router]);

  useUnsavedChangesGuard(dirty);

  useLeaveValidation(
    {
      leave_type_id: content?.leave_type_id ?? null,
      start_date: content?.start_date ?? null,
      end_date: content?.end_date ?? null,
      application_id: applicationId,
    },
    { enabled: Boolean(content?.start_date && content?.end_date) }
  );

  const { reference, status, returns_to: returnsTo, feedback } =
    context ?? {} as ResubmissionContext;

  const handleFieldChange = useCallback((patch: Partial<ResubmissionContent>) => {
    setContext((prev) =>
      prev
        ? {
            ...prev,
            content: { ...prev.content, ...patch },
          }
        : prev,
    );
    setDirty(true);
    setValidationIssues([]);
  }, []);

  const handleSave = useCallback(async () => {
    setBusy(true);
    setConflictMessage(null);
    try {
      await saveChanges(applicationId, {
        leave_type_id: content?.leave_type_id ?? null,
        start_date: content?.start_date ?? null,
        end_date: content?.end_date ?? null,
        reason: content?.reason ?? "",
        row_version: currentRowVersion,
      });
      const fresh = await getResubmissionContext(applicationId);
      setContext(fresh);
      setCurrentRowVersion(fresh.row_version);
      setDirty(false);
      setValidationIssues([]);
      return fresh.row_version;
    } catch (err: unknown) {
      const e = err as { status?: number; data?: unknown };
      if (e.status === 409) {
        setConflictMessage(
          "This application was changed in another window. Reload and try again."
        );
      } else if (e.status === 400) {
        const body = (e.data ?? {}) as Record<string, unknown>;
        setValidationIssues(
          Array.isArray(body.errors) ? (body.errors as ResubmissionValidationIssue[]) : []
        );
      } else {
        setConflictMessage("Save failed. Please try again.");
      }
      return null;
    } finally {
      setBusy(false);
    }
  }, [applicationId, content, currentRowVersion]);

  const handleResubmit = useCallback(async () => {
    setBusy(true);
    setConflictMessage(null);
    try {
      if (dirty) {
        const newRowVersion = await handleSave();
        if (newRowVersion === null) return;
        await resubmitApplication(applicationId, newRowVersion);
      } else {
        await resubmitApplication(applicationId, currentRowVersion);
      }
      router.push(`/applications/${applicationId}`);
    } catch (err: unknown) {
      setBusy(false);
      const e = err as { status?: number; data?: { code?: string; detail?: string } };
      if (e.status === 409 && e.data?.code === "approver_unavailable") {
        setConflictMessage(
          e.data?.detail ??
            "Your approver is currently unavailable. Please contact HR."
        );
      } else if (e.status === 409 && e.data?.code === "workflow_inconsistent") {
        setConflictMessage(
          "The workflow state changed. Reload and try again."
        );
      } else if (e.status === 409) {
        setConflictMessage(
          "This application was changed in another window. Reload and try again."
        );
      } else if (e.status === 400) {
        const body = (e.data ?? {}) as Record<string, unknown>;
        setValidationIssues(
          Array.isArray(body.errors) ? (body.errors as ResubmissionValidationIssue[]) : []
        );
        setDialogOpen(false);
      } else {
        setConflictMessage("Resubmit failed. Please try again.");
      }
    }
  }, [applicationId, dirty, handleSave, router]);

  const handleAddDocument = useCallback(
    async (file: File) => {
      try {
        const fresh = await addResubmissionDocument(
          applicationId,
          file,
          currentRowVersion
        );
        setContext(fresh);
        setCurrentRowVersion(fresh.row_version);
      } catch {
        setConflictMessage("Failed to add document.");
      }
    },
    [applicationId, currentRowVersion]
  );

  const handleReplaceDocument = useCallback(
    async (docId: string, file: File) => {
      try {
        const fresh = await replaceResubmissionDocument(
          applicationId,
          docId,
          file,
          currentRowVersion
        );
        setContext(fresh);
        setCurrentRowVersion(fresh.row_version);
      } catch {
        setConflictMessage("Failed to replace document.");
      }
    },
    [applicationId, currentRowVersion]
  );

  const handleRemoveDocument = useCallback(
    async (docId: string) => {
      try {
        const fresh = await removeResubmissionDocument(
          applicationId,
          docId,
          currentRowVersion
        );
        setContext(fresh);
        setCurrentRowVersion(fresh.row_version);
      } catch {
        setConflictMessage("Failed to remove document.");
      }
    },
    [applicationId, currentRowVersion]
  );

  // Early returns as inline content, not function returns
  const isLoading = loading || (!context && !fetchError);
  const showError = !!fetchError && !isLoading;

  return (
    <div className="space-y-6">
      {isLoading && (
        <div className="max-w-3xl mx-auto space-y-6 py-8">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-10 animate-pulse rounded bg-surface-muted" />
          ))}
        </div>
      )}

      {showError && (
        <div className="max-w-3xl mx-auto py-12 text-center">
          <p className="text-text-secondary">
            {fetchError ?? "Something went wrong."}
          </p>
          <button
            onClick={() => router.push(`/applications/${applicationId}`)}
            className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-brand-primary px-4 py-2 text-sm font-semibold text-white"
          >
            Back to tracker
          </button>
        </div>
      )}

      {!isLoading && context && (
        <>
          {/* Header */}
          <header className="flex flex-wrap items-center gap-3">
            <div className="min-w-0 flex-1">
              <p className="text-xs tracking-wide text-text-muted uppercase">
                Edit application
              </p>
              <h1 className="flex flex-wrap items-center gap-2 text-2xl font-bold text-text-primary">
                {reference}
                {context.submission_cycle > 1 && (
                  <span className="inline-flex items-center rounded-full bg-surface-muted px-3 py-1 text-xs font-semibold text-text-secondary">
                    Resubmission #{context.submission_cycle - 1}
                  </span>
                )}
              </h1>
              <p className="mt-1 text-sm text-text-secondary">{status}</p>
            </div>
            <StatusBadge status={status as TrackingStatus} />
          </header>

          {/* Approver feedback card */}
          <ApproverFeedbackCard feedback={feedback} />

          {/* Conflict / version banner */}
          {conflictMessage && (
            <div
              role="alert"
              className="rounded-lg border border-border-error bg-status-rejected-subtle p-4 text-sm text-status-rejected"
            >
              {conflictMessage}
            </div>
          )}

          {/* Main layout */}
          <div className="lg:flex lg:flex-row-reverse gap-6">
            {/* Left column — form */}
            <div className="space-y-6 lg:w-2/3">
              {/* Returns-to note */}
              {returnsTo && (
                <p className="rounded-lg bg-surface-subtle px-4 py-3 text-sm text-text-secondary">
                  After you resubmit, this application returns to{" "}
                  <strong className="font-medium text-text-primary">
                    {returnsTo.role_label}
                  </strong>{" "}
                  — {returnsTo.approver_name}. Earlier approvals are kept.
                </p>
              )}

              {/* Validation errors panel */}
              <ValidationErrorsPanel issues={validationIssues} />

              {/* Resubmission form */}
              {content && (
                <ResubmissionForm
                  applicationId={applicationId}
                  content={content}
                  onChange={handleFieldChange}
                />
              )}

              {/* Supporting documents */}
              <ResubmissionDocuments
                documents={context.documents.active}
                retired={context.documents.retired}
                busy={busy}
                onAdd={handleAddDocument}
                onReplace={handleReplaceDocument}
                onRemove={handleRemoveDocument}
              />
            </div>
          </div>

          {/* Footer actions */}
          <footer className="border-t border-border-default pt-6 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
            <button
              onClick={() => router.push(`/applications/${applicationId}`)}
              disabled={busy}
              className="inline-flex min-h-11 items-center justify-center rounded-lg border border-border-default px-4 py-2 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary disabled:cursor-not-allowed disabled:opacity-50"
            >
              Cancel
            </button>

            <div className="flex items-center gap-3">
              <button
                onClick={handleSave}
                disabled={busy || !dirty}
                className="inline-flex min-h-11 items-center justify-center rounded-lg border border-border-default px-4 py-2 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary disabled:cursor-not-allowed disabled:opacity-50"
              >
                Save changes
              </button>
              <button
                onClick={() => setDialogOpen(true)}
                disabled={busy}
                className="inline-flex min-h-11 items-center justify-center rounded-lg bg-brand-primary px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-brand-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {busy ? "Resubmitting…" : "Resubmit"}
              </button>
            </div>
          </footer>

          {/* Resubmit confirmation dialog */}
          <ResubmitConfirmDialog
            open={dialogOpen}
            context={context}
            busy={busy}
            conflictMessage={conflictMessage}
            onConfirm={handleResubmit}
            onClose={() => setDialogOpen(false)}
          />
        </>
      )}
    </div>
  );
}