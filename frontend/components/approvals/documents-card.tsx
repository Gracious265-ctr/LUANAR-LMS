"use client";

import { Download, FileText } from "lucide-react";
import { useState } from "react";

import { formatDateTime, formatSize } from "@/lib/approvals/format";
import { fetchDocumentDownload } from "@/lib/approvals/service";
import type { ApprovalReview } from "@/lib/approvals/types";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

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
        <p className="text-sm text-text-secondary">
          No supporting documents were attached.
        </p>
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
  );
}