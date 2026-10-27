import Link from "next/link";
import { redirect } from "next/navigation";

import { DelegationsSection } from "@/components/hr/DelegationsSection";
import { getCurrentUser } from "@/lib/auth";
import {
  DELEGATION_STATE_CODES,
  delegationStateLabel,
  listDelegations,
  type DelegationState,
} from "@/lib/delegations";
import { listAllEmployees } from "@/lib/employees";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { FadeIn } from "@/components/motion/FadeIn";

type StateFilter = DelegationState | "";

const TABS: { value: StateFilter; label: string }[] = [
  { value: "", label: "All" },
  ...DELEGATION_STATE_CODES.map((value) => ({
    value,
    label: delegationStateLabel(value),
  })),
];

/** Where the tabs' "All" tab points, and the escape hatch out of a filter. */
const ALL_STATES_HREF = "/dashboard/hr-admin/delegations";

/** A repeated query parameter arrives as an array; the first value wins. */
function single(value: string | string[] | undefined): string {
  if (Array.isArray(value)) return value[0] ?? "";
  return value ?? "";
}

/**
 * The page's own URL for a state and/or approver search.
 *
 * Both are server filters, so each control keeps the other one: the tabs carry
 * the search, and the search form carries the active tab.
 */
function delegationsHref(filters: {
  state?: StateFilter;
  approver?: string;
}): string {
  const params = new URLSearchParams();
  if (filters.state) params.set("state", filters.state);
  if (filters.approver) params.set("approver", filters.approver);
  const query = params.toString();
  return query ? `${ALL_STATES_HREF}?${query}` : ALL_STATES_HREF;
}

export default async function DelegationsPage({
  searchParams,
}: {
  searchParams: Promise<{
    state?: string | string[];
    approver?: string | string[];
  }>;
}) {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (user.role !== "hr") {
    redirect("/dashboard");
  }

  const params = await searchParams;
  const stateValue = single(params.state);
  const state: StateFilter = DELEGATION_STATE_CODES.includes(
    stateValue as DelegationState
  )
    ? (stateValue as DelegationState)
    : "";
  const approver = single(params.approver).trim();

  let delegations;
  let delegationsError = "";
  try {
    delegations = await listDelegations(
      state || undefined,
      approver || undefined
    );
  } catch {
    delegationsError = "Unable to load delegations. Please try again.";
  }

  // The whole staff, not one page: both pickers in the create form are built
  // from this, and a page-1 read would quietly offer only the first twenty
  // people. Read on every visit rather than on open, matching the roles page,
  // which loads all employees for its holder picker the same way.
  const employees = await listAllEmployees().catch(() => []);

  return (
    <FadeIn>
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold tracking-tight text-text-primary">Delegations</h2>
          <p className="text-text-secondary">Review and decide approver unavailability requests.</p>
        </div>

        <form
          method="get"
          className="flex flex-wrap items-end gap-3 rounded-xl border border-border-default bg-surface-card p-4 shadow-subtle"
        >
          {/* Keep the active tab when searching, so the two filters combine. */}
          {state && <input type="hidden" name="state" value={state} />}
          <div className="w-full sm:w-80">
            <label
              htmlFor="approver"
              className="mb-1 block text-xs font-medium uppercase tracking-wide text-text-muted"
            >
              Approver
            </label>
            <Input
              id="approver"
              name="approver"
              type="search"
              defaultValue={approver}
              placeholder="Name or email"
              className="h-10 py-2 text-sm"
            />
          </div>
          <Button type="submit" variant="primary">
            Search
          </Button>
          {approver && (
            <Link
              href={delegationsHref({ state })}
              className="rounded-md border border-border-default bg-button-secondary px-4 py-2 text-sm font-medium text-text-secondary hover:bg-button-secondary-hover"
            >
              Clear
            </Link>
          )}
        </form>

        <Card>
          <DelegationsSection
            delegations={delegations?.results ?? []}
            employees={employees}
            stateFilter={state}
            heading={
              approver
                ? `Delegations for "${approver}"`
                : state
                  ? `${delegationStateLabel(state)} delegations`
                  : "All delegations"
            }
            clearFiltersHref={delegationsHref({ approver })}
            error={delegationsError}
            tabs={TABS.map((tab) => ({
              label: tab.label,
              href: delegationsHref({ state: tab.value, approver }),
              current: state === tab.value,
            }))}
          />
        </Card>
      </div>
    </FadeIn>
  );
}