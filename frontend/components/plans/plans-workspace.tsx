"use client";

import Link from "next/link";
import { useState } from "react";
import { Plus } from "lucide-react";

import type { PlanScope } from "@/lib/plans/types";
import { buttonVariants } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { PlanApprovalsList } from "./plan-approvals-list";
import { PlanConfirmationsPanel } from "./plan-confirmations-panel";
import { PlansList } from "./plans-list";

type PlansView = PlanScope | "approvals" | "confirmations";

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
        <Link
          href="/dashboard/plans/new"
          className={buttonVariants({ variant: "primary", size: "md" })}
        >
          <Plus className="size-4" aria-hidden="true" />
          New plan
        </Link>
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
    </div>
  );
}
