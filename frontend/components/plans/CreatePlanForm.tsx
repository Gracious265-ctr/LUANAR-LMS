"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { DateRangePicker } from "@/components/ui/date-picker";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Field } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/toast";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Alert } from "@/components/ui/states";
import { getPlannableLeaveTypes, type LeaveType } from "@/lib/services/leaveTypes";
import { createPlan } from "@/lib/plans/service";

/**
 * Create a Plan (spec 3.5).
 *
 * A single short form, not a multi-step wizard. Only leave types flagged
 * `plannable` are offered, and each one carries its reminder window so the
 * employee can see when the nudge will arrive. An overlapping plan saves
 * anyway — it is only a personal reminder — and the server's note is shown as a
 * dismissible warning rather than a blocker.
 */
export function CreatePlanForm({
  initialLeaveType,
}: {
  /** Pre-selects a leave type, e.g. when re-planning a missed one. */
  initialLeaveType?: number;
}) {
  const router = useRouter();
  const { showToast } = useToast();

  const [types, setTypes] = useState<LeaveType[]>([]);
  const [typesLoading, setTypesLoading] = useState(true);
  const [typesError, setTypesError] = useState<string | null>(null);

  const [leaveType, setLeaveType] = useState<number | null>(initialLeaveType ?? null);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [notes, setNotes] = useState("");

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [warning, setWarning] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await getPlannableLeaveTypes();
        if (cancelled) return;
        setTypes(data);
        setTypesError(null);
      } catch (err) {
        if (cancelled) return;
        setTypesError(
          err instanceof Error ? err.message : "Unable to load leave types."
        );
      } finally {
        if (!cancelled) setTypesLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const selected = types.find((t) => t.id === leaveType) ?? null;
  const canSave =
    leaveType !== null && startDate !== "" && endDate !== "" && !saving;

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (leaveType === null) return;
    setSaving(true);
    setError(null);
    try {
      const plan = await createPlan({
        leave_type: leaveType,
        planned_start_date: startDate,
        planned_end_date: endDate,
        notes: notes.trim(),
      });
      if (plan.overlap_warning) {
        setWarning(plan.overlap_warning);
      } else {
        showToast("Plan saved.");
        router.push("/dashboard/plans");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the plan.");
    } finally {
      setSaving(false);
      setSaved(true);
    }
  }

  if (saved && warning) {
    return (
      <Card>
        <h2 className="text-base font-semibold text-text-primary">Plan saved</h2>
        <Alert tone="info" className="mt-3" onDismiss={() => setWarning(null)}>
          {warning}
        </Alert>
        <div className="mt-4">
          <Button variant="primary" onClick={() => router.push("/dashboard/plans")}>
            Back to My Plans
          </Button>
        </div>
      </Card>
    );
  }

  return (
    <Card>
      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <h2 className="text-base font-semibold text-text-primary">Create a Plan</h2>
          <p className="mt-1 text-sm text-text-secondary">
            Save a leave type and dates ahead of time. Nothing is submitted — when the
            date nears, we&apos;ll remind you to apply.
          </p>
        </div>

        <Field
          label="Leave type"
          htmlFor="plan-leave-type"
          error={typesError}
          hint={
            selected?.planNoticeDays != null
              ? `A reminder fires ${selected.planNoticeDays} days before the start date.`
              : undefined
          }
        >
          <Select
            value={leaveType === null ? "" : String(leaveType)}
            onValueChange={(next) => setLeaveType(next ? Number(next) : null)}
            disabled={typesLoading}
          >
            <SelectTrigger id="plan-leave-type" aria-label="Leave type">
              <SelectValue
                placeholder={typesLoading ? "Loading…" : "Select a leave type"}
              />
            </SelectTrigger>
            <SelectContent>
              {types.map((t) => (
                <SelectItem key={t.id} value={String(t.id)}>
                  {t.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>

        <Field label="Planned dates" htmlFor="plan-dates">
          <DateRangePicker
            id="plan-dates"
            from={startDate}
            to={endDate}
            onRangeChange={(from, to) => {
              setStartDate(from);
              setEndDate(to);
            }}
          />
        </Field>

        <Field label="Notes" htmlFor="plan-notes" hint="Optional.">
          <Textarea
            id="plan-notes"
            name="plan-notes"
            rows={3}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Anything you want to remember about this leave"
          />
        </Field>

        {error && (
          <p role="alert" className="text-sm text-status-rejected">
            {error}
          </p>
        )}

        <div className="flex items-center gap-3">
          <Button
            type="submit"
            variant="primary"
            loading={saving}
            disabled={!canSave}
            title={
              canSave
                ? "Save the plan"
                : "Choose a leave type and both dates first"
            }
          >
            {saving ? "Saving…" : "Save plan"}
          </Button>
          <Button
            type="button"
            variant="secondary"
            onClick={() => router.push("/dashboard/plans")}
          >
            Cancel
          </Button>
        </div>

        {!typesLoading && types.length === 0 && (
          <p className="text-sm text-text-muted">
            No plannable leave types are available yet.
          </p>
        )}
      </form>
    </Card>
  );
}
