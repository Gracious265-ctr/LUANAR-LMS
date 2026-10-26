import Link from "next/link";
import { redirect } from "next/navigation";

import { AuditEntriesTable } from "@/components/hr/audit-entries-table";
import { FinalizedLeaveTable } from "@/components/hr/finalized-leave-table";
import { getCurrentUser } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import {
  ACTION_LABELS,
  listAuditEntries,
  listFinalizedApplications,
  TARGET_TYPE_LABELS,
} from "@/lib/audit";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card } from "@/components/ui/card";
import { FadeIn } from "@/components/motion/FadeIn";

type AuditSearchParams = Promise<{
  action?: string | string[];
  target_type?: string | string[];
}>;

export default async function AuditPage({
  searchParams,
}: {
  searchParams: AuditSearchParams;
}) {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (user.role !== "hr") {
    redirect("/dashboard");
  }

  const params = await searchParams;
  const action =
    typeof params.action === "string"
      ? params.action
      : Array.isArray(params.action)
        ? params.action[0]
        : "";
  const targetType =
    typeof params.target_type === "string"
      ? params.target_type
      : Array.isArray(params.target_type)
        ? params.target_type[0]
        : "";

  let finalized;
  let finalizedError = "";
  try {
    finalized = await listFinalizedApplications();
  } catch {
    finalizedError = "Unable to load finalized applications. Please try again.";
  }

  let entries;
  let entriesError = "";
  try {
    entries = await listAuditEntries({
      action: action || undefined,
      targetType: targetType || undefined,
    });
  } catch {
    entriesError = "Unable to load the administrative history. Please try again.";
  }

  const hasFilters = Boolean(action || targetType);

  return (
    <FadeIn>
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold tracking-tight text-text-primary">Audit View</h2>
          <p className="text-text-secondary">Review finalized applications and the administrative audit trail.</p>
        </div>

        <Card>
          <h3 className="mb-4 text-lg font-semibold text-text-primary">
            Finalized leave
          </h3>
          <p className="mb-4 text-sm text-text-secondary">Applications employees have submitted.</p>
          {finalizedError ? (
            <div className="rounded-lg bg-status-rejected-subtle py-12 text-center text-sm text-status-rejected">
              {finalizedError}
            </div>
          ) : finalized ? (
            <FinalizedLeaveTable applications={finalized.results} />
          ) : null}
        </Card>

        <Card>
          <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
            <div>
              <h3 className="text-lg font-semibold text-text-primary">
                Administrative history
              </h3>
              <p className="text-sm text-text-secondary">Every configuration change, decision, and submission is recorded.</p>
            </div>
            <form
              method="get"
              className="flex flex-wrap items-end gap-3 rounded-lg border border-border-default bg-surface-page p-3"
            >
              <div className="text-sm">
                <label
                  htmlFor="action"
                  className="mb-1 block text-xs font-medium uppercase tracking-wide text-text-muted"
                >
                  Action
                </label>
                <Select name="action" defaultValue={action || ""}>
                  <SelectTrigger id="action" className="w-auto">
                    <SelectValue placeholder="All actions" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="">All actions</SelectItem>
                    {Object.entries(ACTION_LABELS).map(([value, label]) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="text-sm">
                <label
                  htmlFor="target_type"
                  className="mb-1 block text-xs font-medium uppercase tracking-wide text-text-muted"
                >
                  Target
                </label>
                <Select name="target_type" defaultValue={targetType || ""}>
                  <SelectTrigger id="target_type" className="w-auto">
                    <SelectValue placeholder="All targets" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="">All targets</SelectItem>
                    {Object.entries(TARGET_TYPE_LABELS).map(([value, label]) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <Button type="submit" variant="primary">
                Apply
              </Button>
              {hasFilters && (
                <Link
                  href="/dashboard/hr-admin/audit"
                  className="rounded-md border border-border-default bg-button-secondary px-4 py-2 text-sm font-medium text-text-secondary hover:bg-button-secondary-hover"
                >
                  Clear
                </Link>
              )}
            </form>
          </div>
          {entriesError ? (
            <div className="rounded-lg bg-status-rejected-subtle py-12 text-center text-sm text-status-rejected">
              {entriesError}
            </div>
          ) : entries ? (
            <AuditEntriesTable entries={entries.results} />
          ) : null}
        </Card>
      </div>
    </FadeIn>
  );
}