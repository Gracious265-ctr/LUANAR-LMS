"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  CalendarDays,
  FileText,
  Upload,
  CheckCircle2,
} from "lucide-react";

import {
  type LeaveApplication,
  submitLeaveApplication,
} from "@/lib/leave-api";

interface ReviewSummaryProps {
  application: LeaveApplication;
  leaveTypeName: string;
}

export function ReviewSummary({ application, leaveTypeName }: ReviewSummaryProps) {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [referenceNumber, setReferenceNumber] = useState("");
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const result = await submitLeaveApplication(application.id);
      setReferenceNumber(result.reference_number);
      setSubmitted(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit");
    } finally {
      setSubmitting(false);
    }
  };

  if (submitted) {
    return (
      <div className="bg-surface-card rounded-xl border border-border-success shadow-subtle p-8 text-center">
        <CheckCircle2 className="h-16 w-16 mx-auto text-brand-secondary mb-4" />
        <h2 className="text-2xl font-bold text-text-primary mb-2">
          Application Submitted
        </h2>
        <p className="text-text-secondary mb-4">
          Your leave application has been submitted successfully.
        </p>
        <div className="inline-block bg-surface-muted rounded-lg px-4 py-2 mb-6">
          <span className="text-xs text-text-muted block">Reference Number</span>
          <span className="text-lg font-mono font-bold text-text-primary">
            {referenceNumber}
          </span>
        </div>
        <div>
          <Link
            href="/dashboard/leave/drafts"
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md bg-button-primary text-button-primary-foreground font-medium text-sm hover:bg-button-primary-hover transition-colors"
          >
            Back to Applications
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="bg-surface-card rounded-xl border border-border-default shadow-subtle p-6">
        <div className="mb-4">
          <h2 className="text-xl font-bold text-text-primary">
            Review Application
          </h2>
        </div>

        <div className="space-y-4">
          <ReviewSection
            icon={<FileText className="h-4 w-4" />}
            label="Leave Type"
            value={leaveTypeName}
            editHref={`/dashboard/leave/${application.id}/edit`}
          />
          <ReviewSection
            icon={<CalendarDays className="h-4 w-4" />}
            label="Dates"
            value={
              application.start_date && application.end_date
                ? `${application.start_date} to ${application.end_date}`
                : "Not set"
            }
            editHref={`/dashboard/leave/${application.id}/edit`}
          />
          <ReviewSection
            icon={<CalendarDays className="h-4 w-4" />}
            label="Working Days"
            value={application.calculated_days?.toString() ?? "—"}
          />
          <ReviewSection
            icon={<FileText className="h-4 w-4" />}
            label="Reason"
            value={application.reason || "Not provided"}
            editHref={`/dashboard/leave/${application.id}/edit`}
          />
        </div>
      </div>

      {application.documents.length > 0 && (
        <div className="bg-surface-card rounded-xl border border-border-default shadow-subtle p-6">
          <h3 className="text-lg font-semibold text-text-primary mb-3">
            Supporting Documents
          </h3>
          <div className="space-y-2">
            {application.documents.map((doc) => (
              <div
                key={doc.id}
                className="flex items-center gap-3 rounded-lg border border-border-default bg-surface-muted p-3"
              >
                <Upload className="h-4 w-4 text-text-muted" />
                <span className="text-sm text-text-primary">{doc.file_name}</span>
                <span className="text-xs text-text-muted ml-auto">
                  {(doc.file_size / 1024).toFixed(1)} KB
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-border-error bg-status-rejected-subtle p-4 text-sm text-status-rejected">
          {error}
        </div>
      )}

      <div className="flex justify-end">
        <button
          onClick={handleSubmit}
          disabled={submitting}
          className="px-6 py-2.5 rounded-md bg-brand-secondary text-brand-secondary-foreground font-medium text-sm hover:bg-brand-secondary-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {submitting ? "Submitting..." : "Submit Application"}
        </button>
      </div>
    </div>
  );
}

function ReviewSection({
  icon,
  label,
  value,
  editHref,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  editHref?: string;
}) {
  return (
    <div className="flex items-start justify-between py-3 border-b border-border-subtle last:border-0">
      <div className="flex items-center gap-2 text-text-secondary">
        {icon}
        <span className="text-sm font-medium">{label}</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-sm text-text-primary">{value}</span>
        {editHref && (
          <Link
            href={editHref}
            className="text-xs text-text-link hover:text-text-link-hover"
          >
            Edit
          </Link>
        )}
      </div>
    </div>
  );
}
