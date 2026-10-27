"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { FilePen, Inbox, Plus, SearchX } from "lucide-react";

import { type LeaveApplication } from "@/lib/leave-api";
import { useLeaveApplications } from "@/lib/hooks/useLeaveApplications";
import { matchesSearch } from "@/lib/search";
import { getLeaveTypes } from "@/lib/services/leaveTypes";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { FilterChips } from "@/components/ui/filter-chips";
import { ListSearch } from "@/components/ui/list-search";
import { EmptyState } from "@/components/ui/states";
import { Stagger } from "@/components/motion/Stagger";
import { StaggerItem } from "@/components/motion/StaggerItem";

import { ApplicationCard } from "./ApplicationCard";
import {
  LeaveApplicationOverlay,
  type LeaveOverlayStage,
} from "./LeaveApplicationOverlay";

interface OverlayTarget {
  mode: "create" | "edit";
  applicationId?: string;
  stage: LeaveOverlayStage;
}

/**
 * The statuses My Applications can be narrowed to. `submitted` reads as
 * "Pending" because that is what the card's own badge calls it, and the value
 * stays the backend's code because the filter is applied by the endpoint.
 */
const STATUS_FILTERS = [
  { value: "", label: "All" },
  { value: "submitted", label: "Pending" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
  { value: "cancelled", label: "Cancelled" },
] as const;

type StatusFilter = (typeof STATUS_FILTERS)[number]["value"];

/**
 * The list of leave applications, with the apply flow as an overlay. Rendered
 * at two routes so each has its own sidebar item:
 *
 * - `applications` (My Applications) is the track view for everything that has
 *   left the employee's hands — drafts are excluded.
 * - `drafts` lists in-progress applications.
 *
 * The open application lives in the URL (`?compose=1`, `?edit=<id>`,
 * `&stage=review`) rather than in component state, so a refresh resumes the
 * same application, the Back button steps out of it, and the old
 * `/dashboard/leave/new` and `/dashboard/leave/{id}/edit` links keep working
 * through the redirect shims in those routes.
 */
export function ApplicationsList({ view }: { view: "applications" | "drafts" }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const isDrafts = view === "drafts";
  const basePath = isDrafts
    ? "/dashboard/leave/drafts"
    : "/dashboard/leave/applications";

  // An optional `?status=` narrows My Applications (e.g. the dashboard's
  // pending card links here with `status=submitted`). It maps straight onto the
  // server-side filter the endpoint already exposes.
  const statusFilter = searchParams.get("status") ?? undefined;
  const { applications, loading, error, refetch, removeLocal, restoreLocal } =
    useLeaveApplications(
      isDrafts
        ? { status: "draft" }
        : { status: statusFilter, excludeStatus: "draft" }
    );
  const [leaveTypeNames, setLeaveTypeNames] = useState<Record<number, string>>({});
  const [search, setSearch] = useState("");

  // A hand-edited `?status=` outside the five codes is passed to the API
  // unchanged but cannot select a chip, so the bar honestly reads "All".
  const activeStatus: StatusFilter = STATUS_FILTERS.some(
    (option) => option.value === statusFilter
  )
    ? (statusFilter as StatusFilter)
    : "";

  const visibleApplications = useMemo(
    () =>
      applications.filter((application) =>
        matchesSearch(search, [
          application.reference_number,
          application.reason,
          application.status,
          application.start_date,
          application.end_date,
          application.leave_type_id != null
            ? leaveTypeNames[application.leave_type_id]
            : null,
        ])
      ),
    [applications, leaveTypeNames, search]
  );

  const setStatusFilter = useCallback(
    (next: StatusFilter) => {
      const params = new URLSearchParams(searchParams.toString());
      if (next) {
        params.set("status", next);
      } else {
        params.delete("status");
      }
      const query = params.toString();
      router.push(query ? `${basePath}?${query}` : basePath);
    },
    [basePath, router, searchParams]
  );

  const composeParam = searchParams.get("compose");
  const editParam = searchParams.get("edit");
  const stageParam = searchParams.get("stage");
  const stage: LeaveOverlayStage =
    stageParam === "review" || stageParam === "done" ? stageParam : "form";
  const composeRequested = composeParam === "1";

  // "New Application" continues an in-progress draft rather than starting a
  // blank one, so a `compose` request on the drafts list resumes the most
  // recently edited draft — the one the employee is most likely mid-way through.
  const latestDraftId = useMemo(() => {
    if (!isDrafts) return undefined;
    const latest = applications.reduce<LeaveApplication | undefined>(
      (newest, app) => (!newest || app.updated_at > newest.updated_at ? app : newest),
      undefined
    );
    return latest?.id;
  }, [isDrafts, applications]);

  const resolvedEditId =
    editParam ?? (composeRequested ? latestDraftId : undefined);

  // Memoised because the stage-sync callback below depends on it, and a fresh
  // object literal each render would defeat the memo entirely. The overlay is
  // held closed until the list has loaded on the drafts view, so a `compose`
  // request cannot flash a blank create dialog before it resolves to the draft.
  const target: OverlayTarget | null = useMemo(() => {
    if (resolvedEditId) {
      return { mode: "edit", applicationId: resolvedEditId, stage };
    }
    if (composeRequested && !loading) {
      return { mode: "create", stage: "form" };
    }
    return null;
  }, [resolvedEditId, composeRequested, loading, stage]);

  const targetId = target?.applicationId;

  const openNew = useCallback(() => {
    // The compose flow always lives on the drafts list, so starting one from My
    // Applications still lands where drafts are continued — and a `compose`
    // request there resumes the most recent draft.
    router.push("/dashboard/leave/drafts?compose=1");
  }, [router]);

  const openExisting = useCallback(
    (applicationId: string, nextStage: LeaveOverlayStage) => {
      router.push(
        nextStage === "form"
          ? `${basePath}?edit=${applicationId}`
          : `${basePath}?edit=${applicationId}&stage=${nextStage}`
      );
    },
    [router, basePath]
  );

  /**
   * Mirrors a stage transition into the URL so a refresh, a copy-pasted link,
   * and the Back button all land somewhere real.
   *
   * `replace` rather than `push`, deliberately. Opening the overlay already
   * pushed one entry, and `close()` steps back exactly once, so pushing a second
   * entry per stage would make the first close press a no-op from the user's
   * point of view — the dialog would still be open, one stage back.
   */
  const handleStageChange = useCallback(
    (nextStage: LeaveOverlayStage, nextApplicationId?: string) => {
      const id = nextApplicationId ?? targetId;
      if (!id) return;
      router.replace(
        nextStage === "form"
          ? `${basePath}?edit=${id}`
          : `${basePath}?edit=${id}&stage=${nextStage}`
      );
    },
    [router, basePath, targetId]
  );

  /**
   * Closing goes back through history when we pushed the state, so the browser
   * Back button and the overlay's close affordance behave the same. The
   * fallback handles a direct visit to a deep link, where there is nothing to
   * pop back to.
   */
  const close = useCallback(() => {
    if (window.history.length > 1) {
      router.back();
      return;
    }
    router.replace(basePath);
  }, [router, basePath]);

  useEffect(() => {
    let active = true;
    getLeaveTypes().then((types) => {
      if (!active) return;
      const map: Record<number, string> = {};
      for (const t of types) {
        map[t.id] = t.name;
      }
      setLeaveTypeNames(map);
    });
    return () => {
      active = false;
    };
  }, []);

  const overlay = (
    <LeaveApplicationOverlay
      open={target !== null}
      mode={target?.mode ?? "create"}
      applicationId={target?.mode === "edit" ? target.applicationId : undefined}
      initialStage={target?.stage ?? "form"}
      basePath={basePath}
      onOpenChange={(open) => {
        if (!open) close();
      }}
      onSubmitted={() => refetch({ silent: true })}
      onStageChange={handleStageChange}
    />
  );

  if (loading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-32 animate-pulse rounded-xl bg-surface-muted" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <Card className="text-center">
        <p className="text-status-rejected text-sm">{error}</p>
        <Button onClick={() => refetch()} variant="link" size="sm" className="mt-2 h-auto text-text-link">
          Try again
        </Button>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {overlay}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold tracking-tight text-text-primary">
            {isDrafts ? "Drafts" : "My Applications"}
          </h2>
          <p className="text-text-secondary text-sm">
            {applications.length} {isDrafts ? "draft" : "application"}
            {applications.length === 1 ? "" : "s"}
          </p>
        </div>
        <Button onClick={openNew} className="px-4 py-2">
          <Plus className="h-4 w-4" />
          New Application
        </Button>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <ListSearch
          value={search}
          onChange={setSearch}
          label={
            isDrafts ? "Search drafts" : "Search applications"
          }
          placeholder={
            isDrafts
              ? "Search by reference, leave type, or dates"
              : "Search by reference, leave type, dates, or reason"
          }
          className="w-full sm:w-80"
        />
        {!isDrafts && (
          <FilterChips
            label="Filter applications by status"
            options={STATUS_FILTERS}
            value={activeStatus}
            onChange={setStatusFilter}
          />
        )}
      </div>

      {applications.length === 0 ? (
        <Card>
          <EmptyState
            icon={
              isDrafts ? (
                <FilePen className="h-10 w-10" />
              ) : (
                <Inbox className="h-10 w-10" />
              )
            }
            title={isDrafts ? "No drafts" : "No applications yet"}
            description={
              isDrafts
                ? "Applications you start but haven't submitted will show up here."
                : "Your submitted leave applications will show up here."
            }
            action={
              <Button onClick={openNew} className="px-4 py-2">
                <Plus className="h-4 w-4" />
                New Application
              </Button>
            }
          />
        </Card>
      ) : visibleApplications.length === 0 ? (
        <Card>
          <EmptyState
            icon={<SearchX className="h-10 w-10" />}
            title="No matching applications"
            description="Try a different reference, leave type, date, or status."
          />
        </Card>
      ) : (
        <Stagger className="grid gap-4">
          {visibleApplications.map((app) => (
            <StaggerItem key={app.id}>
              <ApplicationCard
                application={app}
                leaveTypeName={
                  app.leave_type_id != null
                    ? leaveTypeNames[app.leave_type_id] || `Type #${app.leave_type_id}`
                    : "Not selected"
                }
                onDelete={removeLocal}
                onRestore={restoreLocal}
                onEdit={openExisting}
              />
            </StaggerItem>
          ))}
        </Stagger>
      )}
    </div>
  );
}
