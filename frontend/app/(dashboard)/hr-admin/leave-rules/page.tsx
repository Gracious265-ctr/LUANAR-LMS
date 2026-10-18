import Link from "next/link";
import { redirect } from "next/navigation";

import { LeaveRulesSection } from "@/components/hr/LeaveRulesSection";
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
import { FadeIn } from "@/components/motion/FadeIn";

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
    redirect("/");
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
    return `/hr-admin/leave-rules${qs ? `?${qs}` : ""}`;
  }

  return (
    <FadeIn>
      <div className="space-y-6">
        <div>
          <div>
            <h2 className="text-xl font-semibold tracking-tight text-text-primary">Leave rules</h2>
            <p className="text-text-secondary">
              Configure how long and under what conditions each leave type can be
              taken. Rule changes are effective-dated and never alter submitted
              applications.
            </p>
          </div>
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

        {rulesError ? (
          <div className="rounded-lg bg-status-rejected-subtle py-12 text-center text-sm text-status-rejected">
            {rulesError}
          </div>
        ) : rules ? (
          <LeaveRulesSection
            rules={rules.results}
            leaveTypes={leaveTypes?.results ?? []}
            today={currentDateIso()}
            clearFiltersHref="/hr-admin/leave-rules"
            heading={
              effective === "all"
                ? "All rules"
                : effective === "current"
                  ? "Current rules"
                  : "Upcoming rules"
            }
          />
        ) : null}
      </div>
    </FadeIn>
  );
}