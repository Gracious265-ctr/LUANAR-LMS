"use client";

import { FileText, Plus } from "lucide-react";
import Link from "next/link";

import { useLeaveApplications } from "@/lib/hooks/useLeaveApplications";
import { DraftCard } from "./DraftCard";

export function DraftsList() {
  const { applications, loading, error, refetch } = useLeaveApplications("draft");

  if (loading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-32 animate-pulse rounded-xl bg-surface-muted" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-surface-card rounded-xl border border-border-default shadow-subtle p-8 text-center">
        <p className="text-status-rejected text-sm">{error}</p>
        <button
          onClick={refetch}
          className="mt-2 text-sm text-text-link hover:text-text-link-hover"
        >
          Try again
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-text-primary">My Drafts</h2>
          <p className="text-text-secondary text-sm">
            {applications.length} draft{applications.length !== 1 ? "s" : ""}
          </p>
        </div>
        <Link
          href="/dashboard/leave/new"
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md bg-button-primary text-button-primary-foreground font-medium text-sm hover:bg-button-primary-hover transition-colors"
        >
          <Plus className="h-4 w-4" />
          New Application
        </Link>
      </div>

      {applications.length === 0 ? (
        <div className="bg-surface-card rounded-xl border border-border-default shadow-subtle p-12 text-center">
          <FileText className="h-12 w-12 mx-auto text-text-disabled mb-4" />
          <h3 className="text-lg font-semibold text-text-primary mb-2">
            No drafts yet
          </h3>
          <p className="text-text-secondary text-sm mb-4">
            Start a new leave application to see it here.
          </p>
          <Link
            href="/dashboard/leave/new"
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-md bg-button-primary text-button-primary-foreground font-medium text-sm hover:bg-button-primary-hover transition-colors"
          >
            <Plus className="h-4 w-4" />
            New Application
          </Link>
        </div>
      ) : (
        <div className="grid gap-4">
          {applications.map((app) => (
            <DraftCard key={app.id} application={app} onDelete={refetch} />
          ))}
        </div>
      )}
    </div>
  );
}
