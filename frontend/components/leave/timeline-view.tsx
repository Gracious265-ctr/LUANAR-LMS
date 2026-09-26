import {
  ArrowLeftRight,
  BadgeCheck,
  CircleCheckBig,
  FileText,
  History,
  PencilLine,
  Send,
  Undo2,
  Workflow,
  type LucideIcon,
} from "lucide-react";

import { formatDateTime } from "@/lib/tracking/format";
import type { TimelineEntry } from "@/lib/leave-history";

const KIND_ICONS: Record<string, LucideIcon> = {
  submission: Send,
  workflow_assignment: Workflow,
  decision: CircleCheckBig,
  revision: PencilLine,
  cancellation: Undo2,
  document: FileText,
  reassignment: ArrowLeftRight,
  finalisation: BadgeCheck,
  audit: History,
};

const KIND_TONES: Record<string, string> = {
  submission: "bg-brand-primary-subtle text-brand-primary",
  workflow_assignment: "bg-status-info-subtle text-status-info",
  decision: "bg-status-info-subtle text-status-info",
  revision: "bg-status-pending-subtle text-status-pending",
  cancellation: "bg-status-rejected-subtle text-status-rejected",
  document: "bg-status-info-subtle text-status-info",
  reassignment: "bg-status-pending-subtle text-status-pending",
  finalisation: "bg-status-approved-subtle text-status-approved",
  audit: "bg-surface-muted text-text-muted",
};

const GLYPHS: Record<string, string> = {
  submission: "Submitted",
  workflow_assignment: "Workflow",
  decision: "Decision",
  revision: "Revision",
  cancellation: "Cancellation",
  document: "Document",
  reassignment: "Reassignment",
  finalisation: "Finalisation",
  audit: "Event",
};

interface TimelineViewProps {
  entries: TimelineEntry[];
  emptyMessage?: string;
}

/**
 * Shared chronological activity feed (Unit 24). Reads the timeline entries
 * returned by the history endpoints; used verbatim on the HR per-application
 * page and the employee submitted-application page.
 */
export function TimelineView({
  entries,
  emptyMessage = "No recorded events for this application.",
}: TimelineViewProps) {
  if (entries.length === 0) {
    return <p className="text-sm text-text-muted">{emptyMessage}</p>;
  }

  return (
    <ol className="relative space-y-5 border-l border-border-default pl-6">
      {entries.map((entry) => (
        <li key={entry.id} className="relative">
          <span className="absolute -left-[27px] top-0.5">
            <TimelineGlyph kind={entry.kind} />
          </span>
          <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
            <span className="text-sm font-medium text-text-primary">
              {entry.action_label}
            </span>
            <span className="text-xs text-text-muted">
              {formatDateTime(entry.occurred_at)}
            </span>
          </div>
          {entry.summary && (
            <p className="mt-0.5 text-sm text-text-secondary">
              {entry.summary}
            </p>
          )}
          {(entry.stage_order != null || entry.resubmission_number != null) && (
            <p className="mt-1 flex flex-wrap gap-2 text-xs text-text-muted">
              {entry.stage_order != null && (
                <span className="rounded-full border border-border-default px-2 py-0.5">
                  Stage {entry.stage_order}
                </span>
              )}
              {entry.resubmission_number != null && (
                <span className="rounded-full border border-border-default px-2 py-0.5">
                  Resubmission {entry.resubmission_number}
                </span>
              )}
            </p>
          )}
        </li>
      ))}
    </ol>
  );
}

/** The small glyph dot for one timeline entry kind (also used in dashboard rows). */
export function TimelineGlyph({ kind }: { kind: string }) {
  const Icon = KIND_ICONS[kind] ?? History;
  const tone = KIND_TONES[kind] ?? KIND_TONES.audit;
  return (
    <span
      className={`flex h-5 w-5 items-center justify-center rounded-full ${tone}`}
      title={GLYPHS[kind] ?? kind}
    >
      <Icon className="h-3 w-3" aria-hidden="true" />
    </span>
  );
}