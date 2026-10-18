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
import { Card } from "@/components/ui/card";
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
const ALL_STATES_HREF = "/hr-admin/delegations";

export default async function DelegationsPage({
  searchParams,
}: {
  searchParams: Promise<{ state?: string | string[] }>;
}) {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (user.role !== "hr") {
    redirect("/");
  }

  const params = await searchParams;
  const stateValue = typeof params.state === "string" ? params.state : "";
  const state: StateFilter = DELEGATION_STATE_CODES.includes(
    stateValue as DelegationState
  )
    ? (stateValue as DelegationState)
    : "";

  let delegations;
  let delegationsError = "";
  try {
    delegations = await listDelegations(state || undefined);
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
          <p className="text-text-secondary">
            Review approver unavailability requests, approve a delegate, reject
            with a reason, or cancel active cover.
          </p>
        </div>

        <Card>
          <DelegationsSection
            delegations={delegations?.results ?? []}
            employees={employees}
            stateFilter={state}
            heading={state ? `${delegationStateLabel(state)} delegations` : "All delegations"}
            clearFiltersHref={ALL_STATES_HREF}
            error={delegationsError}
            tabs={TABS.map((tab) => ({
              label: tab.label,
              href: `${ALL_STATES_HREF}${tab.value ? `?state=${tab.value}` : ""}`,
              current: state === tab.value,
            }))}
          />
        </Card>
      </div>
    </FadeIn>
  );
}