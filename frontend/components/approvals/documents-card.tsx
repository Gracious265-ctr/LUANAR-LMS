"use client";

<<<<<<< HEAD
import { useState } from "react";

import { Download, FileText, Loader2, Paperclip } from "lucide-react";

import { formatBytes, formatDateTime } from "@/lib/approvals/format";
import { ApiError, fetchDocumentDownload } from "@/lib/approvals/service";
import type { ApprovalDetail } from "@/lib/approvals/types";

import { Card } from "./primitives";

export function DocumentsCard({ detail }: { detail: ApprovalDetail }) {
  const [downloading, setDownloading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function onDownload(documentId: string) {
    setDownloading(documentId);
    setError(null);
    try {
      const { url } = await fetchDocumentDownload(detail.id, documentId);
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? "The file is no longer available."
          : "Could not start the download. Please try again."
      );
    } finally {
      setDownloading(null);
    }
  }

  if (detail.documents.length === 0) {
    return (
      <Card title="Documents" icon={<Paperclip className="h-4 w-4" />}>
        <p className="text-sm text-text-muted">No supporting documents.</p>
      </Card>
    );
  }

  return (
    <Card title="Documents" icon={<Paperclip className="h-4 w-4" />}>
      <ul className="divide-y divide-border-default">
        {detail.documents.map((doc) => (
          <li key={doc.id} className="flex items-center gap-3 py-3">
            <span className="text-text-secondary" aria-hidden="true">
              <FileText className="h-5 w-5" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-text-primary" title={doc.name}>
                {doc.name}
              </p>
              <p className="text-xs text-text-muted">
                {[
                  formatBytes(doc.size_bytes),
                  doc.uploaded_at ? formatDateTime(doc.uploaded_at) : "",
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
            </div>
            <button
              type="button"
              onClick={() => onDownload(doc.id)}
              disabled={downloading === doc.id}
              aria-label={`Download ${doc.name}`}
              className="inline-flex items-center gap-1.5 rounded-lg border border-border-default px-3 py-1.5 text-xs font-medium text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary disabled:cursor-not-allowed disabled:opacity-60"
            >
              {downloading === doc.id ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
              ) : (
                <Download className="h-3.5 w-3.5" aria-hidden="true" />
              )}
              Download
            </button>
          </li>
        ))}
      </ul>
      {error && (
        <p role="alert" className="mt-2 text-sm text-status-rejected">
          {error}
        </p>
      )}
    </Card>
=======
import { Download, FileText, FileX } from "lucide-react";
import { useState } from "react";

import { formatDateTime, formatSize } from "@/lib/approvals/format";
import { fetchDocumentDownload } from "@/lib/approvals/service";
import type { ApprovalReview } from "@/lib/approvals/types";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/states";

import { Panel } from "./panel";

export function DocumentsCard({ data }: { data: ApprovalReview }) {
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState("");

  const documents = data.documents;

  async function openDocument(documentId: string) {
    if (busyId) return;
    setBusyId(documentId);
    setError("");
    try {
      const doc = await fetchDocumentDownload(data.application.id, documentId);
      window.open(doc.download_url, "_blank", "noopener,noreferrer");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not open the document."
      );
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Panel title="Supporting documents">
      {documents.length === 0 ? (
        <EmptyState
          className="py-6"
          icon={<FileX className="h-8 w-8" />}
          title="No supporting documents attached"
          description="Files attached to this application will show up here."
        />
      ) : (
        <ul className="divide-y divide-border-default">
          {documents.map((doc) => (
            <li key={doc.id} className="flex items-center justify-between gap-3 py-2.5">
              <div className="flex items-center gap-3">
                <FileText className="h-4 w-4 shrink-0 text-text-secondary" aria-hidden="true" />
                <div>
                  <p className="text-sm font-medium text-text-primary">{doc.name}</p>
                  <p className="text-xs text-text-muted">
                    {formatSize(doc.size)}
                    {doc.uploaded_at ? ` · ${formatDateTime(doc.uploaded_at)}` : ""}
                  </p>
                </div>
              </div>
              <Button
  type="button"
  onClick={() => openDocument(doc.id)}
  disabled={busyId !== null}
  variant="secondary"
  size="sm"
>
                <Download className="h-3.5 w-3.5" aria-hidden="true" />
                {busyId === doc.id ? "Opening…" : "View"}
              </Button>
            </li>
          ))}
        </ul>
      )}
      {error && (
        <Alert tone="rejected" className="mt-3">
          {error}
        </Alert>
      )}
    </Panel>
>>>>>>> feature/plans-teams
  );
}