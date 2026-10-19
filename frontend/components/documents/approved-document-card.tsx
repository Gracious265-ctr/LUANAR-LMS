"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { FileCheck2, Loader2, TriangleAlert, ExternalLink } from "lucide-react";

import {
  fetchApprovedDocument,
  fetchHRAapprovedDocument,
  type ApprovedDocumentResult,
  type ApprovedLeaveDocument,
} from "@/lib/documents/approved";
import { formatSize } from "@/lib/approvals/format";
import { formatDateTime } from "@/lib/tracking/format";

// The approved document is rendered in the django-q worker after the approval
// commits, so it can be ready a moment later. While the row reports ``pending``
// the card re-checks at this cadence until the render finishes (or gives up
// after ``MAX_POLLS`` attempts so an endpoint that never resolves is not polled
// forever).
const POLL_INTERVAL_MS = 3000;
const MAX_POLLS = 30;

/**
 * The official approved-leave document, as a link to a signed URL.
 *
 * Deliberately a link and not a viewer, iframe or proxy: the PDF is opened
 * straight from storage, so the bytes never pass through this server. While
 * the document is still rendering the backend reports the status with
 * ``available: false``, which is shown inline rather than as a broken link, so
 * the card needs only one request to know what to render.
 */
export function ApprovedDocumentCard({
  applicationId,
  audience = "employee",
}: {
  applicationId: string;
  audience?: "employee" | "hr";
}) {
  const [result, setResult] = useState<ApprovedDocumentResult | null>(null);
  const inFlight = useRef(false);

  const refetch = useCallback(() => {
    if (inFlight.current) return;
    const loader =
      audience === "hr" ? fetchHRAapprovedDocument : fetchApprovedDocument;
    inFlight.current = true;
    loader(applicationId)
      .then(setResult)
      .finally(() => {
        inFlight.current = false;
      });
  }, [applicationId, audience]);

  useEffect(() => {
    let cancelled = false;
    const loader =
      audience === "hr" ? fetchHRAapprovedDocument : fetchApprovedDocument;
    loader(applicationId).then((next) => {
      if (!cancelled) setResult(next);
    });
    return () => {
      cancelled = true;
    };
  }, [applicationId, audience]);

  const pending = result !== null && result.ok && result.data.status === "pending";

  useEffect(() => {
    if (!pending) return;
    let attempts = 0;
    const timer = setInterval(() => {
      attempts += 1;
      if (attempts > MAX_POLLS) {
        clearInterval(timer);
        return;
      }
      refetch();
    }, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [pending, refetch]);

  if (!result) {
    return (
      <section
        aria-label="Approved leave document"
        className="rounded-xl border border-border-default bg-surface-card p-5 shadow-subtle"
      >
        <div className="h-12 animate-pulse rounded-lg bg-surface-muted" />
      </section>
    );
  }

  // A 404 means the caller may not read it (or none exists yet) — the same
  // answer either way, and nothing is rendered that would confirm otherwise.
  if (!result.ok) {
    return null;
  }

  return (
    <section
      aria-label="Approved leave document"
      className="rounded-xl border border-border-default bg-surface-card p-5 shadow-subtle"
    >
      <div className="flex items-center gap-2">
        <FileCheck2 className="h-5 w-5 text-text-secondary" aria-hidden="true" />
        <h2 className="text-base font-semibold text-text-primary">
          Approved leave document
        </h2>
      </div>
      <Body document={result.data} />
    </section>
  );
}

function Body({ document }: { document: ApprovedLeaveDocument }) {
  const { status, available, download_url, file_name, file_size, rendered_at } =
    document;

  if (status === "pending") {
    return (
      <p className="mt-2 flex items-center gap-2 text-sm text-text-secondary">
        <Loader2
          className="h-4 w-4 animate-spin"
          aria-hidden="true"
        />
        Being prepared — the document appears here once it is ready.
      </p>
    );
  }

  if (status === "failed") {
    return (
      <p className="mt-2 flex items-start gap-2 text-sm text-status-rejected">
        <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
        <span>
          The document could not be generated. Please contact HR.
        </span>
      </p>
    );
  }

  return (
    <div className="mt-2 flex items-center justify-between gap-3">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-text-primary">
          {file_name}
        </p>
        <p className="text-xs text-text-muted">
          {formatSize(file_size)}
          {rendered_at ? ` · generated ${formatDateTime(rendered_at)}` : ""}
        </p>
      </div>
      {available && download_url ? (
        <a
          href={download_url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-input-border bg-input-background px-3 py-1.5 text-sm font-medium text-text-primary transition-colors hover:bg-surface-hover"
        >
          <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
          Open
        </a>
      ) : null}
    </div>
  );
}
