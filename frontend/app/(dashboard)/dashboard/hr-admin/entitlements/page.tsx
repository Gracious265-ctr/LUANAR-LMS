import Link from "next/link";
import { redirect } from "next/navigation";
import { Plus, Search } from "lucide-react";

import { EntitlementTable } from "@/components/hr/entitlement-table";
import { getCurrentUser } from "@/lib/auth";
import {
  listEntitlements,
  resolveEntitlement,
} from "@/lib/entitlements";
import { currentDateIso } from "@/lib/utils";
import { Input } from "@/components/ui/input";

export default async function EntitlementsPage({
  searchParams,
}: {
  searchParams: Promise<{ grade?: string | string[] }>;
}) {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (user.role !== "hr") {
    redirect("/dashboard");
  }

  const { grade } = await searchParams;
  const queryGrade = typeof grade === "string" ? grade.trim() : "";

  let entitlements;
  let listError = "";
  try {
    entitlements = await listEntitlements();
  } catch {
    listError = "Unable to load entitlement rules. Please try again.";
  }

  let resolution = null;
  let resolveError = "";
  if (queryGrade) {
    try {
      resolution = await resolveEntitlement(queryGrade);
    } catch {
      resolveError = "Unable to resolve this grade. Please try again.";
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-xl font-semibold tracking-tight text-text-primary">Entitlements</h2>
          <p className="text-text-secondary">
            Configure grade ranges and annual leave entitlements. Grade ranges
            must not overlap; change an existing band by editing its rule.
          </p>
        </div>
        <Link
          href="/dashboard/hr-admin/entitlements/new"
          className="inline-flex items-center gap-2 rounded-md bg-button-primary px-4 py-2 text-sm font-medium text-button-primary-foreground hover:bg-button-primary-hover"
        >
          <Plus className="h-4 w-4" />
          New entitlement
        </Link>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <form
          method="get"
          className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle lg:col-span-1"
        >
          <h3 className="text-lg font-semibold text-text-primary">
            Resolve a grade
          </h3>
          <p className="mt-1 text-sm text-text-secondary">
            Enter a grade to see the annual entitlement the system determines
            for it today.
          </p>
          <div className="relative mt-4">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
            <Input
              name="grade"
              defaultValue={queryGrade}
              placeholder="e.g. G"
              className="pl-9 pr-3"
            />
          </div>
          <button
            type="submit"
            className="mt-3 rounded-md border border-border-default bg-button-secondary px-4 py-2 text-sm font-medium text-text-secondary hover:bg-button-secondary-hover"
          >
            Resolve
          </button>

          {queryGrade && (
            <div className="mt-4 rounded-md bg-brand-primary-subtle p-3 text-sm">
              {resolveError ? (
                <p className="text-status-rejected">{resolveError}</p>
              ) : resolution && resolution.days !== null ? (
                <p className="text-text-primary">
                  <span className="font-semibold">Grade {resolution.grade}:</span>{" "}
                  {resolution.days} annual days
                  <span className="block text-xs text-text-muted">
                    Effective from {resolution.effective_from}
                  </span>
                </p>
              ) : (
                <p className="text-text-secondary">
                  No entitlement rule applies to grade{" "}
                  <span className="font-semibold">{queryGrade}</span> yet.
                </p>
              )}
            </div>
          )}
        </form>

        <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle lg:col-span-2">
          <h3 className="mb-4 text-lg font-semibold text-text-primary">
            Configuration
          </h3>
          {listError ? (
            <div className="rounded-lg bg-status-rejected-subtle py-12 text-center text-sm text-status-rejected">
              {listError}
            </div>
          ) : entitlements ? (
            <EntitlementTable
              entitlements={entitlements.results}
              today={currentDateIso()}
            />
          ) : null}
        </div>
      </div>
    </div>
  );
}