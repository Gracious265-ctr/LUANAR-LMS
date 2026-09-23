/** Unit 17 resubmission API payload types (mirror of the backend serializers). */

export type ResubmissionStatus =
  | "draft"
  | "pending"
  | "rejected"
  | "correction_required"
  | "approved"
  | "cancelled";

export type DecisionAction =
  | "approve"
  | "reject"
  | "return_for_correction";

export interface ResubmissionFeedback {
  action: "reject" | "return_for_correction";
  role_label: string;
  approver_name: string;
  comment: string;
  decided_at: string | null;
}

export interface ReturnsTo {
  role_label: string;
  approver_name: string;
}

export interface ResubmissionContent {
  leave_type_id: number | null;
  leave_type_name: string;
  start_date: string | null;
  end_date: string | null;
  working_days: number | null;
  reason: string;
}

export interface ActiveDocument {
  id: string;
  name: string;
  size_bytes: number;
  uploaded_at: string | null;
}

export interface RetiredDocument {
  id: string;
  name: string;
  retired_at: string | null;
  retire_reason: "replaced" | "removed" | null;
  replaced_by_name: string | null;
}

export interface ChangeField {
  field: string;
  label: string;
  before: unknown;
  after: unknown;
}

export interface ChangeDocuments {
  added: { name: string }[];
  removed: { name: string }[];
  replaced: { old_name: string; new_name: string }[];
}

export interface ChangesPreview {
  has_changes: boolean;
  fields: ChangeField[];
  documents: ChangeDocuments;
}

export interface ResubmissionContext {
  id: string;
  reference: string;
  status: ResubmissionStatus;
  submission_cycle: number;
  row_version: number;
  can_edit: boolean;
  feedback: ResubmissionFeedback | null;
  returns_to: ReturnsTo | null;
  content: ResubmissionContent;
  documents: {
    active: ActiveDocument[];
    retired: RetiredDocument[];
  };
  changes_preview: ChangesPreview;
}

export interface ResubmittedApplication {
  id: string;
  reference: string;
  status: ResubmissionStatus;
  submission_cycle: number;
}

/** Validation failures returned by save/resubmit as ``{code, errors: [...]}``. */
export interface ResubmissionValidationIssue {
  code: string;
  field: string;
  message: string;
  detail?: string;
}

export interface ResubmissionValidationBody {
  code: "validation_failed";
  errors: ResubmissionValidationIssue[];
}

export interface ResubmissionConflictBody {
  code:
    | "not_editable"
    | "not_resubmittable"
    | "version_conflict"
    | "approver_unavailable"
    | "workflow_inconsistent";
  detail: string;
}