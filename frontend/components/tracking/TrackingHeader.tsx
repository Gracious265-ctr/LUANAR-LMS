import { ArrowLeft, Clock } from "lucide-react";
import Link from "next/link";

import { formatDate, formatDateTime } from "@/lib/tracking/format";
import { STATUS_META } from "@/lib/tracking/labels";
import type { TrackingResponse } from "@/lib/tracking/types";
import { Button } from "@/components/ui/button";

import { StatusBadge } from "./StatusBadge";
import { Badge } from "@/components/ui/badge";

export function TrackingHeader({
  data,
  onRefresh,
  refreshing,
  lastRefreshed,
}: {
  data: TrackingResponse;
  onRefresh: () => void;
  refreshing: boolean;
  lastRefreshed: Date | null;
}) {
  const { application, status } = data;
  const meta = STATUS_META[status];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <Link
          href="/dashboard/leave/drafts"
          className="inline-flex min-h-11 items-center gap-1.5 rounded-lg text-sm font-medium text-text-link hover:text-text-link-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          My applications
        </Link>
        <div className="flex items-center gap-3">
          {lastRefreshed && (
            <p className="hidden text-xs text-text-muted sm:block">
              Last refreshed {formatDateTime(lastRefreshed.toISOString())}
            </p>
          )}
          <Button
            type="button"
            onClick={onRefresh}
            disabled={refreshing}
            variant="secondary"
            className="min-h-11"
          >
            <meta.icon className="h-4 w-4" aria-hidden="true" />
            Refresh
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
        <h1 className="break-words font-mono text-lg font-semibold text-text-primary">
          {application.reference_number}
        </h1>
        <StatusBadge status={status} />
        {data.has_open_cancellation_request && (
          <Badge tone="pending">
            <Clock className="h-3.5 w-3.5" aria-hidden="true" />
            Cancellation requested
          </Badge>
        )}
      </div>

      <div className="space-y-1 text-sm">
        <p className="font-medium break-words text-text-primary">
          {application.leave_type?.name || "Leave"} ·{" "}
          {formatDate(application.start_date)} – {formatDate(application.end_date)}{" "}
          · {application.working_days}
          {application.working_days === 1 ? " working day" : " working days"}
        </p>
        <p className="text-text-secondary">
          Submitted{" "}
          <time dateTime={application.submitted_at ?? undefined}>
            {formatDateTime(application.submitted_at)}
          </time>
        </p>
        {data.cancelled_at && (
          <p className="text-status-cancelled">
            Cancelled on{" "}
            <time dateTime={data.cancelled_at}>{formatDateTime(data.cancelled_at)}</time>
          </p>
        )}
      </div>
    </div>
  );
}