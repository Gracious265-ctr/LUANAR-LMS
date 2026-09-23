import type { LeaveApplication } from "@/lib/leave-api";

/** Machine-readable error codes mirroring Unit 14 Section 2.3. */
export type ValidationErrorCode =
  | "EMPLOYEE_PROFILE_MISSING"
  | "LEAVE_TYPE_UNAVAILABLE"
  | "END_BEFORE_START"
  | "START_ON_SUBMISSION_DATE"
  | "START_IN_PAST"
  | "START_NOT_WORKING_DAY"
  | "NO_WORKING_DAYS"
  | "NO_FINANCIAL_YEAR_CONFIGURED"
  | "CROSSES_FINANCIAL_YEAR"
  | "MIN_NOTICE_NOT_MET"
  | "MAX_DURATION_EXCEEDED"
  | "NOT_ELIGIBLE"
  | "ELIGIBILITY_RULE_UNSUPPORTED"
  | "ELIGIBILITY_DATA_MISSING"
  | "DOCUMENT_REQUIRED"
  | "REASON_REQUIRED"
  | "OVERLAPPING_LEAVE"
  | "INSUFFICIENT_BALANCE"
  | "ALREADY_SUBMITTED"
  | "APPLICATION_NOT_SUBMITTABLE";

export interface ValidationIssue {
  code: ValidationErrorCode;
  field: string;
  message: string;
  detail?: Record<string, unknown>;
}

export interface ValidationResult {
  valid: boolean;
  working_days: number | null;
  calendar_days: number | null;
  financial_year: string | null;
  available_balance: string | null;
  balance_after_if_approved: string | null;
  errors: ValidationIssue[];
  warnings: ValidationIssue[];
  skipped_checks: string[];
}

export interface SubmittedApplication {
  id: string;
  reference_number: string | null;
  status: string;
  submitted_at: string | null;
  working_days: number | null;
  calendar_days: number | null;
  leave_type: { id: number } & Record<string, unknown>;
  start_date: string | null;
  end_date: string | null;
}

export interface ValidateLeaveInput {
  leave_type_id: number | null;
  start_date: string | null;
  end_date: string | null;
  draft_id?: string | null;
  /** Submitted application id so overlap checks ignore the application itself. */
  application_id?: string | null;
}

/** Thrown by `submitApplication` so callers can branch on status/code. */
export class SubmitError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly body: Record<string, unknown> = {}
  ) {
    super(message);
    this.name = "SubmitError";
  }

  /** `errors` array from a `422 VALIDATION_FAILED` body. */
  get errors(): ValidationIssue[] {
    const raw = this.body.errors;
    return Array.isArray(raw) ? (raw as ValidationIssue[]) : [];
  }

  /** Existing reference from a `409 ALREADY_SUBMITTED` body. */
  get referenceNumber(): string | null {
    const ref = this.body.reference_number;
    return typeof ref === "string" ? ref : null;
  }

  get code(): string | null {
    const code = this.body.code;
    return typeof code === "string" ? code : null;
  }
}

export async function validateLeave(
  input: ValidateLeaveInput,
  signal?: AbortSignal
): Promise<ValidationResult> {
  const res = await fetch("/api/leave/validate/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    signal,
    body: JSON.stringify(input),
  });
  if (!res.ok) throw new Error("Failed to validate leave application");
  return res.json();
}

export async function submitApplication(
  id: string
): Promise<SubmittedApplication> {
  const res = await fetch(`/api/leave/leave-applications/${id}/submit/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
  });
  const body: Record<string, unknown> = await res.json().catch(() => ({}));
  if (!res.ok) {
    const message =
      typeof body.detail === "string" ? body.detail : "Failed to submit application";
    throw new SubmitError(message, res.status, body);
  }
  return body as unknown as SubmittedApplication;
}

/** Structural helper reading server-authoritative fields off an application. */
export function isSubmitted(app: LeaveApplication): boolean {
  return app.status === "submitted" && Boolean(app.reference_number);
}