"use client";

import { CalendarDays } from "lucide-react";

interface WorkingDaysPreviewProps {
  days: number | null;
  loading: boolean;
}

export function WorkingDaysPreview({ days, loading }: WorkingDaysPreviewProps) {
  return (
    <div className="rounded-lg border border-border-default bg-surface-muted p-4">
      <div className="flex items-center gap-2 text-text-secondary mb-1">
        <CalendarDays className="h-4 w-4" />
        <span className="text-sm font-medium">Working Days</span>
      </div>
      {loading ? (
        <div className="h-8 w-16 animate-pulse rounded bg-surface-hover" />
      ) : (
        <div className="text-2xl font-bold text-text-primary">
          {days !== null ? days : "—"}
        </div>
      )}
      <p className="text-xs text-text-muted mt-1">
        Excludes weekends (Sat/Sun)
      </p>
    </div>
  );
}
