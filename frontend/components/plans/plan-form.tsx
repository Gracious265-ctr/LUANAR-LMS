"use client";

import { CalendarRange, Plus, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import type { LeaveType } from "@/lib/leave-rules";
import { createPlan } from "@/lib/plans/service";
import type { PlanInputBlock } from "@/lib/plans/types";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { FormError } from "@/components/ui/form-error";

interface PlanBlockDraft {
  key: number;
  leave_type_id: string;
  start_date: string;
  end_date: string;
}

export function PlanForm({ leaveTypes }: { leaveTypes: LeaveType[] }) {
  const router = useRouter();
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [blocks, setBlocks] = useState<PlanBlockDraft[]>([
    { key: 1, leave_type_id: "", start_date: "", end_date: "" },
  ]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [nextKey, setNextKey] = useState(2);

  function addBlock() {
    setBlocks((current) => [
      ...current,
      { key: nextKey, leave_type_id: "", start_date: "", end_date: "" },
    ]);
    setNextKey((n) => n + 1);
  }

  function removeBlock(key: number) {
    setBlocks((current) =>
      current.length > 1 ? current.filter((block) => block.key !== key) : current
    );
  }

  function updateBlock(
    key: number,
    patch: Partial<PlanBlockDraft>
  ) {
    setBlocks((current) =>
      current.map((block) => (block.key === key ? { ...block, ...patch } : block))
    );
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError("");

    const inputBlocks: PlanInputBlock[] = blocks.map((block) => ({
      leave_type_id: Number(block.leave_type_id),
      start_date: block.start_date,
      end_date: block.end_date,
    }));

    if (
      inputBlocks.some(
        (block) =>
          !Number.isInteger(block.leave_type_id) || block.leave_type_id < 1
      )
    ) {
      setError("Choose a leave type for every block.");
      return;
    }

    setLoading(true);
    try {
      const result = await createPlan({
        period_start: periodStart,
        period_end: periodEnd,
        blocks: inputBlocks,
      });
      if (result.ok) {
        router.push(`/dashboard/plans/${result.data.meta.id}`);
        router.refresh();
      } else {
        setError(result.message);
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Field
          label="Period start"
          htmlFor="period_start"
          hint="The plan covers one financial year."
        >
          <Input
            id="period_start"
            name="period_start"
            type="date"
            required
            value={periodStart}
            onChange={(e) => setPeriodStart(e.target.value)}
          />
        </Field>
        <Field label="Period end" htmlFor="period_end">
          <Input
            id="period_end"
            name="period_end"
            type="date"
            required
            value={periodEnd}
            onChange={(e) => setPeriodEnd(e.target.value)}
          />
        </Field>
      </div>

      <div>
        <div className="mb-3 flex items-center justify-between">
          <h3 className="flex items-center gap-2 text-base font-semibold text-text-primary">
            <CalendarRange className="size-4 text-brand-primary" />
            Leave blocks
          </h3>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={addBlock}
          >
            <Plus className="size-4" />
            Add block
          </Button>
        </div>

        <div className="space-y-3">
          {blocks.map((block) => (
            <div
              key={block.key}
              className="grid grid-cols-1 items-end gap-3 rounded-lg border border-border-default bg-surface-page p-3 md:grid-cols-[1fr_1fr_1fr_auto]"
            >
              <Field label="Leave type" htmlFor={`block-type-${block.key}`}>
                <Select
                  value={block.leave_type_id}
                  onValueChange={(next) =>
                    updateBlock(block.key, { leave_type_id: next })
                  }
                >
                  <SelectTrigger
                    id={`block-type-${block.key}`}
                    aria-label="Leave type"
                  >
                    <SelectValue placeholder="Select leave type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="">Select leave type</SelectItem>
                    {leaveTypes.map((type) => (
                      <SelectItem key={type.id} value={String(type.id)}>
                        {type.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>
              <Field label="Start date" htmlFor={`block-start-${block.key}`}>
                <Input
                  id={`block-start-${block.key}`}
                  type="date"
                  value={block.start_date}
                  onChange={(e) =>
                    updateBlock(block.key, { start_date: e.target.value })
                  }
                />
              </Field>
              <Field label="End date" htmlFor={`block-end-${block.key}`}>
                <Input
                  id={`block-end-${block.key}`}
                  type="date"
                  value={block.end_date}
                  onChange={(e) =>
                    updateBlock(block.key, { end_date: e.target.value })
                  }
                />
              </Field>
              <Button
                type="button"
                onClick={() => removeBlock(block.key)}
                disabled={blocks.length === 1}
                aria-label="Remove block"
                variant="ghost"
                size="icon"
                className="size-9"
              >
                <Trash2 className="size-4" />
              </Button>
            </div>
          ))}
        </div>
      </div>

      {error && <FormError>{error}</FormError>}

      <div className="flex items-center gap-3">
        <Button type="submit" variant="primary" loading={loading}>
          {loading ? "Creating..." : "Create plan"}
        </Button>
        <Button
          type="button"
          variant="secondary"
          onClick={() => router.push("/dashboard/plans")}
        >
          Cancel
        </Button>
      </div>
    </form>
  );
}