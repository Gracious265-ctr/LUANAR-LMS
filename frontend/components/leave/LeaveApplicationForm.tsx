"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { createLeaveApplication } from "@/lib/leave-api";
import { useAutosaveDraft } from "@/lib/hooks/useAutosaveDraft";
import { previewWorkingDays } from "@/lib/services/calendarRules";
import { LeaveTypeSelect } from "./LeaveTypeSelect";
import { DateRangeFields } from "./DateRangeFields";
import { WorkingDaysPreview } from "./WorkingDaysPreview";
import { SupportingDocumentsUploader } from "./SupportingDocumentsUploader";

interface LeaveApplicationFormProps {
  mode: "create" | "edit";
  applicationId?: string;
}

export function LeaveApplicationForm({
  mode,
  applicationId,
}: LeaveApplicationFormProps) {
  const router = useRouter();
  const [leaveTypeId, setLeaveTypeId] = useState<number | null>(null);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [reason, setReason] = useState("");
  const [documents, setDocuments] = useState<
    { id: string; file_name: string; file_size: number; file_path: string; file_url: string; content_type: string; uploaded_at: string }[]
  >([]);
  const [workingDays, setWorkingDays] = useState<number | null>(null);
  const [daysLoading, setDaysLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [initialLoaded, setInitialLoaded] = useState(
    () => !(mode === "edit" && applicationId)
  );
  const [currentId, setCurrentId] = useState<string | null>(
    mode === "edit" ? (applicationId ?? null) : null
  );

  const formData = useMemo(
    () => ({
      leave_type_id: leaveTypeId,
      start_date: startDate || null,
      end_date: endDate || null,
      reason,
    }),
    [leaveTypeId, startDate, endDate, reason]
  );

  const { saveStatus } = useAutosaveDraft(currentId, formData);

  useEffect(() => {
    if (!(mode === "edit" && applicationId)) return;
    const fetchApp = async () => {
      try {
        const res = await fetch(`/api/leave/leave-applications/${applicationId}/`, {
          credentials: "include",
        });
        if (res.ok) {
          const data = await res.json();
          if (data.status === "submitted") {
            setSubmitted(true);
            return;
          }
          setLeaveTypeId(data.leave_type_id);
          setStartDate(data.start_date || "");
          setEndDate(data.end_date || "");
          setReason(data.reason || "");
          setDocuments(data.documents || []);
          setWorkingDays(data.calculated_days);
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

  useEffect(() => {
    if (!startDate || !endDate) return;
    let cancelled = false;
    previewWorkingDays(startDate, endDate)
      .then((res) => {
        if (cancelled) return;
        setWorkingDays(res.days);
        setDaysLoading(false);
      })
      .catch(() => {
        if (cancelled) return;
        setWorkingDays(null);
        setDaysLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [startDate, endDate]);

  const displayedWorkingDays = startDate && endDate ? workingDays : null;

  const ensureDraftCreated = useCallback(async (patch: Record<string, unknown> = {}) => {
    if (currentId) return currentId;
    try {
      const app = await createLeaveApplication(patch);
      setCurrentId(app.id);
      setCreateError(null);
      return app.id;
    } catch {
      setCreateError(
        "Could not start your application. Check your connection and try again."
      );
      return null;
    }
  }, [currentId]);

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
      <div className="bg-surface-card rounded-xl border border-border-default shadow-subtle p-8 text-center">
        <div className="text-lg font-semibold text-text-primary mb-2">
          Application Already Submitted
        </div>
        <p className="text-sm text-text-secondary mb-6">
          This leave application has been submitted and can no longer be edited.
          View its current details in your applications list.
        </p>
        <Link
          href="/dashboard/leave/drafts"
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md bg-button-primary text-button-primary-foreground font-medium text-sm hover:bg-button-primary-hover transition-colors"
        >
          Back to Applications
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {loadError && (
        <div
          role="alert"
          className="rounded-lg border border-border-error bg-status-rejected-subtle p-4 text-sm text-status-rejected"
        >
          {loadError}
        </div>
      )}

      {createError && (
        <div
          role="alert"
          className="rounded-lg border border-border-error bg-status-rejected-subtle p-4 text-sm text-status-rejected"
        >
          {createError}
        </div>
      )}

      <div className="bg-surface-card rounded-xl border border-border-default shadow-subtle p-6">
        <h3 className="text-lg font-semibold text-text-primary mb-4">
          Leave Details
        </h3>
        <div className="space-y-4">
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
          <WorkingDaysPreview days={displayedWorkingDays} loading={daysLoading} />
          <div>
            <label
              htmlFor="leave-reason"
              className="block text-sm font-medium text-text-secondary mb-1.5"
            >
              Reason
            </label>
            <textarea
              id="leave-reason"
              value={reason}
              onChange={(e) => handleFieldChange("reason", e.target.value)}
              rows={3}
              placeholder="Provide a reason for your leave application..."
              className="w-full rounded-md border border-input-border bg-input-background px-3 py-2 text-sm text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-1 focus:ring-input-ring-focus resize-none"
            />
          </div>
        </div>
      </div>

      <div className="bg-surface-card rounded-xl border border-border-default shadow-subtle p-6">
        <SupportingDocumentsUploader
          applicationId={currentId}
          documents={documents}
          onDocumentsChange={setDocuments}
          onEnsureDraft={ensureDraftCreated}
        />
      </div>

      {saveStatus !== "idle" && (
        <div className="text-sm text-text-muted">
          {saveStatus === "saving" && "Saving..."}
          {saveStatus === "saved" && "All changes saved"}
          {saveStatus === "error" && (
            <span className="text-status-rejected">Save failed</span>
          )}
        </div>
      )}

      <div className="flex justify-end">
        <button
          onClick={() =>
            currentId
              ? router.push(`/dashboard/leave/${currentId}/review`)
              : undefined
          }
          disabled={!currentId}
          className="px-4 py-2 rounded-md bg-button-primary text-button-primary-foreground font-medium text-sm hover:bg-button-primary-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          Review Application
        </button>
      </div>
    </div>
  );
}
