"use client";

import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useState,
} from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { createLeaveApplication, type SupportingDocument } from "@/lib/leave-api";
import { useAutosaveDraft } from "@/lib/hooks/useAutosaveDraft";
import { useLeaveValidation } from "@/lib/hooks/useLeaveValidation";
import { LeaveTypeSelect } from "./LeaveTypeSelect";
import { DateRangeFields } from "./DateRangeFields";
import { WorkingDaysPreview } from "./WorkingDaysPreview";
import { SupportingDocumentsUploader } from "./SupportingDocumentsUploader";
import { Textarea } from "@/components/ui/textarea";
import { Field } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";
import { Card } from "@/components/ui/card";

interface LeaveApplicationFormProps {
  mode: "create" | "edit";
  applicationId?: string;
  /**
   * Called instead of navigating when the user continues to review. The compose
   * overlay advances its own stage; the standalone pages fall back to a
   * `router.push` when this is absent.
   */
  onContinueToReview?: (draftId: string) => void;
  /** Fired once a draft exists, so the host can make the overlay deep-linkable. */
  onDraftCreated?: (draftId: string) => void;
  /** Hide the built-in action row when the host supplies its own footer. */
  hideActions?: boolean;
}

export interface LeaveApplicationFormHandle {
  /** Persist any debounced autosave immediately. */
  flush: () => void;
  /** The draft id, once one has been created. */
  getDraftId: () => string | null;
}

const READ_ONLY_STATUSES = ["submitted", "approved", "rejected", "cancelled"];

export const LeaveApplicationForm = forwardRef<
  LeaveApplicationFormHandle,
  LeaveApplicationFormProps
>(function LeaveApplicationForm(
  { mode, applicationId, onContinueToReview, onDraftCreated, hideActions },
  ref
) {
  const router = useRouter();
  const [leaveTypeId, setLeaveTypeId] = useState<number | null>(null);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [reason, setReason] = useState("");
<<<<<<< HEAD
  const [documents, setDocuments] = useState<SupportingDocument[]>([]);
=======
  const [status, setStatus] = useState<string | null>(null);
  const [documents, setDocuments] = useState<SupportingDocument[]>([]);
const [loadError, setLoadError] = useState<string | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
>>>>>>> feature/plans-teams
  const [initialLoaded, setInitialLoaded] = useState(
    () => !(mode === "edit" && applicationId)
  );
  const [currentId, setCurrentId] = useState<string | null>(
    mode === "edit" ? (applicationId ?? null) : null
  );
  const [calculatedDays, setCalculatedDays] = useState<number | null>(null);

  const formData = useMemo(
    () => ({
      leave_type_id: leaveTypeId,
      start_date: startDate || null,
      end_date: endDate || null,
      reason,
    }),
    [leaveTypeId, startDate, endDate, reason]
  );

  const { saveStatus, flush } = useAutosaveDraft(
    currentId,
    formData,
    800,
    (saved) => setCalculatedDays(saved.calculated_days ?? null)
  );

  useImperativeHandle(
    ref,
    () => ({
      flush,
      getDraftId: () => currentId,
    }),
    [flush, currentId]
  );

  useEffect(() => {
    if (!(mode === "edit" && applicationId)) return;
    const fetchApp = async () => {
      try {
        const res = await fetch(`/api/leave/leave-applications/${applicationId}/`, {
          credentials: "include",
        });
        if (res.ok) {
          const data = await res.json();
          if (READ_ONLY_STATUSES.includes(data.status)) {
            setSubmitted(true);
            return;
          }
          setStatus(data.status);
          setLeaveTypeId(data.leave_type_id);
          setStartDate(data.start_date || "");
          setEndDate(data.end_date || "");
          setReason(data.reason || "");
          setCalculatedDays(data.calculated_days ?? null);
          setDocuments(data.documents || []);
        } else {
          setLoadError("Could not load this draft. It may have been removed.");
        }
      } catch {
        setLoadError(
          "Could not load this draft. Check your connection and try again."
        );
      } finally {
        setInitialLoaded(true);
      }
    };
    fetchApp();
  }, [mode, applicationId]);

  const validation = useLeaveValidation(
    {
      leave_type_id: leaveTypeId,
      start_date: startDate || null,
      end_date: endDate || null,
      draft_id: currentId,
    },
    { enabled: Boolean(startDate && endDate) }
  );

  const errorFor = (field: string): string | null =>
    (validation.result?.errors ?? []).find((issue) => issue.field === field)
      ?.message ?? null;

  const startError = errorFor("start_date");
  const endError = errorFor("end_date");
  const leaveTypeError = errorFor("leave_type");
  const reasonError = errorFor("reason");
  const topIssues = (validation.result?.errors ?? []).filter((issue) =>
    ["documents", "—"].includes(issue.field)
  );

  const ensureDraftCreated = useCallback(
    async (patch: Record<string, unknown> = {}) => {
      if (currentId) return currentId;
      try {
        const app = await createLeaveApplication(patch);
        setCurrentId(app.id);
        setCalculatedDays(app.calculated_days ?? null);
        setCreateError(null);
        onDraftCreated?.(app.id);
        return app.id;
      } catch {
        setCreateError(
          "Could not start your application. Check your connection and try again."
        );
        return null;
      }
    },
    [currentId, onDraftCreated]
  );

  const handleFieldChange = useCallback(
    async (field: string, value: unknown) => {
      if (field === "leave_type_id") setLeaveTypeId(value as number | null);
      if (field === "start_date") setStartDate(value as string);
      if (field === "end_date") setEndDate(value as string);
      if (field === "reason") setReason(value as string);

      if (!currentId) {
        await ensureDraftCreated({ [field]: value ?? "" });
      }
    },
    [currentId, ensureDraftCreated]
  );

  if (!initialLoaded) {
    return (
      <div className="space-y-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-10 animate-pulse rounded bg-surface-muted" />
        ))}
      </div>
    );
  }

  if (submitted) {
    return (
      <Card className="text-center">
        <div className="text-lg font-semibold text-text-primary mb-2">
          Application No Longer Editable
        </div>
        <p className="text-sm text-text-secondary mb-6">
          This leave application has left the editable stage and is now a
          read-only record. View its current details in your applications list.
        </p>
        <Link
          href="/dashboard/leave/drafts"
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md bg-button-primary text-button-primary-foreground font-medium text-sm hover:bg-button-primary-hover transition-colors"
        >
          Back to Applications
        </Link>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {loadError && (
        <Alert tone="rejected" className="border border-border-error p-4">
          {loadError}
        </Alert>
      )}

      {createError && (
        <Alert tone="rejected" className="border border-border-error p-4">
          {createError}
        </Alert>
      )}

      <Card>
        <h3 className="text-lg font-semibold text-text-primary mb-4">
          Leave Details
        </h3>
        <div className="space-y-4">
          {leaveTypeError && (
            <FieldError message={leaveTypeError} id="leave-type-error" />
          )}
          <LeaveTypeSelect
            value={leaveTypeId}
            onChange={(v) => handleFieldChange("leave_type_id", v)}
          />
          <DateRangeFields
            startDate={startDate}
            endDate={endDate}
            onStartChange={(v) => handleFieldChange("start_date", v)}
            onEndChange={(v) => handleFieldChange("end_date", v)}
          />
          {startError && <FieldError message={startError} id="start-date-error" />}
          {endError && <FieldError message={endError} id="end-date-error" />}
          <WorkingDaysPreview
            days={
              startDate && endDate
                ? (validation.result?.working_days ?? calculatedDays ?? null)
                : null
            }
            loading={Boolean(startDate && endDate) && validation.isLoading}
          />
          <Field label="Reason" htmlFor="reason">
            <Textarea
              id="reason"
              className="resize-none"
              value={reason}
              onChange={(e) => handleFieldChange("reason", e.target.value)}
              rows={3}
              aria-describedby={reasonError ? "reason-error" : undefined}
              placeholder="Provide a reason for your leave application..."
            />
            {reasonError && <FieldError message={reasonError} id="reason-error" />}
          </Field>
          {topIssues.length > 0 && (
            <Alert
              tone="rejected"
              className="flex-col gap-0 border border-border-error p-3"
            >
              {topIssues.map((issue) => (
                <p key={issue.code} className="text-sm text-status-rejected">
                  {issue.message}
                </p>
              ))}
            </Alert>
          )}
        </div>
      </Card>

      <Card>
        <SupportingDocumentsUploader
          applicationId={currentId}
          documents={documents}
          editable={mode === "create" || status === "draft" || status === "correction_required"}
          canReplace={status === "correction_required"}
          onDocumentsChange={setDocuments}
          onEnsureDraft={ensureDraftCreated}
        />
      </Card>

      {saveStatus !== "idle" && (
        <div className="text-sm text-text-muted">
          {saveStatus === "saving" && "Saving..."}
          {saveStatus === "saved" && "All changes saved"}
          {saveStatus === "error" && (
            <span className="text-status-rejected">Save failed</span>
          )}
        </div>
      )}

      {!hideActions && (
        <div className="flex justify-end">
          <Button
            onClick={() => {
              if (!currentId) return;
              if (onContinueToReview) {
                flush();
                onContinueToReview(currentId);
              } else {
                router.push(`/dashboard/leave/${currentId}/review`);
              }
            }}
            disabled={!currentId}
          >
            Review Application
          </Button>
        </div>
      )}
    </div>
  );
});

function FieldError({ message, id }: { message: string; id: string }) {
  return (
    <p id={id} role="alert" className="text-sm text-status-rejected">
      {message}
    </p>
  );
}
