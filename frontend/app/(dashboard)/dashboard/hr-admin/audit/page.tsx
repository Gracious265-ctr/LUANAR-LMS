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
import { EmptyState } from "@/components/ui/states";
import { Input } from "@/components/ui/input";
import { FadeIn } from "@/components/motion/FadeIn";

type AuditSearchParams = Promise<{
  action?: string | string[];
  target_type?: string | string[];
  employee?: string | string[];
}>;

/** A repeated query parameter arrives as an array; the first value wins. */
function single(value: string | string[] | undefined): string {
  if (Array.isArray(value)) return value[0] ?? "";
  return value ?? "";
}

/**
 * The page's own URL for a given combination of filters.
 *
 * Both forms on this page are plain GET forms, so each one must carry the
 * other's parameters as hidden inputs; this is what the "Clear" links point at
 * once one filter is dropped.
 */
function auditHref(filters: {
  action?: string;
  targetType?: string;
  employee?: string;
}): string {
  const params = new URLSearchParams();
  if (filters.action) params.set("action", filters.action);
  if (filters.targetType) params.set("target_type", filters.targetType);
  if (filters.employee) params.set("employee", filters.employee);
  const query = params.toString();
  return query
    ? `/dashboard/hr-admin/audit?${query}`
    : "/dashboard/hr-admin/audit";
}

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
  const action = single(params.action);
  const targetType = single(params.target_type);
  const employee = single(params.employee).trim();

  let finalized;
  let finalizedError = "";
  try {
    finalized = await listFinalizedApplications({
      employee: employee || undefined,
    });
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
          <div className="mb-4">
            <h3 className="text-lg font-semibold text-text-primary">
              Finalized leave
            </h3>
            <p className="text-sm text-text-secondary">
              Applications employees have submitted. Search by the
              employee&apos;s name or email.
            </p>
          </div>

          <form method="get" className="mb-4 flex flex-wrap items-end gap-3">
            {/* The other form's filters travel with this one, so searching for
                an employee does not silently reset the audit history below. */}
            {action && <input type="hidden" name="action" value={action} />}
            {targetType && (
              <input type="hidden" name="target_type" value={targetType} />
            )}
            <div className="w-full sm:w-80">
              <label
                htmlFor="employee"
                className="mb-1 block text-xs font-medium uppercase tracking-wide text-text-muted"
              >
                Employee
              </label>
              <Input
                id="employee"
                name="employee"
                type="search"
                defaultValue={employee}
                placeholder="Name or email"
                className="h-10 py-2 text-sm"
              />
            </div>
            <Button type="submit" variant="primary">
              Search
            </Button>
            {employee && (
              <Link
                href={auditHref({ action, targetType })}
                className="rounded-md border border-border-default bg-button-secondary px-4 py-2 text-sm font-medium text-text-secondary hover:bg-button-secondary-hover"
              >
                Clear
              </Link>
            )}
          </form>

          {finalizedError ? (
            <div className="rounded-lg bg-status-rejected-subtle py-12 text-center text-sm text-status-rejected">
              {finalizedError}
            </div>
          ) : finalized ? (
            <FinalizedLeaveTable
              applications={finalized.results}
              empty={
                employee ? (
                  <EmptyState
                    title="No finalized leave matches this employee"
                    description="Try a different name or email."
                  />
                ) : undefined
              }
            />
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
              {/* Keep the employee search alive when the history is narrowed. */}
              {employee && (
                <input type="hidden" name="employee" value={employee} />
              )}
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
                  href={auditHref({ employee })}
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