import Link from "next/link";
import { redirect } from "next/navigation";
import { Plus } from "lucide-react";

import { DelegationTable } from "@/components/hr/delegation-table";
import { getCurrentUser } from "@/lib/auth";
import {
  DELEGATION_STATE_CODES,
  delegationStateLabel,
  listDelegations,
  type DelegationState,
} from "@/lib/delegations";
import { Card } from "@/components/ui/card";

type StateFilter = DelegationState | "";

const TABS: { value: StateFilter; label: string }[] = [
  { value: "", label: "All" },
  ...DELEGATION_STATE_CODES.map((value) => ({
    value,
    label: delegationStateLabel(value),
  })),
];

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
    redirect("/dashboard");
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

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-xl font-semibold tracking-tight text-text-primary">Delegations</h2>
          <p className="text-text-secondary">
            Review approver unavailability requests, approve a delegate, reject
            with a reason, or cancel active cover.
          </p>
        </div>
        <Link
          href="/dashboard/hr-admin/delegations/new"
          className="inline-flex items-center gap-2 rounded-md bg-button-primary px-4 py-2 text-sm font-medium text-button-primary-foreground hover:bg-button-primary-hover"
        >
          <Plus className="h-4 w-4" />
          New delegation request
        </Link>
      </div>

      <div className="flex flex-wrap gap-1 rounded-lg border border-border-default bg-surface-card p-1 shadow-subtle">
        {TABS.map((tab) => (
          <Link
            key={tab.value}
            href={`/dashboard/hr-admin/delegations${tab.value ? `?state=${tab.value}` : ""}`}
            className={
              state === tab.value
                ? "rounded-md bg-brand-primary px-4 py-1.5 text-sm font-medium text-brand-primary-foreground"
                : "rounded-md px-4 py-1.5 text-sm font-medium text-text-secondary hover:text-text-primary"
            }
          >
            {tab.label}
          </Link>
        ))}
      </div>

      <Card>
        <h3 className="mb-4 text-lg font-semibold text-text-primary">
          {state ? `${delegationStateLabel(state)} delegations` : "All delegations"}
        </h3>
        {delegationsError ? (
          <div className="rounded-lg bg-status-rejected-subtle py-12 text-center text-sm text-status-rejected">
            {delegationsError}
          </div>
        ) : delegations ? (
          <DelegationTable delegations={delegations.results} />
        ) : null}
      </Card>
    </div>
  );
}