import { Search } from "lucide-react";

import { EntitlementsSection } from "@/components/hr/EntitlementsSection";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  listEntitlements,
  resolveEntitlement,
  type EntitlementListResponse,
  type EntitlementResolution,
} from "@/lib/entitlements";
import { currentDateIso } from "@/lib/utils";

const LIST_ERROR = "Unable to load entitlement rules. Please try again.";
const RESOLVE_ERROR = "Unable to resolve this grade. Please try again.";

/**
 * The grade-based annual-days registry, rendered in whichever module hosts it.
 *
 * Annual days are not a property of a leave type (per §1.3); they are granted
 * per grade band, leave type and financial year. This component is the shared
 * body of that screen so Leave Configuration and the HR-admin page cannot drift
 * apart: both read the same `/entitlements/` API and render the same create/edit
 * overlay.
 *
 * `grade` is the `?grade=` lookup answer ("what does this grade get?"), which is
 * deliberately separate from the table's own local search. The form is a plain
 * GET form, so it submits back to whichever route rendered it.
 */
export async function AnnualDaysConfig({
  grade = "",
  basePath,
}: {
  grade?: string;
  /**
   * Where a table row's edit link points. Defaults to the HR-admin route so
   * existing deep links are unchanged; Leave Configuration passes its own.
   */
  basePath?: string;
}) {
  const queryGrade = grade.trim();

  let entitlements: EntitlementListResponse | undefined;
  let listError = "";
  try {
    entitlements = await listEntitlements();
  } catch {
    listError = LIST_ERROR;
  }

  let resolution: EntitlementResolution | null = null;
  let resolveError = "";
  if (queryGrade) {
    try {
      resolution = await resolveEntitlement(queryGrade);
    } catch {
      resolveError = RESOLVE_ERROR;
    }
  }

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
      <form
        method="get"
        className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle lg:col-span-1"
      >
        <h3 className="text-lg font-semibold text-text-primary">
          Resolve a grade
        </h3>
        <p className="mt-1 text-sm text-text-secondary">
          Enter a grade to see its current entitlement.
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
        <Button type="submit" variant="secondary" className="mt-3">
          Resolve
        </Button>

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

      <div className="lg:col-span-2">
        {listError ? (
          <div className="rounded-lg bg-status-rejected-subtle py-12 text-center text-sm text-status-rejected">
            {listError}
          </div>
        ) : entitlements ? (
          <EntitlementsSection
            entitlements={entitlements.results}
            today={currentDateIso()}
            basePath={basePath}
          />
        ) : null}
      </div>
    </div>
  );
}
