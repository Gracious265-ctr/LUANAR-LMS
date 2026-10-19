"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ExternalLink, FileText, Loader2 } from "lucide-react";

import {
  fetchApprovedDocumentUrl,
  fetchSupportingDocumentUrl,
  listMyApprovedDocuments,
  listMySupportingDocuments,
  type ApprovedDocumentFeedRow,
  type ApprovedDocumentStatus,
  type SupportingDocumentFeedRow,
} from "@/lib/documents/library";
import { formatSize } from "@/lib/approvals/format";
import { formatDateTime } from "@/lib/format";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState } from "@/components/ui/states";

const OPEN_LINK_CLASS =
  "inline-flex shrink-0 items-center gap-1.5 rounded-md border border-input-border bg-input-background px-3 py-1.5 text-sm font-medium text-text-primary transition-colors hover:bg-surface-hover";

const APPROVED_LABEL: Record<ApprovedDocumentStatus, string> = {
  ready: "Ready",
  pending: "Preparing",
  failed: "Failed",
};

const APPROVED_TONE: Record<ApprovedDocumentStatus, BadgeTone> = {
  ready: "approved",
  pending: "pending",
  failed: "rejected",
};

type Loadable<T> =
  | { state: "loading" }
  | { state: "error"; message: string }
  | { state: "ready"; rows: T[] };

/**
 * The client-side documents library. Two owner-scoped feeds are fetched in
 * parallel from this app's proxy routes, so a failure in one (or a slow
 * backend) never blocks the other: each section owns its own loading, error
 * and empty presentation rather than sharing one page-level spinner.
 */
export function DocumentsLibrary() {
  const [supporting, setSupporting] = useState<Loadable<SupportingDocumentFeedRow>>(
    { state: "loading" }
  );
  const [approved, setApproved] = useState<Loadable<ApprovedDocumentFeedRow>>({
    state: "loading",
  });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;

    listMySupportingDocuments()
      .then(({ results }) => {
        if (!cancelled) setSupporting({ state: "ready", rows: results });
      })
      .catch((error: Error) => {
        if (!cancelled) setSupporting({ state: "error", message: error.message });
      });

    listMyApprovedDocuments()
      .then(({ results }) => {
        if (!cancelled) setApproved({ state: "ready", rows: results });
      })
      .catch((error: Error) => {
        if (!cancelled) setApproved({ state: "error", message: error.message });
      });

    return () => {
      cancelled = true;
    };
  }, [attempt]);

  const retry = useCallback(() => {
    setSupporting({ state: "loading" });
    setApproved({ state: "loading" });
    setAttempt((value) => value + 1);
  }, []);

  return (
    <div className="space-y-6">
      <Section
        title="Supporting documents"
        description="Everything you have attached to your leave applications."
        loadable={supporting}
        onRetry={retry}
        emptyTitle="No supporting documents yet"
        emptyDescription="Documents you attach to a leave application appear here."
        renderRow={(row) => <SupportingRow key={row.id} row={row} />}
      />

      <Section
        title="Approved documents"
        description="Generated when an application you submitted is finalized."
        loadable={approved}
        onRetry={retry}
        emptyTitle="No approved documents yet"
        emptyDescription="Once an application is approved, its document is generated and listed here."
        renderRow={(row) => <ApprovedRow key={row.id} row={row} />}
      />
    </div>
  );
}

function Section<T>({
  title,
  description,
  loadable,
  onRetry,
  emptyTitle,
  emptyDescription,
  renderRow,
}: {
  title: string;
  description: string;
  loadable: Loadable<T>;
  onRetry: () => void;
  emptyTitle: string;
  emptyDescription: string;
  renderRow: (row: T) => React.ReactNode;
}) {
  return (
    <section className="space-y-3">
      <div>
        <h3 className="text-base font-semibold text-text-primary">{title}</h3>
        <p className="text-sm text-text-secondary">{description}</p>
      </div>

      <Card className="p-5">
        {loadable.state === "loading" && (
          <div className="space-y-3" aria-hidden="true">
            {[0, 1, 2].map((key) => (
              <div
                key={key}
                className="h-10 animate-pulse rounded-md bg-surface-hover"
              />
            ))}
          </div>
        )}

        {loadable.state === "error" && (
          <ErrorState
            className="border-0 bg-transparent p-6 shadow-none"
            title="Could not load these documents"
            message={loadable.message}
            onRetry={onRetry}
          />
        )}

        {loadable.state === "ready" && loadable.rows.length === 0 && (
          <EmptyState
            titleAs="h4"
            icon={<FileText className="h-5 w-5 text-text-muted" />}
            title={emptyTitle}
            description={emptyDescription}
          />
        )}

        {loadable.state === "ready" && loadable.rows.length > 0 && (
          <ul className="divide-y divide-border-subtle">
            {loadable.rows.map(renderRow)}
          </ul>
        )}
      </Card>
    </section>
  );
}


function SupportingRow({ row }: { row: SupportingDocumentFeedRow }) {
  return (
    <li className="flex items-start justify-between gap-3 py-3 first:pt-0 last:pb-0">
      <div className="flex min-w-0 items-start gap-3">
        <FileText className="mt-0.5 h-4 w-4 shrink-0 text-text-muted" aria-hidden="true" />
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-text-primary">
            {row.file_name}
          </p>
          <p className="mt-0.5 text-xs text-text-muted">
            {formatSize(row.file_size)} · uploaded {formatDateTime(row.uploaded_at)}
            {" · "}
            <Link
              href={`/leave/applications/${row.application.id}`}
              className="font-medium text-brand-primary hover:underline"
            >
              {row.application.reference_number || "View application"}
            </Link>
          </p>
          {row.status === "retired" && (
            <p className="mt-0.5 text-xs text-text-muted">
              {row.retire_reason === "replaced" ? "Replaced" : "Removed"}
              {row.retired_at ? ` ${formatDateTime(row.retired_at)}` : ""}
            </p>
          )}
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-2">
        <Badge size="xs" tone={row.status === "active" ? "approved" : "muted"}>
          {row.status === "active" ? "Active" : "Archived"}
        </Badge>
        <OpenDocumentButton
          label="Open"
          load={() => fetchSupportingDocumentUrl(row.application.id, row.id)}
        />
      </div>
    </li>
  );
}

function ApprovedRow({ row }: { row: ApprovedDocumentFeedRow }) {
  return (
    <li className="flex items-start justify-between gap-3 py-3">
      <div className="flex min-w-0 items-start gap-3">
        <FileText className="mt-0.5 h-4 w-4 shrink-0 text-text-muted" aria-hidden="true" />
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-text-primary">
            {row.file_name || "Approved leave document"}
          </p>
          <p className="mt-0.5 text-xs text-text-muted">
            {approvedSummary(row)}
            {" · "}
            <Link
              href={`/leave/applications/${row.application}`}
              className="font-medium text-brand-primary hover:underline"
            >
              {row.reference_number || "View application"}
            </Link>
          </p>
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-2">
        <Badge size="xs" tone={APPROVED_TONE[row.status]}>
          {APPROVED_LABEL[row.status]}
        </Badge>
        {row.available && (
          <OpenDocumentButton
            label="Download"
            load={() => fetchApprovedDocumentUrl(row.application)}
          />
        )}
      </div>
    </li>
  );
}

/**
 * Opens a stored document, minting its signed URL only when clicked. The feed
 * deliberately carries no URLs (signing is a storage round-trip per row), so
 * the click is when the one request this row needs is made. The button owns
 * its own busy and error state so a failed file never disturbs the list.
 */
function OpenDocumentButton({
  label,
  load,
}: {
  label: string;
  load: () => Promise<string>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const open = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const url = await load();
      if (url) {
        window.open(url, "_blank", "noopener,noreferrer");
      } else {
        setError("The file is not available yet.");
      }
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Could not open the file."
      );
    } finally {
      setBusy(false);
    }
  }, [load]);

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        onClick={open}
        disabled={busy}
        className={`${OPEN_LINK_CLASS} disabled:opacity-60`}
      >
        {busy ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
        ) : (
          <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
        )}
        {label}
      </button>
      {error && (
        <p
          role="alert"
          className="max-w-[12rem] text-right text-xs text-status-rejected"
        >
          {error}
        </p>
      )}
    </div>
  );
}

function approvedSummary(row: ApprovedDocumentFeedRow): string {
  if (row.status === "ready") {
    return row.approved_on
      ? `${formatSize(row.file_size)} · approved ${formatDateTime(row.approved_on)}`
      : formatSize(row.file_size);
  }
  if (row.status === "pending") return "Being prepared";
  return "Generation failed";
}
