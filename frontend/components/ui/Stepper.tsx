"use client";

import { useState } from "react";
import { Check, Clock, Minus, X } from "lucide-react";

import { formatDateTime } from "@/lib/format";
import { STATUS_TEXT } from "@/lib/status-styles";
import { Avatar } from "@/components/ui/Avatar";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

/**
 * The status of one step (spec 2.1). Six values, defined once here and reused
 * by every surface that renders a sequence — the component never invents a
 * status, and no integration redefines these colours locally.
 */
export type StepStatus =
  | "completed"
  | "current"
  | "pending"
  | "skipped"
  | "blocked"
  | "error";

/**
 * One node of any ordered process (spec 2.1). This is the whole contract:
 * the component has zero awareness of leave applications, documents or org
 * units — each integration maps its own data into `Step[]`.
 */
export interface Step {
  id: string;
  /** Primary text — a role, a stage name, a step name. */
  label: string;
  /** Secondary text — a unit name, a person, a detail. */
  sublabel?: string;
  status: StepStatus;
  /** The person associated with this step, if any. */
  actor?: { id: string; name: string } | null;
  /** When this step was completed/decided. */
  timestamp?: string | null;
  /** Expandable text — a comment, a reason, extra context. */
  detail?: string | null;
  /** Shows an "Acting" badge next to the actor (approval-chain specific). */
  isActing?: boolean;
}

export interface StepperProps {
  steps: Step[];
  /** "auto" = horizontal desktop, vertical mobile (default). */
  orientation?: "horizontal" | "vertical" | "auto";
  size?: "sm" | "md";
  /** false where there is no person per step (e.g. an onboarding checklist). */
  showAvatars?: boolean;
  /**
   * When provided, the node of each jumpable step becomes a button that calls
   * this with the step. Used by flows that let the user step back to an earlier
   * point (the leave application wizard); approval chains pass nothing and stay
   * read-only.
   */
  onStepClick?: (step: Step) => void;
  /** Which steps may be jumped to. Defaults to completed and current. */
  isStepClickable?: (step: Step) => boolean;
  /** Accessible name for a jumpable node. Defaults to the step label. */
  stepAriaLabel?: (step: Step) => string;
}

const STATUS_ICON = {
  completed: Check,
  current: Clock,
  pending: Clock,
  skipped: Minus,
  blocked: Minus,
  error: X,
} as const;

/** The node itself, when there is no avatar to show. */
const NODE_STYLE: Record<StepStatus, string> = {
  completed: "border-2 border-brand-primary bg-brand-primary text-white",
  current:
    "border-2 border-brand-primary bg-brand-primary-subtle text-brand-primary",
  pending: "border border-border-strong bg-surface-card text-text-muted",
  skipped: "border-2 border-dashed border-border-strong text-text-muted",
  blocked:
    "border-2 border-status-rejected/40 bg-status-rejected-subtle " +
    STATUS_TEXT.rejected,
  error:
    "border-2 border-status-rejected/40 bg-status-rejected-subtle " +
    STATUS_TEXT.rejected,
};

/** The line leaving a step: brand once the flow has settled through it. */
function outgoingLine(status: StepStatus): string {
  if (status === "completed") return "border-brand-primary";
  if (status === "skipped") return "border-border-strong border-dashed";
  if (status === "blocked" || status === "error")
    return "border-status-rejected/40";
  return "border-border-strong";
}

function isTerminalProblem(status: StepStatus): boolean {
  return status === "blocked" || status === "error";
}

/**
 * One stepper for every ordered sequence (spec 2). Horizontal on desktop and
 * vertical on mobile are the same DOM tree switched with breakpoint classes;
 * `orientation` only changes flex-direction and connector placement, never the
 * step markup (spec 2.3). Nodes are never compressed below a legible minimum.
 */
export function Stepper({
  steps,
  orientation = "auto",
  size = "md",
  showAvatars = true,
  onStepClick,
  isStepClickable,
  stepAriaLabel,
}: StepperProps) {
  const [openId, setOpenId] = useState<string | null>(null);

  if (steps.length === 0) return null;

  const auto = orientation === "auto";
  const horizontal = orientation === "horizontal";
  const compact = size === "sm";

  const listClass = cn(
    "flex",
    auto ? "flex-col md:flex-row" : horizontal ? "flex-row" : "flex-col"
  );

  const stepClass = cn(
    "relative flex min-w-0 items-start gap-3",
    auto
      ? "md:flex-1 md:flex-col md:items-center md:gap-0 md:text-center"
      : horizontal
        ? "flex-1 flex-col items-center gap-0 text-center"
        : ""
  );

  return (
    <ol className={listClass}>
      {steps.map((step, index) => {
        const isLast = index === steps.length - 1;
        const expandable = Boolean(step.detail);
        const open = expandable && openId === step.id;
        const nodeSize = compact ? "h-6 w-6" : "h-8 w-8";
        const Icon = STATUS_ICON[step.status];
        const showAvatar = showAvatars && Boolean(step.actor);
        const clickable = Boolean(
          onStepClick &&
            (isStepClickable
              ? isStepClickable(step)
              : step.status === "completed" || step.status === "current")
        );
        const nodeWrapperClass = cn(
          "relative z-10 shrink-0",
          horizontal && "self-center",
          auto && "md:self-center"
        );

        const node =
          showAvatar ? (
            <span className="relative inline-flex shrink-0 rounded-full">
              {step.status === "current" && (
                <span
                  aria-hidden="true"
                  className="pointer-events-none absolute -inset-1 animate-pulse rounded-full bg-brand-primary/15 motion-reduce:animate-none"
                />
              )}
              <Avatar
                name={step.actor!.name}
                userId={step.actor!.id}
                size={compact ? "sm" : "md"}
                className={cn(
                  "relative",
                  step.status === "current" && "ring-2 ring-brand-primary",
                  (step.status === "pending" ||
                    step.status === "skipped" ||
                    isTerminalProblem(step.status)) &&
                    "opacity-80"
                )}
              />
              {isTerminalProblem(step.status) && (
                <span
                  className="absolute -bottom-0.5 -right-0.5 grid h-[18px] w-[18px] place-content-center rounded-full border-2 border-surface-card bg-status-rejected text-white"
                >
                  <Icon className="h-2.5 w-2.5" aria-hidden="true" />
                </span>
              )}
            </span>
          ) : (
            <span
              aria-hidden="true"
              className={cn(
                "grid shrink-0 place-content-center rounded-full",
                nodeSize,
                NODE_STYLE[step.status]
              )}
            >
              <Icon className={compact ? "h-3 w-3" : "h-4 w-4"} />
            </span>
          );

        return (
          <li
            key={step.id}
            data-state={step.status}
            aria-current={step.status === "current" ? "step" : undefined}
            className={cn(
              stepClass,
              !isLast && "pb-8",
              !isLast && (auto ? "md:pb-0" : horizontal && "pb-0")
            )}
          >
            {!isLast && (
              <>
                {!horizontal && (
                  <span
                    aria-hidden="true"
                    className={cn(
                      "absolute bottom-0 left-[15px] w-0 border-l-2",
                      compact && "left-[11px]",
                      auto && "md:hidden",
                      outgoingLine(step.status)
                    )}
                  />
                )}
                {(horizontal || auto) && (
                  <span
                    aria-hidden="true"
                    className={cn(
                      "absolute -right-1/2 left-1/2 top-[15px] h-0 border-t-2",
                      compact && "top-[11px]",
                      auto && "hidden md:block",
                      outgoingLine(step.status)
                    )}
                  />
                )}
              </>
            )}

            {clickable ? (
              <button
                type="button"
                aria-label={stepAriaLabel ? stepAriaLabel(step) : step.label}
                onClick={() => onStepClick?.(step)}
                className={cn(
                  nodeWrapperClass,
                  "inline-flex cursor-pointer rounded-full transition-opacity hover:opacity-80 focus-ring"
                )}
              >
                {node}
              </button>
            ) : expandable ? (
              <button
                type="button"
                aria-expanded={open}
                aria-label={`${step.label} details`}
                onClick={() => setOpenId(open ? null : step.id)}
                className={cn(
                  "relative z-10 inline-flex shrink-0 cursor-pointer rounded-full transition-opacity hover:opacity-80 focus-ring",
                  horizontal && "self-center",
                  auto && "md:self-center"
                )}
              >
                {node}
              </button>
            ) : (
              <span className={nodeWrapperClass}>{node}</span>
            )}

            <div
              className={cn(
                "min-w-0 flex-1",
                !compact && "mt-2",
                (horizontal || auto) && "md:mt-2 md:w-full md:flex-none"
              )}
            >
              <h3
                className={cn(
                  "text-sm font-semibold",
                  step.status === "pending" || step.status === "skipped"
                    ? "text-text-muted"
                    : "text-text-primary"
                )}
              >
                {step.label}
              </h3>

              {!compact && step.actor && (
                <p className="mt-0.5 text-sm text-text-secondary">
                  {step.actor.name}
                  {step.isActing && (
                    <Badge
                      size="sm"
                      tone="neutral"
                      className="ml-1.5 align-middle font-medium"
                    >
                      Acting
                    </Badge>
                  )}
                </p>
              )}

              {!compact && step.sublabel && (
                <p
                  className={cn(
                    "mt-0.5 text-xs",
                    isTerminalProblem(step.status)
                      ? STATUS_TEXT.rejected
                      : "text-text-muted"
                  )}
                >
                  {step.sublabel}
                </p>
              )}

              {!compact && step.status === "current" && !step.sublabel && (
                <p className="mt-0.5 text-xs text-text-muted">In progress</p>
              )}

              {!compact && step.status === "completed" && step.timestamp && (
                <p className="mt-0.5 text-xs text-text-muted">
                  {formatDateTime(step.timestamp)}
                </p>
              )}

              {open && step.detail && (
                <div
                  className={cn(
                    "mt-2 rounded-r-lg border-l-2 px-3 py-2 text-left text-sm break-words whitespace-pre-line",
                    isTerminalProblem(step.status)
                      ? cn(
                          "border-status-rejected bg-status-rejected-subtle",
                          STATUS_TEXT.rejected
                        )
                      : "border-border-strong bg-surface-subtle text-text-secondary"
                  )}
                >
                  {step.detail}
                </div>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
