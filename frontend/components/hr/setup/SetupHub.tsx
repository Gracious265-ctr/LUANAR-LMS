"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  CalendarPlus,
  Check,
  ChevronRight,
  CircleAlert,
  Sparkles,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";
import {
  SETUP_STEPS,
  presetObjectLabel,
  type ApplyResult,
  type SetupStatus,
} from "@/lib/setup";
import {
  applyDefaults,
  previewDefaults,
  rolloverFinancialYear,
} from "@/lib/setup-client";

type ApplyPhase = "loading" | "ready" | "applying" | "error";

/**
 * The setup spine, in order, with the two writes that skip the hand-work.
 *
 * Steps are judged on live data the server computed, so an install that is
 * already configured simply shows as complete instead of asking HR to repeat it.
 * "Apply defaults" is offered as a preview first: the dialog shows exactly what
 * the run would create (nothing, if everything is already present) before HR
 * commits, which is what lets the button be safe to press.
 */
export function SetupHub({ status }: { status: SetupStatus }) {
  const router = useRouter();
  const { showToast } = useToast();

  const doneCount = SETUP_STEPS.filter((step) => status.steps[step.key].done).length;
  const hasYear = status.steps.financial_year.done;

  const [applyOpen, setApplyOpen] = useState(false);
  const [applyPhase, setApplyPhase] = useState<ApplyPhase>("loading");
  const [applyResult, setApplyResult] = useState<ApplyResult | null>(null);
  const [applyError, setApplyError] = useState("");

  const [rolloverOpen, setRolloverOpen] = useState(false);
  const [rolloverBusy, setRolloverBusy] = useState(false);
  const [rolloverError, setRolloverError] = useState("");

  async function openApply() {
    setApplyOpen(true);
    setApplyPhase("loading");
    setApplyError("");
    setApplyResult(null);
    try {
      setApplyResult(await previewDefaults());
      setApplyPhase("ready");
    } catch (err) {
      setApplyError(
        err instanceof Error ? err.message : "Could not preview the defaults."
      );
      setApplyPhase("error");
    }
  }

  async function runApply() {
    setApplyPhase("applying");
    setApplyError("");
    try {
      const result = await applyDefaults();
      setApplyResult(result);
      setApplyOpen(false);
      showToast(
        result.total_created > 0
          ? "Default configuration applied."
          : "Everything is already configured."
      );
      router.refresh();
    } catch (err) {
      setApplyError(
        err instanceof Error ? err.message : "Could not apply the defaults."
      );
      setApplyPhase("error");
    }
  }

  async function runRollover() {
    setRolloverBusy(true);
    setRolloverError("");
    try {
      const result = await rolloverFinancialYear();
      setRolloverOpen(false);
      showToast(
        result.total_created > 0
          ? "New financial year opened."
          : "The next financial year is already open."
      );
      router.refresh();
    } catch (err) {
      setRolloverError(
        err instanceof Error ? err.message : "Could not open a new financial year."
      );
    } finally {
      setRolloverBusy(false);
    }
  }

  return (
    <section
      aria-labelledby="setup-heading"
      className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2
            id="setup-heading"
            className="text-lg font-semibold tracking-tight text-text-primary"
          >
            {status.complete ? "You're set up" : "Get started"}
          </h2>
          <p className="mt-1 text-sm text-text-secondary">
            {status.complete
              ? "Every step is in place. You can keep fine-tuning below whenever you need to."
              : "Work down these five steps to make the leave system usable. The first three can be filled in for you."}
          </p>
        </div>
        <span className="rounded-full bg-surface-muted px-3 py-1 text-xs font-semibold text-text-secondary">
          {doneCount} of {SETUP_STEPS.length} done
        </span>
      </div>

      <ol className="mt-5 space-y-1">
        {SETUP_STEPS.map((step, index) => {
          const state = status.steps[step.key];
          return (
            <li key={step.key}>
              <Link
                href={step.href}
                className="group flex items-center gap-3 rounded-lg px-2 py-2.5 transition-colors hover:bg-surface-hover"
              >
                <span
                  className={cn(
                    "grid size-7 shrink-0 place-content-center rounded-full text-xs font-semibold",
                    state.done
                      ? "bg-status-approved-subtle text-status-approved"
                      : "bg-surface-muted text-text-muted"
                  )}
                  aria-hidden="true"
                >
                  {state.done ? <Check className="size-4" /> : index + 1}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-2">
                    <span className="text-sm font-medium text-text-primary">
                      {step.title}
                    </span>
                    {state.done && state.count > 1 ? (
                      <span className="text-xs text-text-muted">
                        {state.count}
                      </span>
                    ) : null}
                  </span>
                  <span className="block text-sm text-text-secondary">
                    {step.description}
                  </span>
                </span>
                <ChevronRight
                  className="size-4 shrink-0 text-text-muted transition-transform group-hover:translate-x-0.5"
                  aria-hidden="true"
                />
              </Link>
            </li>
          );
        })}
      </ol>

      <div className="mt-5 flex flex-wrap items-center gap-2 border-t border-border-subtle pt-4">
        <Button variant="primary" size="sm" onClick={openApply}>
          <Sparkles className="h-4 w-4" aria-hidden="true" />
          Apply default configuration
        </Button>
        {hasYear ? (
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              setRolloverError("");
              setRolloverOpen(true);
            }}
          >
            <CalendarPlus className="h-4 w-4" aria-hidden="true" />
            Start a new financial year
          </Button>
        ) : null}
      </div>

      <ApplyDefaultsDialog
        open={applyOpen}
        onOpenChange={setApplyOpen}
        phase={applyPhase}
        result={applyResult}
        error={applyError}
        onConfirm={runApply}
      />

      <Dialog open={rolloverOpen} onOpenChange={setRolloverOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Open the next financial year?</DialogTitle>
            <DialogDescription>
              This opens the following 1 July – 30 June year, makes it the active
              one, and carries your leave rules forward. Entitlements and holidays
              are not copied. Nothing already recorded is changed.
            </DialogDescription>
          </DialogHeader>
          {rolloverError ? (
            <p role="alert" className="text-sm text-status-rejected">
              {rolloverError}
            </p>
          ) : null}
          <DialogFooter>
            <Button
              variant="secondary"
              onClick={() => setRolloverOpen(false)}
              disabled={rolloverBusy}
            >
              Cancel
            </Button>
            <Button variant="primary" onClick={runRollover} loading={rolloverBusy}>
              Open new year
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}

function ApplyDefaultsDialog({
  open,
  onOpenChange,
  phase,
  result,
  error,
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  phase: ApplyPhase;
  result: ApplyResult | null;
  error: string;
  onConfirm: () => void;
}) {
  const created = result
    ? Object.entries(result.created).filter(([, count]) => count > 0)
    : [];
  const nothingToDo = result !== null && created.length === 0;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Apply the default configuration</DialogTitle>
          <DialogDescription>
            This fills in anything that is missing — the financial year, leave
            types and rules, grade entitlements, and the six approver roles. It
            never changes what already exists, so it is safe to run at any time.
          </DialogDescription>
        </DialogHeader>

        {phase === "loading" ? (
          <p className="text-sm text-text-secondary">Checking what is missing…</p>
        ) : null}

        {phase === "error" ? (
          <p role="alert" className="text-sm text-status-rejected">
            {error}
          </p>
        ) : null}

        {phase !== "loading" && phase !== "error" && result ? (
          nothingToDo ? (
            <p className="flex items-center gap-2 text-sm text-status-approved">
              <Check className="h-4 w-4" aria-hidden="true" />
              Everything is already configured — there is nothing to add.
            </p>
          ) : (
            <div className="text-sm">
              <p className="mb-2 text-text-secondary">This will create:</p>
              <ul className="space-y-1">
                {created.map(([key, count]) => (
                  <li key={key} className="flex items-center gap-2 text-text-primary">
                    <CircleAlert
                      className="h-3.5 w-3.5 text-status-pending"
                      aria-hidden="true"
                    />
                    {count} {presetObjectLabel(key)}
                    {count === 1 ? "" : "s"}
                  </li>
                ))}
              </ul>
            </div>
          )
        ) : null}

        <DialogFooter>
          <Button
            variant="secondary"
            onClick={() => onOpenChange(false)}
            disabled={phase === "applying"}
          >
            {nothingToDo ? "Close" : "Cancel"}
          </Button>
          {!nothingToDo ? (
            <Button
              variant="primary"
              onClick={onConfirm}
              loading={phase === "applying"}
              disabled={phase === "loading" || phase === "error" || !result}
            >
              Apply
            </Button>
          ) : null}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
