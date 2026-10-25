"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Inbox } from "lucide-react";

import { ApplicationStatusBadge } from "@/components/leave/ApplicationStatusBadge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/states";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatDisplayDate, formatDateRange } from "@/lib/date";
import type { LeaveApplicationSummary } from "@/lib/leave-dashboard";

/**
 * The five most recent applications, any status. Unlike the needs-attention
 * cards these rows route to the read-only tracking page — from here the
 * employee is usually just checking status, not acting — which is also the
 * first step of the 3-click cancel flow (§2.5). Always rendered: it is the one
 * section that is never hidden, and falls back to an empty state for a
 * brand-new employee.
 */
export function RecentApplicationsSection({
  applications,
}: {
  applications: LeaveApplicationSummary[];
}) {
  const router = useRouter();

  return (
    <section aria-labelledby="recent-heading">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2
          id="recent-heading"
          className="text-lg font-semibold text-text-primary"
        >
          Recent Applications
        </h2>
        <Link
          href="/dashboard/leave/applications"
          className="inline-flex items-center gap-1 text-sm font-medium text-brand-primary hover:underline focus-ring"
        >
          View all
          <ArrowRight className="h-4 w-4" aria-hidden="true" />
        </Link>
      </div>

      {applications.length === 0 ? (
        <EmptyState
          icon={<Inbox className="h-10 w-10 text-text-muted" />}
          title="No applications yet"
          description="Start by creating a draft or submitting your first leave application."
          action={
            <Button
              variant="primary"
              onClick={() => router.push("/dashboard/leave/drafts?compose=1")}
            >
              New Application
            </Button>
          }
        />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Leave Type</TableHead>
              <TableHead>Dates</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Submitted</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {applications.map((app) => (
              <TableRow
                key={app.id}
                role="link"
                tabIndex={0}
                onClick={() => router.push(`/applications/${app.id}`)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    router.push(`/applications/${app.id}`);
                  }
                }}
                className="cursor-pointer focus-ring"
              >
                <TableCell className="font-medium text-text-primary">
                  {app.leave_type ?? "Leave application"}
                </TableCell>
                <TableCell>{formatDateRange(app.start_date, app.end_date)}</TableCell>
                <TableCell>
                  <ApplicationStatusBadge status={app.status} />
                </TableCell>
                <TableCell>{formatDisplayDate(app.created_at)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </section>
  );
}
