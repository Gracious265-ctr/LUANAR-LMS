import Link from "next/link";
import { redirect } from "next/navigation";
import { Plus } from "lucide-react";

import { LeaveRuleTable } from "@/components/hr/leave-rule-table";
import { getCurrentUser } from "@/lib/auth";
import {
  listLeaveRules,
  listLeaveTypes,
  type EffectiveFilter,
} from "@/lib/leave-rules";
import { currentDateIso } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card } from "@/components/ui/card";

const TABS: { value: EffectiveFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "current", label: "Current" },
  { value: "upcoming", label: "Upcoming" },
];

export default async function LeaveRulesPage({
  searchParams,
}: {
  searchParams: Promise<{
    effective?: string | string[];
    leave_type?: string | string[];
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
  const effective: EffectiveFilter =
    params.effective === "current" || params.effective === "upcoming"
      ? params.effective
      : "all";
  const leaveTypeFilter =
    typeof params.leave_type === "string" ? params.leave_type : "";

  let leaveTypes;
  let typesError = "";
  try {
    leaveTypes = await listLeaveTypes();
  } catch {
    typesError = "Unable to load leave types. Please try again.";
  }

  let rules;
  let rulesError = "";
  try {
    rules = await listLeaveRules({
      ...(leaveTypeFilter ? { leave_type: leaveTypeFilter } : {}),
      effective,
    });
  } catch {
    rulesError = "Unable to load leave rules. Please try again.";
  }

  function tabHref(value: EffectiveFilter): string {
    const query = new URLSearchParams();
    if (leaveTypeFilter) {
      query.set("leave_type", leaveTypeFilter);
    }
    if (value !== "all") {
      query.set("effective", value);
    }
    const qs = query.toString();
    return `/dashboard/hr-admin/leave-rules${qs ? `?${qs}` : ""}`;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-xl font-semibold tracking-tight text-text-primary">Leave rules</h2>
          <p className="text-text-secondary">
            Configure how long and under what conditions each leave type can be
            taken. Rule changes are effective-dated and never alter submitted
            applications.
          </p>
        </div>
        <Link
          href="/dashboard/hr-admin/leave-rules/new"
          className="inline-flex items-center gap-2 rounded-md bg-button-primary px-4 py-2 text-sm font-medium text-button-primary-foreground hover:bg-button-primary-hover"
        >
          <Plus className="h-4 w-4" />
          New rule
        </Link>
      </div>

      <div className="flex items-center justify-between gap-4">
        <div className="flex rounded-lg border border-border-default bg-surface-card p-1 shadow-subtle">
          {TABS.map((tab) => (
            <Link
              key={tab.value}
              href={tabHref(tab.value)}
              className={
                effective === tab.value
                  ? "rounded-md bg-brand-primary px-4 py-1.5 text-sm font-medium text-brand-primary-foreground"
                  : "rounded-md px-4 py-1.5 text-sm font-medium text-text-secondary hover:text-text-primary"
              }
            >
              {tab.label}
            </Link>
          ))}
        </div>

        <form method="get" className="flex items-center gap-2">
          {effective !== "all" && (
            <input type="hidden" name="effective" value={effective} />
          )}
          <Select name="leave_type" defaultValue={leaveTypeFilter}>
            <SelectTrigger size="sm" aria-label="Leave type" className="w-auto py-1.5">
              <SelectValue placeholder="All leave types" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">All leave types</SelectItem>
              {leaveTypes?.results.map((leaveType) => (
                <SelectItem key={leaveType.id} value={String(leaveType.id)}>
                  {leaveType.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button type="submit" variant="secondary" size="sm">
            Filter
          </Button>
        </form>
      </div>

      {typesError && (
        <div className="rounded-lg bg-status-rejected-subtle p-3 text-sm text-status-rejected">
          {typesError}
        </div>
      )}

      <Card>
        <h3 className="mb-4 text-lg font-semibold text-text-primary">
          {effective === "all"
            ? "All rules"
            : effective === "current"
              ? "Current rules"
              : "Upcoming rules"}
        </h3>
        {rulesError ? (
          <div className="rounded-lg bg-status-rejected-subtle py-12 text-center text-sm text-status-rejected">
            {rulesError}
          </div>
        ) : rules ? (
          <LeaveRuleTable rules={rules.results} today={currentDateIso()} />
        ) : null}
      </Card>
    </div>
  );
}