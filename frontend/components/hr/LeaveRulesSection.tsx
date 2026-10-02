"use client";

import { useRouter } from "next/navigation";

import { Plus } from "lucide-react";

import type { LeaveRule, LeaveType } from "@/lib/leave-rules";
import { useOverlayParam } from "@/lib/hooks/useOverlayParam";
import { AdminFormOverlay } from "@/components/hr/AdminFormOverlay";
import { LeaveRuleForm } from "@/components/hr/leave-rule-form";
import { LeaveRuleTable } from "@/components/hr/leave-rule-table";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

/** Query key for the leave-rule overlay on the list page. */
export const LEAVE_RULE_PARAM = "rule";

export interface LeaveRulesSectionProps {
  rules: LeaveRule[];
  leaveTypes: LeaveType[];
  /** Server-resolved today, so "current" versus "scheduled" has one authority. */
  today?: string;
  /**
   * Overrides the card heading, for a page that names the slice it is showing
   * ("Current rules", "Upcoming rules").
   */
  heading?: string;
  /**
   * Where "Show all rules" goes, as a plain href.
   *
   * A string rather than a callback because this section is a client component
   * and the page that renders it is a server component: a function cannot cross
   * that boundary. The router lives here, so the page only names the target.
   */
  clearFiltersHref?: string;
}

/**
 * The leave-rule registry as a create/edit overlay.
 *
 * Edit mode resolves the record from the rows already on screen: the table
 * carries the whole rule, and the leave types it needs are already on the page.
 *
 * This is the one list in the wave whose filters can hide the row being edited
 * — `?effective` and `?leave_type` both narrow the query. The dialog says so
 * and offers to show every rule rather than clearing an admin's filters for
 * them without being asked.
 */
export function LeaveRulesSection({
  rules,
  leaveTypes,
  today,
  heading = "Leave rules",
  clearFiltersHref,
}: LeaveRulesSectionProps) {
  const router = useRouter();
  const overlay = useOverlayParam(LEAVE_RULE_PARAM);

  const editing =
    overlay.target !== null && !overlay.isCreate
      ? rules.find((row) => String(row.id) === overlay.target)
      : undefined;

  return (
    <Card>
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-text-primary">{heading}</h3>
          <p className="mt-1 text-sm text-text-secondary">
            Rules set how long a leave type may be taken, how much notice is
            needed, and whether it draws on the annual entitlement.
          </p>
        </div>
        <Button
          variant="primary"
          onClick={overlay.openCreate}
          className="shrink-0"
        >
          <Plus className="h-4 w-4" />
          New leave rule
        </Button>
      </div>

            <LeaveRuleTable rules={rules} today={today} onEdit={overlay.openEdit} />

      <AdminFormOverlay
        open={overlay.isOpen}
        targetKey={overlay.target}
        size="md"
        title={
          editing
            ? `Edit ${editing.leave_type_name} rule`
            : overlay.isCreate
              ? "New leave rule"
              : "Edit leave rule"
        }
        description={
          editing
            ? "Changes apply to applications filed from the effective date onward."
            : "Define the limits for a leave type. A rule applies from its effective date; earlier applications keep the rule they were filed under."
        }
        onOpenChange={(open) => {
          if (!open) overlay.close();
        }}
        notFound={
          editing === undefined && !overlay.isCreate
            ? "That leave rule is not in the current view. The list may be filtered to a different leave type or date range."
            : undefined
        }
        clearFiltersLabel="Show all rules"
        onClearFilters={clearFiltersHref ? () => router.push(clearFiltersHref) : undefined}
      >
        <LeaveRuleForm
          leaveRule={editing}
          leaveTypes={leaveTypes}
          onSuccess={() => {
            overlay.close();
            router.refresh();
          }}
          onCancel={overlay.close}
        />
      </AdminFormOverlay>
    </Card>
  );
}
