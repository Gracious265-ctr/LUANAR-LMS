"use client";

import { useEffect, useState } from "react";

import {
  type ValidationResult,
  validateLeave,
} from "@/lib/leave-validation";

export interface LeaveValidationInput {
  leave_type_id: number | null;
  start_date: string | null;
  end_date: string | null;
  draft_id?: string | null;
  application_id?: string | null;
}

export interface UseLeaveValidationOptions {
  /** Debounce delay in ms. Defaults to 400. */
  debounceMs?: number;
  /** When false the hook never fires (e.g. nothing to validate yet). */
  enabled?: boolean;
}

/**
 * Runs the backend validation pipeline with a 400 ms debounce and cancels
 * stale requests via `AbortController`, exposing `{ result, isLoading, error }`.
 */
export function useLeaveValidation(
  input: LeaveValidationInput,
  options: UseLeaveValidationOptions = {}
) {
  const { debounceMs = 400, enabled = true } = options;
  const [result, setResult] = useState<ValidationResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const hasRequiredFields =
    input.leave_type_id !== null &&
    input.leave_type_id !== undefined &&
    Boolean(input.start_date) &&
    Boolean(input.end_date);

  useEffect(() => {
    const controller = new AbortController();
    const debounceTimer = setTimeout(() => {
      if (!enabled || !hasRequiredFields) {
        setResult(null);
        setError(null);
        setIsLoading(false);
        return;
      }

      validateLeave(
        {
          leave_type_id: input.leave_type_id,
          start_date: input.start_date,
          end_date: input.end_date,
          draft_id: input.draft_id ?? null,
          application_id: input.application_id ?? null,
        },
        controller.signal
      )
        .then((validation) => {
          setResult(validation);
          setError(null);
          setIsLoading(false);
        })
        .catch((err: unknown) => {
          setResult(null);
          setError(
            err instanceof Error && err.name === "AbortError"
              ? null
              : "Validation is temporarily unavailable. Please try again."
          );
          setIsLoading(false);
        });
      setIsLoading(true);
    }, debounceMs);

    return () => {
      clearTimeout(debounceTimer);
      controller.abort();
    };
  }, [
    input.leave_type_id,
    input.start_date,
    input.end_date,
    input.draft_id,
    input.application_id,
    debounceMs,
    enabled,
    hasRequiredFields,
  ]);

  return { result, isLoading, error };
}