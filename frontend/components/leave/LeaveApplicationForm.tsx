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
import { getLeaveTypes, type LeaveType } from "@/lib/services/leaveTypes";
import { getLeaveFormDefaults } from "@/lib/services/leaveFormDefaults";
import { formatDateRange } from "@/lib/date";
import { useAutosaveDraft } from "@/lib/hooks/useAutosaveDraft";
import { useLeaveValidation } from "@/lib/hooks/useLeaveValidation";
import { LeaveTypeSelect } from "./LeaveTypeSelect";
import { DateRangeFields } from "./DateRangeFields";
import { WorkingDaysPreview } from "./WorkingDaysPreview";
import { SupportingDocumentsUploader } from "./SupportingDocumentsUploader";
import { Stepper, type Step, type StepStatus } from "@/components/ui/Stepper";
import { Textarea } from "@/components/ui/textarea";
import { Field } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";
import { Card } from "@/components/ui/card";
import { pushToast } from "@/components/ui/toast";

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

const READ_ONLY_STATUSES = ["submitted", "approved", "cancelled"];

/** The wizard's four steps (spec 04 §3.4). The documents step is skipped when
 * the selected type needs no documents and none are attached. */
const STEP_DEFS = [
  { id: "dates", label: "Dates & leave type" },
  { id: "reason", label: "Reason & details" },
  { id: "documents", label: "Supporting documents" },
  { id: "review", label: "Review & submit" },
] as const;

const DOCUMENTS_STEP_INDEX = 2;
const REVIEW_STEP_INDEX = 3;

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
  const [status, setStatus] = useState<string | null>(null);
  const [documents, setDocuments] = useState<SupportingDocument[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [initialLoaded, setInitialLoaded] = useState(
    () => !(mode === "edit" && applicationId)
  );
  const [currentId, setCurrentId] = useState<string | null>(
    mode === "edit" ? (applicationId ?? null) : null
  );
  const [calculatedDays, setCalculatedDays] = useState<number | null>(null);
  const [stepIndex, setStepIndex] = useState(0);
  const [leaveTypes, setLeaveTypes] = useState<LeaveType[]>([]);
  const [typesLoading, setTypesLoading] = useState(true);
  const [typesError, setTypesError] = useState<string | null>(null);

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

  // Save failures are the one autosave event worth interrupting the user for
  // (spec 04 §3.5); success stays silent in the status line below.
  useEffect(() => {
    if (saveStatus === "error") {
      pushToast(
        "Could not save your draft. Check your connection and try again.",
        "error"
      );
    }
  }, [saveStatus]);

  useEffect(() => {
    let cancelled = false;
    getLeaveTypes()
      .then((data) => {
        if (cancelled) return;
        setLeaveTypes(data);
        setTypesError(null);
      })
      .catch(() => {
        if (!cancelled) setTypesError("Unable to load leave types.");
      })
      .finally(() => {
        if (!cancelled) setTypesLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Smart defaults (spec 04 §3.6): a brand-new application warm-starts from the
  // employee's most-recent type and the next working day. An edit never
  // overwrites what the draft already holds.
  useEffect(() => {
    if (mode !== "create" || applicationId) return;
    let cancelled = false;
    getLeaveFormDefaults()
      .then((defaults) => {
        if (cancelled) return;
        if (defaults.last_leave_type_id !== null) {
          setLeaveTypeId(defaults.last_leave_type_id);
        }
        if (defaults.default_start_date) {
          setStartDate(defaults.default_start_date);
        }
      })
      .catch(() => {
        // Advisory only — a failure leaves the form at its blank defaults.
      });
    return () => {
      cancelled = true;
    };
  }, [mode, applicationId]);

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

  const selectedType = useMemo(
    () => leaveTypes.find((t) => t.id === leaveTypeId) ?? null,
    [leaveTypes, leaveTypeId]
  );
  const documentsStepVisible =
    Boolean(selectedType?.requiresDocuments) || documents.length > 0;

  const statusFor = (index: number): StepStatus => {
    if (index === DOCUMENTS_STEP_INDEX && !documentsStepVisible) return "skipped";
    if (index < stepIndex) return "completed";
    if (index === stepIndex) return "current";
    return "pending";
  };

  const canAdvance = (index: number): boolean => {
    if (index === 0) {
      const hasDatesError = Boolean(startError || endError || leaveTypeError);
      return (
        leaveTypeId !== null &&
        Boolean(startDate) &&
        Boolean(endDate) &&
        !hasDatesError
      );
    }
    if (index === 1) {
      return reason.trim().length > 0 && !reasonError;
    }
    if (index === DOCUMENTS_STEP_INDEX) {
      return !selectedType?.requiresDocuments || documents.length > 0;
    }
    return true;
  };

  const goNext = () => {
    let next = stepIndex + 1;
    if (next === DOCUMENTS_STEP_INDEX && !documentsStepVisible) {
      next = REVIEW_STEP_INDEX;
    }
    setStepIndex(Math.min(next, REVIEW_STEP_INDEX));
  };

  const goBack = () => {
    let prev = stepIndex - 1;
    if (prev === DOCUMENTS_STEP_INDEX && !documentsStepVisible) {
      prev = 1;
    }
    setStepIndex(Math.max(prev, 0));
  };

  const goTo = (index: number) => {
    const state = statusFor(index);
    if (state === "completed" || state === "current") setStepIndex(index);
  };

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

  const handleContinue = () => {
    if (!currentId) return;
    if (onContinueToReview) {
      flush();
      onContinueToReview(currentId);
    } else {
      router.push(`/leave/${currentId}/review`);
    }
  };

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
          href="/leave"
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md bg-button-primary text-button-primary-foreground font-medium text-sm hover:bg-button-primary-hover transition-colors"
        >
          Back to Applications
        </Link>
      </Card>
    );
  }

  const stepperSteps: Step[] = STEP_DEFS.map((def, index) => ({
    id: def.id,
    label: def.label,
    status: statusFor(index),
  }));

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

      <Stepper
        steps={stepperSteps}
        orientation="horizontal"
        size="sm"
        showAvatars={false}
        onStepClick={(step) => {
          const index = STEP_DEFS.findIndex((def) => def.id === step.id);
          if (index >= 0) goTo(index);
        }}
        isStepClickable={(step) =>
          step.status === "completed" || step.status === "current"
        }
        stepAriaLabel={(step) => `Go to ${step.label}`}
      />

      {stepIndex === 0 && (
        <Card>
          <h3 className="text-lg font-semibold text-text-primary mb-4">
            Dates & leave type
          </h3>
          <div className="space-y-4">
            {leaveTypeError && (
              <FieldError message={leaveTypeError} id="leave-type-error" />
            )}
            <LeaveTypeSelect
              value={leaveTypeId}
              onChange={(v) => handleFieldChange("leave_type_id", v)}
              types={leaveTypes}
              loading={typesLoading}
              error={typesError}
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
          </div>
        </Card>
      )}

      {stepIndex === 1 && (
        <Card>
          <h3 className="text-lg font-semibold text-text-primary mb-4">
            Reason & details
          </h3>
          <div className="space-y-4">
            <Field label="Reason" htmlFor="reason">
              <Textarea
                id="reason"
                className="resize-none"
                value={reason}
                onChange={(e) => handleFieldChange("reason", e.target.value)}
                rows={4}
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
      )}

      {stepIndex === DOCUMENTS_STEP_INDEX && (
        <Card>
          <h3 className="text-lg font-semibold text-text-primary mb-4">
            Supporting documents
          </h3>
          <SupportingDocumentsUploader
            applicationId={currentId}
            documents={documents}
            editable={
              mode === "create" ||
              status === "draft" ||
              status === "rejected"
            }
            canReplace={status === "rejected"}
            onDocumentsChange={setDocuments}
            onEnsureDraft={ensureDraftCreated}
          />
        </Card>
      )}

      {stepIndex === REVIEW_STEP_INDEX && (
        <Card>
          <h3 className="text-lg font-semibold text-text-primary mb-4">
            Review & submit
          </h3>
          <dl className="space-y-3 text-sm">
            <ReviewRow
              label="Leave type"
              value={selectedType?.name ?? "—"}
            />
            <ReviewRow
              label="Dates"
              value={formatDateRange(startDate, endDate) || "—"}
            />
            <ReviewRow
              label="Working days"
              value={
                startDate && endDate
                  ? String(validation.result?.working_days ?? calculatedDays ?? "—")
                  : "—"
              }
            />
            <ReviewRow label="Reason" value={reason || "—"} />
            <ReviewRow
              label="Supporting documents"
              value={
                documents.length > 0
                  ? `${documents.length} attached`
                  : selectedType?.requiresDocuments
                    ? "Required"
                    : "None required"
              }
            />
          </dl>
        </Card>
      )}

      {!hideActions && (
        <div className="flex items-center justify-between gap-3">
          <div>
            {stepIndex > 0 && (
              <Button type="button" variant="secondary" onClick={goBack}>
                Back
              </Button>
            )}
          </div>
          <div className="flex items-center gap-3">
            {saveStatus !== "idle" && (
              <span className="text-sm text-text-muted">
                {saveStatus === "saving" && "Saving..."}
                {saveStatus === "saved" && "All changes saved"}
                {saveStatus === "error" && (
                  <span className="text-status-rejected">Save failed</span>
                )}
              </span>
            )}
            {stepIndex < REVIEW_STEP_INDEX ? (
              <Button
                type="button"
                onClick={goNext}
                disabled={!canAdvance(stepIndex)}
              >
                Next
              </Button>
            ) : (
              <Button type="button" onClick={handleContinue} disabled={!currentId}>
                Review Application
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  );
});

function ReviewRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-text-secondary">{label}</dt>
      <dd className="text-right font-medium text-text-primary">{value}</dd>
    </div>
  );
}

function FieldError({ message, id }: { message: string; id: string }) {
  return (
    <p id={id} role="alert" className="text-sm text-status-rejected">
      {message}
    </p>
  );
}
