"use client";

import Link from "next/link";
import { CalendarDays, FileText, Pencil, Upload } from "lucide-react";

import type { ValidationResult } from "@/lib/leave-validation";
import type { LeaveApplication } from "@/lib/leave-api";

interface LeaveReviewSummaryProps {
  application: LeaveApplication;
  leaveTypeName: string;
  validation: ValidationResult | null;
}

/**
 * Summary card for the review screen. Working days come from the server's
 * validation result (never recomputed client-side).
 */
export function LeaveReviewSummary({
  application,
  leaveTypeName,
  validation,
}: LeaveReviewSummaryProps) {
  const workingDays = validation?.working_days ?? application.calculated_days;
  const calendarDays = validation?.calendar_days;
  const financialYear = validation?.financial_year;

  return (
    <div className="bg-surface-card rounded-xl border border-border-default shadow-subtle p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-bold text-text-primary">Summary</h2>
        <Link
          href={`/dashboard/leave/${application.id}/edit`}
          className="inline-flex items-center gap-1.5 text-xs font-medium text-text-link hover:text-text-link-hover"
        >
          <Pencil className="h-3.5 w-3.5" />
          Edit
        </Link>
      </div>

      <div className="space-y-0 divide-y divide-border-subtle">
        <Row
          icon={<FileText className="h-4 w-4" />}
          label="Leave type"
          value={leaveTypeName}
        />
        <Row
          icon={<CalendarDays className="h-4 w-4" />}
          label="Dates"
          value={
            application.start_date && application.end_date
              ? `${application.start_date} to ${application.end_date}`
              : "Not set"
          }
        />
        <Row
          icon={<CalendarDays className="h-4 w-4" />}
          label="Working days"
          value={workingDays !== null && workingDays !== undefined ? String(workingDays) : "—"}
          emphasis
        />
        <Row
          icon={<CalendarDays className="h-4 w-4" />}
          label="Calendar days"
          value={calendarDays !== null && calendarDays !== undefined ? String(calendarDays) : "—"}
        />
        <Row
          icon={<CalendarDays className="h-4 w-4" />}
          label="Financial year"
          value={financialYear || "—"}
        />
        <Row
          icon={<FileText className="h-4 w-4" />}
          label="Reason"
          value={application.reason || "Not provided"}
          multiline
        />
      </div>

      {application.documents.length > 0 && (
        <div className="mt-5">
          <p className="text-xs font-medium text-text-muted uppercase mb-2">
            Attached documents
          </p>
          <ul className="space-y-1.5">
            {application.documents.map((doc) => (
              <li
                key={doc.id}
                className="flex items-center gap-2 text-sm text-text-primary"
              >
                <Upload className="h-3.5 w-3.5 text-text-muted" />
                {doc.file_name}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function Row({
  icon,
  label,
  value,
  emphasis,
  multiline,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  emphasis?: boolean;
  multiline?: boolean;
}) {
  return (
    <div className="flex items-start justify-between gap-4 py-3">
      <div className="flex items-center gap-2 text-text-secondary shrink-0">
        {icon}
        <span className="text-sm font-medium">{label}</span>
      </div>
      <span
        className={`text-sm text-text-primary text-right ${
          emphasis ? "text-lg font-bold" : multiline ? "whitespace-pre-wrap" : ""
        }`}
      >
        {value}
      </span>
    </div>
  );
}