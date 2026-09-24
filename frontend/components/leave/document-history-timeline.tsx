"use client";

import { FileText, History, RotateCcw, Trash2 } from "lucide-react";

import { formatFileSize } from "@/lib/documents/config";
import type {
  DocumentAction,
  DocumentHistory,
  SupportingDocument,
} from "@/lib/documents/types";
import { formatDateTime } from "@/lib/tracking/format";

const ACTION_LABELS: Record<DocumentAction, string> = {
  document_uploaded: "Uploaded",
  document_removed: "Removed",
  document_replaced: "Replaced",
};

interface DocumentHistoryTimelineProps {
  history: DocumentHistory;
}

/**
 * Active + retired documents and the audit timeline for a submitted
 * application (Unit 19 history surface).
 */
export function DocumentHistoryTimeline({
  history,
}: DocumentHistoryTimelineProps) {
  return (
    <div className="space-y-5">
      <section>
        <h3 className="mb-2 text-xs font-semibold uppercase text-text-muted">
          Active documents ({history.active.length})
        </h3>
        {history.active.length === 0 ? (
          <p className="text-sm text-text-muted">None.</p>
        ) : (
          <ul className="space-y-1.5">
            {history.active.map((doc) => (
              <ActiveRow key={doc.id} document={doc} />
            ))}
          </ul>
        )}
      </section>

      <section>
        <h3 className="mb-2 text-xs font-semibold uppercase text-text-muted">
          Retired documents ({history.retired.length})
        </h3>
        {history.retired.length === 0 ? (
          <p className="text-sm text-text-muted">None.</p>
        ) : (
          <ul className="space-y-1.5">
            {history.retired.map((doc) => (
              <RetiredRow key={doc.id} document={doc} />
            ))}
          </ul>
        )}
      </section>

      <section>
        <h3 className="mb-2 text-xs font-semibold uppercase text-text-muted">
          Activity
        </h3>
        {history.events.length === 0 ? (
          <p className="text-sm text-text-muted">No document activity yet.</p>
        ) : (
          <ul className="space-y-3">
            {history.events.map((event) => (
              <li key={event.id} className="flex gap-3">
                <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-surface-muted text-text-muted">
                  <History className="h-3.5 w-3.5" aria-hidden="true" />
                </span>
                <div className="min-w-0">
                  <p className="text-sm text-text-primary">
                    {ACTION_LABELS[event.action] ?? event.action}
                    <span className="text-text-muted">
                      {" · "}
                      {event.actor_name || "Unknown"}
                    </span>
                  </p>
                  {typeof event.metadata?.file_name === "string" && (
                    <p className="text-xs text-text-muted">
                      {event.metadata.file_name}
                    </p>
                  )}
                  <p className="text-xs text-text-muted">
                    {formatDateTime(event.occurred_at)}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function ActiveRow({ document }: { document: SupportingDocument }) {
  return (
    <li className="flex items-center gap-2 text-sm text-text-primary">
      <FileText className="h-3.5 w-3.5 text-text-muted shrink-0" />
      <span className="truncate">{document.file_name}</span>
      <span className="text-xs text-text-muted">
        {formatFileSize(document.file_size)}
      </span>
    </li>
  );
}

function RetiredRow({ document }: { document: SupportingDocument }) {
  const isReplaced = document.retire_reason === "replaced";
  return (
    <li className="flex items-center gap-2 text-sm text-text-muted line-through decoration-text-muted/50">
      {isReplaced ? (
        <RotateCcw className="h-3.5 w-3.5 shrink-0 text-status-pending" />
      ) : (
        <Trash2 className="h-3.5 w-3.5 shrink-0" />
      )}
      <span className="truncate">{document.file_name}</span>
      {isReplaced && document.replaced_by_name && (
        <span className="text-xs text-text-primary no-underline">
          → {document.replaced_by_name}
        </span>
      )}
    </li>
  );
}