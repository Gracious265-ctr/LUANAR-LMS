"use client";

import { useEffect, useState } from "react";
import { ChevronDown, FileText, ExternalLink } from "lucide-react";

import { listDocuments, type SupportingDocument } from "@/lib/leave-api";
import { formatSize } from "@/lib/approvals/format";
import { formatDateTime } from "@/lib/tracking/format";
import type { TrackingDocument } from "@/lib/tracking/types";
import { cn } from "@/lib/utils";

/**
 * Read-only supporting documents card for the tracking detail page.
 *
 * Active rows come straight from the tracking payload and link out to their
 * signed URL. Past (retired) rows are fetched from the document list endpoint
 * with ``include_retired`` and rendered collapsed under an "Archived (N)"
 * heading: replaced rows keep their signed URL (Open offered), removed rows
 * are intentionally gone and show no Open button.
 */
export function SupportingDocumentsCard({
  applicationId,
  documents,
}: {
  applicationId: string;
  documents: TrackingDocument[];
}) {
  const [archiveOpen, setArchiveOpen] = useState(false);
  const [archived, setArchived] = useState<SupportingDocument[]>([]);
  const [archiveLoaded, setArchiveLoaded] = useState(false);
  const [archiveError, setArchiveError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    listDocuments(applicationId, { includeRetired: true })
      .then((rows) => {
        if (cancelled) return;
        setArchived(rows);
        setArchiveLoaded(true);
        setArchiveError(false);
      })
      .catch(() => {
        if (cancelled) return;
        setArchiveError(true);
        setArchiveLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, [applicationId]);

  return (
    <section
      aria-label="Supporting documents"
      className="rounded-xl border border-border-default bg-surface-card p-5 shadow-subtle"
    >
      <div className="flex items-center gap-2">
        <FileText className="h-5 w-5 text-text-secondary" aria-hidden="true" />
        <h2 className="text-base font-semibold text-text-primary">
          Supporting documents
        </h2>
      </div>

      {documents.length === 0 ? (
        <p className="mt-2 text-sm text-text-secondary">
          No supporting documents were attached.
        </p>
      ) : (
        <ul className="mt-1 divide-y divide-border-default">
          {documents.map((doc) => (
            <li
              key={doc.id}
              className="flex items-center justify-between gap-3 py-2.5"
            >
              <div className="min-w-0">
                <p className="text-sm font-medium text-text-primary truncate">
                  {doc.file_name}
                </p>
                <p className="text-xs text-text-muted">
                  {formatSize(doc.file_size)}
                  {doc.uploaded_at
                    ? ` · uploaded ${formatDateTime(doc.uploaded_at)}`
                    : ""}
                </p>
              </div>
              <button
                type="button"
                onClick={() =>
                  window.open(doc.file_url, "_blank", "noopener,noreferrer")
                }
                className="inline-flex items-center gap-1.5 rounded-md border border-input-border bg-input-background px-3 py-1.5 text-sm font-medium text-text-primary hover:bg-surface-hover transition-colors shrink-0"
              >
                <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                Open
              </button>
            </li>
          ))}
        </ul>
      )}

      {archived.length > 0 && (
        <div className="mt-3 border-t border-border-default pt-2">
          <button
            type="button"
            onClick={() => setArchiveOpen((open) => !open)}
            aria-expanded={archiveOpen}
            className="flex w-full items-center justify-between rounded-md px-1.5 py-2 text-sm font-medium text-text-secondary hover:text-text-primary transition-colors"
          >
            <span>
              Archived ({archived.length})
            </span>
            <ChevronDown
              className={cn(
                "h-4 w-4 transition-transform",
                archiveOpen ? "rotate-180" : ""
              )}
              aria-hidden="true"
            />
          </button>
          {archiveOpen && (
            <ul className="mt-1 space-y-1">
              {archived.map((doc) => {
                const label =
                  doc.retire_reason === "replaced"
                    ? `Replaced on ${formatDateTime(doc.retired_at)}`
                    : `Removed on ${formatDateTime(doc.retired_at)}`;
                return (
                  <li
                    key={doc.id}
                    className="flex items-center justify-between gap-3 rounded-md px-1.5 py-1.5"
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-text-secondary truncate">
                        {doc.file_name}
                      </p>
                      <p
                        className={cn(
                          "text-xs",
                          doc.retire_reason === "replaced"
                            ? "text-status-cancelled"
                            : "text-text-muted"
                        )}
                      >
                        {label}
                      </p>
                    </div>
                    {doc.retire_reason === "replaced" && (
                      <button
                        type="button"
                        onClick={() =>
                          window.open(doc.file_url, "_blank", "noopener,noreferrer")
                        }
                        className="shrink-0 rounded-md border border-input-border bg-input-background px-2.5 py-1 text-xs font-medium text-text-primary hover:bg-surface-hover transition-colors"
                      >
                        Open
                      </button>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}

      {archiveError && archiveLoaded && (
        <p role="alert" className="mt-2 text-xs text-status-rejected">
          Could not load the archived documents.
        </p>
      )}
    </section>
  );
}