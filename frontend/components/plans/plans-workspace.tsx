"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Plus } from "lucide-react";

import type { PlanScope } from "@/lib/plans/types";
import { useOverlayParam } from "@/lib/hooks/useOverlayParam";
import { AdminFormOverlay } from "@/components/hr/AdminFormOverlay";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { PlanApprovalsList } from "./plan-approvals-list";
import { PlanConfirmationsPanel } from "./plan-confirmations-panel";
import { PlanForm } from "./plan-form";
import { PlansList } from "./plans-list";

type PlansView = PlanScope | "approvals" | "confirmations";

/** Query key for the plan overlay on the workspace. */
export const PLAN_PARAM = "plan";

const SCOPE_LABELS: { value: PlansView; label: string }[] = [
  { value: "mine", label: "My plans" },
  { value: "team", label: "My team" },
  { value: "department", label: "My department" },
  { value: "confirmations", label: "To confirm" },
];

/**
 * The employee-facing plan workspace.
 *
 * One switcher owns the scope, so the list below it renders a single scope and
 * never stacks a second tab bar on top. `approvals` only appears for somebody
 * the server says is an approver, and `all` only for HR: both answers arrive
 * from the dashboard layout, which read the caller's capabilities server-side
 * while rendering.
 */
export function PlansWorkspace({
  isHR = false,
  isApprover = false,
  initialView = "mine",
}: {
  isHR?: boolean;
  isApprover?: boolean;
  /** Lets the sidebar deep-link straight to one view. */
  initialView?: PlansView;
}) {
  const [view, setView] = useState<PlansView>(initialView);
  const router = useRouter();
  const overlay = useOverlayParam(PLAN_PARAM);

  const tabs = [...SCOPE_LABELS];
  if (isHR) tabs.push({ value: "all", label: "All plans" });
  if (isApprover) tabs.push({ value: "approvals", label: "To decide" });

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-text-primary">
            Leave day plans
          </h1>
          <p className="text-sm text-text-secondary">
            Plan leave in blocks, send it for approval, then confirm each block
            once it has been approved.
          </p>
        </div>
        {/* Somebody on any scope tab still needs a way to start a new plan. */}
        <Button variant="primary" onClick={overlay.openCreate}>
          <Plus className="size-4" aria-hidden="true" />
          New plan
        </Button>
      </div>

      <Tabs
        value={view}
        className="contents"
        onValueChange={(next) => setView(next as PlansView)}
      >
        <TabsList variant="segmented" aria-label="Leave plans">
          {tabs.map((tab) => (
            <TabsTrigger key={tab.value} variant="segmented" value={tab.value}>
              {tab.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {view === "approvals" ? (
        <PlanApprovalsList headerless />
      ) : view === "confirmations" ? (
        <PlanConfirmationsPanel headerless />
      ) : (
        <PlansList
          key={view}
          headerless
          showScopeTabs={false}
          initialScope={view}
        />
      )}

      {/*
        Create only: editing a plan is its detail page's own workspace, not a
        dialog. Saving swaps this overlay's URL for the new plan's page with
        `replace`, so Back from the plan returns to the list rather than to an
        empty create form.
      */}
      <AdminFormOverlay
        open={overlay.isOpen}
        targetKey={overlay.target}
        title="New leave day plan"
        description="A plan groups the leave you intend to take into one approval, then reserves each block once it is approved."
        size="lg"
        onOpenChange={(open) => {
          if (!open) overlay.close();
        }}
      >
        <PlanForm
          onSuccess={(id) => {
            router.replace(`/dashboard/plans/${id}`);
            router.refresh();
          }}
          onCancel={overlay.close}
        />
      </AdminFormOverlay>
    </div>
  );
}
