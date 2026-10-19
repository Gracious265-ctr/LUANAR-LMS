"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Inbox, Plus } from "lucide-react";

import { useLeaveApplications } from "@/lib/hooks/useLeaveApplications";
import { getLeaveTypes } from "@/lib/services/leaveTypes";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
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

interface ApplicationsListProps {
  /** Heading above the list; the drafts view names itself. */
  heading?: string;
  /** Restricts the fetch to one status, e.g. `"draft"` for the Drafts tab. */
  statusFilter?: string;
  /** Omits statuses from the fetch, e.g. `"draft"` for My Applications. */
  excludeStatus?: string;
}

/**
 * "My Applications" with the apply flow as an overlay.
 *
 * The open application lives in the URL (`?compose=1`, `?edit=<id>`,
 * `&stage=review`) rather than in component state, so a refresh resumes the
 * same application, the Back button steps out of it, and the old
 * `/leave/new` and `/leave/{id}/edit` links keep working through the redirect
 * shims in those routes.
 *
 * The overlay's URL state is anchored to the current pathname, so the same
 * component powers `/leave` (submitted work, drafts hidden) and
 * `/leave/drafts` (drafts only) without either landing on the other.
 */
export function ApplicationsList({
  heading = "My Applications",
  statusFilter,
  excludeStatus,
}: ApplicationsListProps = {}) {
  const { applications, loading, error, refetch, removeLocal, restoreLocal } =
    useLeaveApplications({ status: statusFilter, excludeStatus });
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [leaveTypeNames, setLeaveTypeNames] = useState<Record<number, string>>({});

  const composeParam = searchParams.get("compose");
  const editParam = searchParams.get("edit");
  const stageParam = searchParams.get("stage");
  const stage: LeaveOverlayStage =
    stageParam === "review" || stageParam === "done" ? stageParam : "form";

  // Memoised because the stage-sync callback below depends on it, and a fresh
  // object literal each render would defeat the memo entirely.
  const target: OverlayTarget | null = useMemo(
    () =>
      editParam
        ? { mode: "edit", applicationId: editParam, stage }
        : composeParam === "1"
          ? { mode: "create", stage: "form" }
          : null,
    [editParam, composeParam, stage]
  );

  const targetId = target?.applicationId;

  const openNew = useCallback(() => {
    router.push(`${pathname}?compose=1`);
  }, [router, pathname]);

  const openExisting = useCallback(
    (applicationId: string, nextStage: LeaveOverlayStage) => {
      router.push(
        nextStage === "form"
          ? `${pathname}?edit=${applicationId}`
          : `${pathname}?edit=${applicationId}&stage=${nextStage}`
      );
    },
    [router, pathname]
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
          ? `${pathname}?edit=${id}`
          : `${pathname}?edit=${id}&stage=${nextStage}`
      );
    },
    [router, pathname, targetId]
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
    router.replace(pathname);
  }, [router, pathname]);

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
          <h2 className="text-xl font-semibold tracking-tight text-text-primary">{heading}</h2>
          <p className="text-text-secondary text-sm">
            {applications.length} application{applications.length === 1 ? "" : "s"}
          </p>
        </div>
        <Button onClick={openNew} className="px-4 py-2">
          <Plus className="h-4 w-4" />
          New Application
        </Button>
      </div>

      {applications.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Inbox className="h-10 w-10" />}
            title="No applications yet"
            description="Your submitted leave applications will show up here."
            action={
              <Button onClick={openNew} className="px-4 py-2">
                <Plus className="h-4 w-4" />
                New Application
              </Button>
            }
          />
        </Card>
      ) : (
        <Stagger className="grid gap-4">
          {applications.map((app) => (
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
