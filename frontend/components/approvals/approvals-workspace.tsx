"use client";

import { useState } from "react";

import { ApprovalsList } from "@/components/approvals/approvals-list";
import { CoverPanel } from "@/components/approvals/cover-panel";
import { CancellationRequestsTable } from "@/components/cancellations/cancellation-requests-table";
import type { DelegateCandidate, Delegation } from "@/lib/delegations";
import { cn } from "@/lib/utils";

type WorkspaceView = "applications" | "cancellations" | "cover";

/**
 * Top-level /approvals workspace: a segmented control between the Unit 16
 * application queue, the Unit 18 cancellation requests queue, and — for
 * approvers only — the cover queue, where an approver hands their pending
 * approvals to someone else.
 */
export function ApprovalsWorkspace({
  canRequestCover = false,
  initialView = "applications",
  delegations = null,
  candidates = [],
  delegationsError,
}: {
  canRequestCover?: boolean;
  /** Lets the sidebar deep-link straight to the Cover tab. */
  initialView?: WorkspaceView;
  delegations?: Delegation[] | null;
  candidates?: DelegateCandidate[];
  delegationsError?: string;
}) {
  const [view, setView] = useState<WorkspaceView>(initialView);

  const tabs: { value: WorkspaceView; label: string }[] = [
    { value: "applications", label: "Applications" },
    { value: "cancellations", label: "Cancellation requests" },
  ];
  if (canRequestCover) {
    tabs.push({ value: "cover", label: "Cover" });
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-text-primary">Approvals</h1>
        <p className="text-sm text-text-secondary">
          Review and decide on leave applications and cancellation requests.
        </p>
      </div>

      <div
        role="tablist"
        aria-label="Approvals workspace"
        className="inline-flex rounded-lg border border-border-default bg-surface-card p-1"
      >
        {tabs.map((tab) => (
          <button
            key={tab.value}
            role="tab"
            aria-selected={view === tab.value}
            onClick={() => setView(tab.value)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
              view === tab.value
                ? "bg-brand-primary-subtle text-brand-primary"
                : "text-text-secondary hover:text-text-primary"
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {view === "applications" ? (
        <ApprovalsList headerless />
      ) : view === "cancellations" ? (
        <CancellationRequestsTable />
      ) : (
        <CoverPanel
          delegations={delegations}
          candidates={candidates}
          error={delegationsError}
        />
      )}
    </div>
  );
}
