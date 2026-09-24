"use client";

import { Download, FileText } from "lucide-react";

import { formatFileSize } from "@/lib/documents/config";
import { documentContentUrl } from "@/lib/documents/service";
import type { SupportingDocument } from "@/lib/documents/types";
import { formatDateTime } from "@/lib/tracking/format";

interface DocumentListProps {
  applicationId: string;
  documents: SupportingDocument[];
}

/** Read-only list of active documents with open-in-new-tab content links. */
export function DocumentList({ applicationId, documents }: DocumentListProps) {
  if (documents.length === 0) {
    return (
      <p className="text-sm text-text-muted">No supporting documents.</p>
    );
  }

  return (
    <ul className="space-y-1.5">
      {documents.map((doc) => (
        <li
          key={doc.id}
          className="flex items-center gap-2 rounded-lg border border-border-default bg-surface-card p-2.5"
        >
          <FileText className="h-4 w-4 text-text-muted shrink-0" />
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-text-primary">
              {doc.file_name}
            </p>
            <p className="text-xs text-text-muted">
              {[formatFileSize(doc.file_size), formatDateTime(doc.uploaded_at)]
                .filter(Boolean)
                .join(" · ")}
            </p>
          </div>
          <a
            href={documentContentUrl(applicationId, doc.id)}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`Open ${doc.file_name}`}
            className="p-1 rounded hover:bg-surface-hover text-text-muted hover:text-text-primary transition-colors"
          >
            <Download className="h-4 w-4" />
          </a>
        </li>
      ))}
    </ul>
  );
}