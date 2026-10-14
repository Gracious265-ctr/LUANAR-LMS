"use client";

import { Plus, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { createPlan } from "@/lib/plans/service";
import type { PlanBlockInput } from "@/lib/plans/types";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { DateRangePicker } from "@/components/ui/date-picker";
import { Field } from "@/components/ui/input";
import { FormError } from "@/components/ui/form-error";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { getLeaveTypes, type LeaveType } from "@/lib/services/leaveTypes";

interface DraftBlock {
  key: string;
  leave_type_id: number | null;
  start_date: string;
  end_date: string;
}

let nextKey = 0;
function emptyBlock(): DraftBlock {
  nextKey += 1;
  return { key: `block-${nextKey}`, leave_type_id: null, start_date: "", end_date: "" };
}

/**
 * Builds a plan: a period plus the blocks inside it.
 *
 * The backend owns every rule that matters — the financial year, duration,
 * notice, eligibility, and the balance held by reservations — so this form
 * deliberately checks only what it needs to build a valid request. Anything
 * subtler comes back as a 422 and is rendered here rather than guessed at.
 */
export function PlanForm({
  onSuccess,
  onCancel,
}: {
  /**
   * Replaces the default `router.push(detail)` + `router.refresh()`. The
   * overlay passes this so it can swap its own URL for the new plan's page in
   * place; with it omitted the form navigates on its own, which is what a
   * standalone page needs.
   */
  onSuccess?: (id: string) => void;
  /** Adds a dismiss action. An inline page form has nothing to dismiss to. */
  onCancel?: () => void;
}) {
  const router = useRouter();
  const [types, setTypes] = useState<LeaveType[]>([]);
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [blocks, setBlocks] = useState<DraftBlock[]>([emptyBlock()]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // Loaded on mount: the plan form is the only place leave types are needed,
  // and the options are a small registry rather than a paged read.
  useEffect(() => {
    getLeaveTypes()
      .then(setTypes)
      .catch(() =>
        setError("Could not load leave types. Reload the page and try again.")
      );
  }, []);

  function updateBlock(key: string, patch: Partial<DraftBlock>) {
    setBlocks((current) =>
      current.map((block) => (block.key === key ? { ...block, ...patch } : block))
    );
  }

  function removeBlock(key: string) {
    setBlocks((current) =>
      current.length === 1 ? [emptyBlock()] : current.filter((block) => block.key !== key)
    );
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    if (!periodStart || !periodEnd) {
      setError("Choose the period the plan covers.");
      return;
    }

    const incomplete = blocks.find(
      (block) => !block.leave_type_id || !block.start_date || !block.end_date
    );
    if (incomplete) {
      setError("Every block needs a leave type and a date range.");
      return;
    }

    const payload: PlanBlockInput[] = blocks.map((block) => ({
      leave_type_id: block.leave_type_id as number,
      start_date: block.start_date,
      end_date: block.end_date,
    }));

    setLoading(true);
    try {
      const result = await createPlan({
        period_start: periodStart,
        period_end: periodEnd,
        blocks: payload,
      });
      if (!result.ok) {
        setError(result.message);
        setLoading(false);
        return;
      }
      const id = result.data.meta.id;
      if (onSuccess) {
        onSuccess(id);
        return;
      }
      router.push(`/dashboard/plans/${id}`);
      router.refresh();
    } catch {
      setError("The plan could not be saved. Try again.");
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <Card>
        <CardHeader title="Plan period" />
        <Field
          label="Period covered"
          htmlFor="plan-period"
          hint="The window this plan describes. Every block must fall inside it."
        >
          <DateRangePicker
            id="plan-period"
            from={periodStart}
            to={periodEnd}
            onRangeChange={(from, to) => {
              setPeriodStart(from);
              setPeriodEnd(to);
            }}
          />
        </Field>
      </Card>

      <Card>
        <CardHeader
          title="Planned leave"
          icon={<Plus className="h-4 w-4" />}
          actions={
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setBlocks((current) => [...current, emptyBlock()])}
            >
              <Plus className="h-4 w-4" aria-hidden="true" />
              Add block
            </Button>
          }
        />
        <div className="space-y-4">
          {blocks.map((block, index) => (
            <div
              key={block.key}
              className="grid grid-cols-1 gap-3 rounded-lg border border-border-default p-3 md:grid-cols-[1fr_1.4fr_auto] md:items-end"
            >
              <Field label={`Leave type (block ${index + 1})`} htmlFor={`type-${block.key}`}>
                <Select
                  value={block.leave_type_id === null ? "" : String(block.leave_type_id)}
                  onValueChange={(next) =>
                    updateBlock(block.key, {
                      leave_type_id: next ? Number(next) : null,
                    })
                  }
                >
                  <SelectTrigger id={`type-${block.key}`}>
                    <SelectValue placeholder="Select leave type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="">Select leave type</SelectItem>
                    {types.map((type) => (
                      <SelectItem key={type.id} value={String(type.id)}>
                        {type.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>

              <Field
                label={`Dates (block ${index + 1})`}
                htmlFor={`dates-${block.key}`}
              >
                <DateRangePicker
                  id={`dates-${block.key}`}
                  from={block.start_date}
                  to={block.end_date}
                  onRangeChange={(from, to) =>
                    updateBlock(block.key, { start_date: from, end_date: to })
                  }
                />
              </Field>

              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label={`Remove block ${index + 1}`}
                onClick={() => removeBlock(block.key)}
              >
                <Trash2 className="h-4 w-4" aria-hidden="true" />
              </Button>
            </div>
          ))}
        </div>
      </Card>

      {error && <FormError>{error}</FormError>}

      <div className="flex items-center gap-3">
        <Button type="submit" variant="primary" loading={loading}>
          {loading ? "Saving…" : "Save draft"}
        </Button>
        {onCancel && (
          <Button type="button" variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
        )}
        <p className="text-xs text-text-muted">
          A draft is not routed anywhere until you submit it.
        </p>
      </div>
    </form>
  );
}
