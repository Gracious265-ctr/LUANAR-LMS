"use client";

import { useCallback, useRef, useState } from "react";

import {
  type ValidationIssue,
  submitApplication,
  SubmitError,
} from "@/lib/leave-validation";
import { pushToast } from "@/components/ui/toast";

export interface SubmitFailure {
  message: string;
}

export interface UseSubmitLeaveApplicationOptions {
  /** Called after a successful submit. */
  onSubmitted: () => void;
  /**
   * Called when the server reports the application was already submitted
   * (HTTP 409). Treated as a success state by the caller.
   */
  onAlreadySubmitted: () => void;
}

export interface UseSubmitLeaveApplicationResult {
  submit: (applicationId: string, options?: { resubmit?: boolean }) => Promise<void>;
  isSubmitting: boolean;
  /** Issues surfaced by a 422 response, to be rendered above the form. */
  issues: ValidationIssue[];
  /** Non-validation failure, e.g. a network error. */
  failure: SubmitFailure | null;
  dismissIssues: () => void;
  dismissFailure: () => void;
}

/**
 * Owns the submit transition for a leave application.
 *
 * The review screen and the compose overlay both need identical submit
 * behaviour, including the two outcomes that are easy to get wrong: a 422
 * returns per-field issues that must surface without losing the user's place,
 * and a 409 means the application is already submitted, which is a success
 * state rather than an error. Keeping that in one hook stops the two callers
 * from drifting.
 *
 * A rejected application is edited and then *resubmitted* (`options.resubmit`),
 * which hits the resubmit endpoint rather than submit — the backend only
 * accepts the submit endpoint for drafts.
 */
export function useSubmitLeaveApplication({
  onSubmitted,
  onAlreadySubmitted,
}: UseSubmitLeaveApplicationOptions): UseSubmitLeaveApplicationResult {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [issues, setIssues] = useState<ValidationIssue[]>([]);
  const [failure, setFailure] = useState<SubmitFailure | null>(null);
  const inFlightRef = useRef(false);

  const submit = useCallback(
    async (applicationId: string, options?: { resubmit?: boolean }) => {
      if (inFlightRef.current) return;
      inFlightRef.current = true;
      setIsSubmitting(true);
      setFailure(null);
      setIssues([]);
      try {
        await submitApplication(applicationId, options);
        // Fired before the caller so the confirmation is queued even if the
        // callback navigates away from the screen that triggered it.
        pushToast(
          options?.resubmit ? "Application resubmitted." : "Application submitted."
        );
        onSubmitted();
      } catch (error) {
        if (error instanceof SubmitError) {
          if (error.status === 422) {
            // No toast here: every issue lands inline above the form, and a
            // duplicate would drown the specific field the user must fix.
            setIssues(error.errors);
          } else if (error.status === 409 && error.code === "ALREADY_SUBMITTED") {
            pushToast("This application was already submitted.");
            onAlreadySubmitted();
          } else {
            setFailure({ message: error.message });
            pushToast(error.message, "error");
          }
        } else {
          const message =
            error instanceof Error
              ? error.message
              : "Failed to submit application";
          setFailure({ message });
          pushToast(message, "error");
        }
      } finally {
        inFlightRef.current = false;
        setIsSubmitting(false);
      }
    },
    [onSubmitted, onAlreadySubmitted]
  );

  const dismissIssues = useCallback(() => setIssues([]), []);
  const dismissFailure = useCallback(() => setFailure(null), []);

  return {
    submit,
    isSubmitting,
    issues,
    failure,
    dismissIssues,
    dismissFailure,
  };
}
