"use client";

import { useState } from "react";

import { ApprovalsList } from "@/components/approvals/approvals-list";
import { CancellationRequestsTable } from "@/components/cancellations/cancellation-requests-table";
import { cn } from "@/lib/utils";

type WorkspaceView = "applications" | "cancellations";

/**
 * Top-level /approvals workspace: a segmented control between the Unit 16
 * application queue and the Unit 18 cancellation requests queue.
 */
export function ApprovalsWorkspace() {
  const [view, setView] = useState<WorkspaceView>("applications");

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
        <button
          role="tab"
          aria-selected={view === "applications"}
          onClick={() => setView("applications")}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
            view === "applications"
              ? "bg-brand-primary-subtle text-brand-primary"
              : "text-text-secondary hover:text-text-primary"
          )}
        >
          Applications
        </button>
        <button
          role="tab"
          aria-selected={view === "cancellations"}
          onClick={() => setView("cancellations")}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
            view === "cancellations"
              ? "bg-brand-primary-subtle text-brand-primary"
              : "text-text-secondary hover:text-text-primary"
          )}
        >
          Cancellation requests
        </button>
      </div>

      {view === "applications" ? (
        <ApprovalsList headerless />
      ) : (
        <CancellationRequestsTable />
      )}
    </div>
  );
}