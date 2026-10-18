"use client";

import { formatDistanceToNow } from "date-fns";
import {
  CheckCircle2,
  Edit3,
  Eye,
  FileText,
  Trash2,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { STATUS_META } from "@/lib/tracking/labels";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";

import {
  deleteLeaveApplication,
  type LeaveApplication,
} from "@/lib/leave-api";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

interface ApplicationCardProps {
  application: LeaveApplication;
  leaveTypeName: string;
  /**
   * Optimistically removes the card from its list. Called the moment the
   * delete is confirmed, before the request is sent (spec 3.5), so the host
   * should already own the list state this mutates.
   */
  onDelete: (id: string) => void;
  /** Puts the card back when the delete fails, after the optimistic removal. */
  onRestore?: () => void;
  /**
   * Opens the compose overlay on this draft. Omitted on hosts that still link
   * to the standalone edit page, in which case the links below are rendered.
   */
  onEdit?: (applicationId: string, stage: "form" | "review") => void;
}

const CARD_STATUS_META: Record<
  LeaveApplication["status"],
  { label: string; icon: LucideIcon; badgeTone: BadgeTone }
> = {
  draft: {
    label: "Draft",
    icon: FileText,
    badgeTone: "draft",
  },
  submitted: STATUS_META.pending,
  approved: STATUS_META.approved,
  rejected: STATUS_META.rejected,
  correction_required: STATUS_META.correction_required,
  cancelled: STATUS_META.cancelled,
};

function StatusPill({ status }: { status: LeaveApplication["status"] }) {
  const meta = CARD_STATUS_META[status];
  const Icon = meta.icon;
  return (
    <Badge tone={meta.badgeTone}>
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      {meta.label}
    </Badge>
  );
}

export function ApplicationCard({
  application,
  leaveTypeName,
  onDelete,
  onRestore,
  onEdit,
}: ApplicationCardProps) {
  const [deleting, setDeleting] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { showToast } = useToast();

  const isDraft = application.status === "draft";

  const handleDelete = async () => {
    setDeleting(true);
    setError(null);
    // The row leaves the list before the round trip; in a list host this card
    // unmounts here, and the toast below is what reports either outcome.
    onDelete(application.id);
    try {
      await deleteLeaveApplication(application.id);
      showToast("Draft deleted.");
    } catch {
      onRestore?.();
      setError("Could not delete this draft. Please try again.");
      showToast("Could not delete this draft. Please try again.", "error");
      setConfirming(false);
    } finally {
      setDeleting(false);
    }
  };

  const canReview =
    application.leave_type_id &&
    application.start_date &&
    application.end_date &&
    application.reason;

  return (
    <Card>
      <div className="flex items-start justify-between mb-3">
        <div className="flex flex-wrap items-center gap-2">
          <FileText className="h-4 w-4 text-text-muted" />
          <span className="text-sm font-medium text-text-primary">
            {leaveTypeName}
          </span>
          <StatusPill status={application.status} />
        </div>
        <span className="text-xs text-text-muted whitespace-nowrap">
          {formatDistanceToNow(new Date(application.updated_at), {
            addSuffix: true,
          })}
        </span>
      </div>

      {!isDraft && application.reference_number && (
        <p className="mb-3 font-mono text-sm font-semibold text-text-primary break-words">
          {application.reference_number}
        </p>
      )}

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

      {error && (
        <p role="alert" className="text-xs text-status-rejected mt-2 mb-3">
          {error}
        </p>
      )}

      {isDraft ? (
        <div className="flex items-center gap-2">
          {onEdit ? (
            <>
              <Button
                type="button"
                onClick={() => onEdit(application.id, "form")}
                variant="secondary"
                className="h-auto gap-1.5 px-3 py-1.5 text-sm"
              >
                <Edit3 className="h-3.5 w-3.5" />
                Edit
              </Button>
              <Button
                type="button"
                onClick={() => onEdit(application.id, "review")}
                disabled={!canReview}
                title={
                  canReview
                    ? "Review and submit"
                    : "Complete all fields before reviewing"
                }
                className="h-auto gap-1.5 px-3 py-1.5 text-sm bg-brand-primary text-brand-primary-foreground hover:bg-brand-primary-hover"
              >
                <CheckCircle2 className="h-3.5 w-3.5" />
                Review
              </Button>
            </>
          ) : (
            <>
              <Link
                href={`/leave/${application.id}/edit`}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium bg-button-secondary hover:bg-button-secondary-hover text-text-primary border border-border-default transition-colors"
              >
                <Edit3 className="h-3.5 w-3.5" />
                Edit
              </Link>
              <Link
                href={`/leave/${application.id}/review`}
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
            </>
          )}
          {confirming ? (
            <div className="flex items-center gap-1.5 ml-auto">
              <span className="text-xs text-status-rejected">Delete?</span>
              <Button
                onClick={handleDelete}
                disabled={deleting}
                variant="link"
                size="sm"
                className="h-auto text-status-rejected"
              >
                {deleting ? "..." : "Yes"}
              </Button>
              <Button
                onClick={() => setConfirming(false)}
                variant="link"
                size="sm"
                className="h-auto text-text-muted"
              >
                No
              </Button>
            </div>
          ) : (
            <Button
              type="button"
              aria-label="Delete draft"
              onClick={() => setConfirming(true)}
              variant="ghost"
              size="icon"
              className="ml-auto h-auto w-auto rounded p-1.5 hover:text-status-rejected"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          )}
        </div>
      ) : (
        <div className="flex items-center gap-2">
          <Link
            href={`/leave/applications/${application.id}`}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium bg-brand-primary text-brand-primary-foreground hover:bg-brand-primary-hover transition-colors"
          >
            <Eye className="h-3.5 w-3.5" />
            Track this application
          </Link>
        </div>
      )}
    </Card>
  );
}