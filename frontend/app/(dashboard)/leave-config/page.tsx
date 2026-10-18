import Link from "next/link";
import { Plus } from "lucide-react";

import { LeaveTypeTable } from "@/components/leave-config/LeaveTypeTable";
import { ShowInactiveToggle } from "@/components/leave-config/ShowInactiveToggle";
import { Alert } from "@/components/ui/alert";
import { buttonVariants } from "@/components/ui/button";
import type { LeaveType } from "@/lib/leave-config";
import { listLeaveTypes, requireLeaveConfigAccess } from "@/lib/leave-config-server";

const LIST_ERROR = "Unable to load leave types. Please try again.";

/**
 * The registry (spec 3.2): one table, inactive types greyed into the same
 * list rather than banished to a second page of their own.
 *
 * The list is server-rendered, so "Show inactive" is a navigation rather than
 * local state — a link to everything, retired included, stays shareable and
 * the default view (active only) stays what every other module's dropdown
 * would have seen anyway.
 */
export default async function LeaveConfigPage({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  await requireLeaveConfigAccess();
  const params = await searchParams;
  const includeInactive = params.include_inactive === "true";

  let leaveTypes: LeaveType[] = [];
  let error = "";
  try {
    leaveTypes = await listLeaveTypes({ includeInactive });
  } catch {
    error = LIST_ERROR;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-text-primary">
            Leave Configuration
          </h2>
          <p className="text-text-secondary">
            The leave types every other module reads from. Deactivating a type
            retires it from new applications and plans without touching
            anything already filed against it.
          </p>
        </div>
        <Link
          href="/leave-config/new"
          className={buttonVariants({ variant: "primary" })}
        >
          <Plus className="h-4 w-4" />
          Create Leave Type
        </Link>
      </div>

      <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h3 className="text-lg font-semibold text-text-primary">
            All leave types
          </h3>
          <ShowInactiveToggle checked={includeInactive} />
        </div>

        {error ? (
          <Alert tone="rejected" className="py-12 text-center">
            {error}
          </Alert>
        ) : (
          <LeaveTypeTable leaveTypes={leaveTypes} />
        )}
      </div>
    </div>
  );
}
