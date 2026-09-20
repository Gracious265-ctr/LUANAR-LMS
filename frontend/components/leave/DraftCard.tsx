"use client";

import Link from "next/link";
import { formatDistanceToNow } from "date-fns";
import { FileText, Edit3, Trash2, CheckCircle2 } from "lucide-react";
import { useState } from "react";

import { type LeaveApplication, deleteLeaveApplication } from "@/lib/leave-api";

interface DraftCardProps {
  application: LeaveApplication;
  leaveTypeName: string;
  onDelete: (id: string) => void;
}

export function DraftCard({ application, leaveTypeName, onDelete }: DraftCardProps) {
  const [deleting, setDeleting] = useState(false);
  const [confirming, setConfirming] = useState(false);

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await deleteLeaveApplication(application.id);
      onDelete(application.id);
    } catch {
      // Error handled silently
    } finally {
      setDeleting(false);
      setConfirming(false);
    }
  };

  const canReview =
    application.leave_type_id &&
    application.start_date &&
    application.end_date &&
    application.reason;

  return (
    <div className="bg-surface-card rounded-xl border border-border-default shadow-subtle p-5">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-text-muted" />
          <span className="text-sm font-medium text-text-primary">
            {leaveTypeName}
          </span>
        </div>
        <span className="text-xs text-text-muted">
          {formatDistanceToNow(new Date(application.updated_at), { addSuffix: true })}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-4 text-sm">
        <div>
          <span className="text-text-muted">Dates: </span>
          <span className="text-text-primary">
            {application.start_date && application.end_date
              ? `${application.start_date} to ${application.end_date}`
              : "Not set"}
          </span>
        </div>
        <div>
          <span className="text-text-muted">Days: </span>
          <span className="text-text-primary font-semibold">
            {application.calculated_days ?? "—"}
          </span>
        </div>
      </div>

      {application.reason && (
        <p className="text-sm text-text-secondary mb-4 line-clamp-2">
          {application.reason}
        </p>
      )}

      <div className="flex items-center gap-2">
        <Link
          href={`/dashboard/leave/${application.id}/edit`}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium bg-button-secondary hover:bg-button-secondary-hover text-text-primary border border-border-default transition-colors"
        >
          <Edit3 className="h-3.5 w-3.5" />
          Edit
        </Link>
        <Link
          href={`/dashboard/leave/${application.id}/review`}
          className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
            canReview
              ? "bg-brand-primary text-brand-primary-foreground hover:bg-brand-primary-hover"
              : "bg-surface-muted text-text-disabled cursor-not-allowed"
          }`}
          onClick={(e) => {
            if (!canReview) e.preventDefault();
          }}
          title={
            canReview
              ? "Review and submit"
              : "Complete all fields before reviewing"
          }
        >
          <CheckCircle2 className="h-3.5 w-3.5" />
          Review
        </Link>
        {confirming ? (
          <div className="flex items-center gap-1.5 ml-auto">
            <span className="text-xs text-status-rejected">Delete?</span>
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="text-xs font-medium text-status-rejected hover:underline"
            >
              {deleting ? "..." : "Yes"}
            </button>
            <button
              onClick={() => setConfirming(false)}
              className="text-xs font-medium text-text-muted hover:underline"
            >
              No
            </button>
          </div>
        ) : (
          <button
            onClick={() => setConfirming(true)}
            className="ml-auto p-1.5 rounded hover:bg-surface-hover text-text-muted hover:text-status-rejected transition-colors"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  );
}
