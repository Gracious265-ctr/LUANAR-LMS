import Link from "next/link";
import { redirect } from "next/navigation";

import { CalendarCheck } from "lucide-react";

import { FadeIn } from "@/components/motion/FadeIn";
import { OnLeaveTable } from "@/components/leave/OnLeaveTable";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { getCurrentUser } from "@/lib/auth";
import { getOnLeave, type OnLeaveData } from "@/lib/on-leave";

const ON_LEAVE_HREF = "/dashboard/leave/on-leave";
const LOAD_ERROR = "Unable to load approved leave.";

type OnLeaveSearchParams = Promise<{
  q?: string | string[];
  past?: string | string[];
}>;

/** A repeated query parameter arrives as an array; the first value wins. */
function single(value: string | string[] | undefined): string {
  if (Array.isArray(value)) return value[0] ?? "";
  return value ?? "";
}

async function OnLeavePage({
  searchParams,
}: {
  searchParams: OnLeaveSearchParams;
}) {
  const user = await getCurrentUser();
  if (!user) {
    redirect("/login");
  }

  const params = await searchParams;
  const query = single(params.q).trim();
  const includePast = single(params.past) === "1";

  const result = await getOnLeave({ q: query, includePast }).then(
    (value) => ({ value, error: "" }),
    () => ({ value: null as OnLeaveData | null, error: LOAD_ERROR })
  );

  const linkFor = (past: boolean) => {
    const next = new URLSearchParams();
    if (query) next.set("q", query);
    if (past) next.set("past", "1");
    const search = next.toString();
    return search ? `${ON_LEAVE_HREF}?${search}` : ON_LEAVE_HREF;
  };

  const filters = [
    { label: "Current & upcoming", href: linkFor(false), current: !includePast },
    { label: "Including past", href: linkFor(true), current: includePast },
  ];

  const counts = result.value?.counts;
  const summary = counts
    ? [
        `${counts.on_leave} on leave`,
        `${counts.upcoming} upcoming`,
        ...(includePast ? [`${counts.returned} returned`] : []),
      ].join(" · ")
    : "";

  return (
    <FadeIn>
      <div className="space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-text-primary">
              On Leave
            </h1>
            <p className="mt-1 text-text-secondary">
              {result.value?.scope.label ?? "Approved leave"}
            </p>
          </div>

          <div
            className="flex flex-wrap gap-1 rounded-lg border border-border-default bg-surface-card p-1"
            role="group"
            aria-label="Filter approved leave"
          >
            {filters.map((filter) => (
              <Link
                key={filter.href}
                href={filter.href}
                aria-current={filter.current ? "page" : undefined}
                className={
                  filter.current
                    ? "rounded-md bg-brand-primary-subtle px-3 py-1.5 text-sm font-medium text-brand-primary"
                    : "rounded-md px-3 py-1.5 text-sm font-medium text-text-secondary hover:bg-surface-hover hover:text-text-primary"
                }
              >
                {filter.label}
              </Link>
            ))}
          </div>
        </div>

        <form
          method="get"
          className="flex flex-wrap items-end gap-3 rounded-lg border border-border-default bg-surface-card p-3"
        >
          <div className="min-w-48 flex-1">
            <label
              htmlFor="q"
              className="mb-1 block text-xs font-medium uppercase tracking-wide text-text-muted"
            >
              Search
            </label>
            <Input
              id="q"
              name="q"
              type="search"
              defaultValue={query}
              placeholder="Name or email"
              className="w-full"
            />
          </div>
          {includePast && <input type="hidden" name="past" value="1" />}
          <Button type="submit" variant="primary">
            Search
          </Button>
          {query && (
            <Link
              href={linkFor(includePast)}
              className="rounded-md border border-border-default bg-button-secondary px-4 py-2 text-sm font-medium text-text-secondary hover:bg-button-secondary-hover"
            >
              Clear
            </Link>
          )}
        </form>

        <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
          {summary && (
            <p className="mb-4 text-sm text-text-secondary">{summary}</p>
          )}
          {result.error ? (
            <ErrorState title={LOAD_ERROR} message={result.error} />
          ) : result.value && result.value.results.length > 0 ? (
            <OnLeaveTable rows={result.value.results} />
          ) : (
            <EmptyState
              icon={<CalendarCheck className="h-6 w-6" />}
              title={query ? "No matches" : "Nobody is on leave"}
              description={
                query
                  ? "No approved leave matches that search."
                  : "Approved leave will appear here."
              }
            />
          )}
        </div>
      </div>
    </FadeIn>
  );
}

export default OnLeavePage;
