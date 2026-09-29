"use client";

import { useState } from "react";
import Link from "next/link";
import { Check, CheckCircle2, Copy } from "lucide-react";

import { Button } from "@/components/ui/button";
import type {
  SubmittedApplication,
  ValidationResult,
} from "@/lib/leave-validation";

interface SubmissionConfirmationProps {
  application: SubmittedApplication;
  leaveTypeName?: string;
  validation?: ValidationResult | null;
}

function formatDateRange(start: string | null, end: string | null): string {
  if (!start || !end) return "—";
  return `${start} to ${end}`;
}

function formatTimestamp(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function SubmissionConfirmation({
  application,
  leaveTypeName,
}: SubmissionConfirmationProps) {
  const [copied, setCopied] = useState(false);
  const reference = application.reference_number ?? "";

  const copyReference = async () => {
    try {
      await navigator.clipboard.writeText(reference);
    } catch {
      return;
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="bg-surface-card rounded-xl border border-border-success shadow-subtle p-8 text-center">
      <CheckCircle2 className="h-16 w-16 mx-auto text-brand-secondary mb-4" />
      <h2 className="text-xl font-semibold tracking-tight text-text-primary mb-2">
        Application submitted
      </h2>
      <p className="text-text-secondary mb-6">
        Keep this reference number to track your application.
      </p>

      <div className="inline-block bg-surface-muted rounded-lg px-6 py-3 mb-6 select-all">
        <span className="text-xs text-text-muted block mb-1">
          Reference Number
        </span>
        <span className="text-xl font-mono font-semibold tracking-tight text-text-primary">
          {reference}
        </span>
        <Button
          type="button"
          onClick={copyReference}
          disabled={!reference}
          aria-label="Copy reference number"
          variant="secondary"
          size="sm"
          className="ml-3 align-middle"
        >
          {copied ? (
            <>
              <Check className="h-3.5 w-3.5 text-brand-secondary" />
              Copied
            </>
          ) : (
            <>
              <Copy className="h-3.5 w-3.5" />
              Copy
            </>
          )}
        </Button>
      </div>

      <div className="flex items-center justify-center gap-3 mb-8">
        <span className="inline-flex items-center gap-1.5 rounded-full bg-status-pending-subtle px-3 py-1 text-xs font-semibold text-status-pending">
          Submitted
        </span>
        {application.submitted_at && (
          <span className="text-xs text-text-muted">
            {formatTimestamp(application.submitted_at)}
          </span>
        )}
      </div>

      <div className="mx-auto max-w-sm text-sm text-text-secondary mb-8">
        <p>
          <span className="text-text-muted">{leaveTypeName ?? "Leave"}</span>
          {" · "}
          {formatDateRange(application.start_date, application.end_date)}
          {application.working_days !== null && (
            <>
              {" · "}
              {application.working_days} working day
              {application.working_days === 1 ? "" : "s"}
            </>
          )}
        </p>
      </div>

      <div className="flex flex-wrap items-center justify-center gap-3">
        <Link
          href="/dashboard/leave/drafts"
          className="px-4 py-2 rounded-md bg-brand-secondary text-brand-secondary-foreground font-medium text-sm hover:bg-brand-secondary-hover transition-colors"
        >
          View my applications
        </Link>
        <Link
          href={`/applications/${application.id}`}
          className="px-4 py-2 rounded-md border border-brand-primary-border bg-brand-primary-subtle text-brand-primary font-medium text-sm hover:bg-brand-primary-muted transition-colors"
        >
          Track this application
        </Link>
        <Link
          href="/dashboard"
          className="px-4 py-2 rounded-md border border-input-border bg-input-background text-text-primary font-medium text-sm hover:bg-surface-hover transition-colors"
        >
          Back to dashboard
        </Link>
      </div>
    </div>
  );
}