import { cn } from "@/lib/utils";

import { formatDateTime } from "@/lib/approvals/format";
import type { DecisionAction } from "@/lib/approvals/types";

export const ACTION_BADGE_CLASSES: Record<DecisionAction, string> = {
  approve: "bg-status-approved-subtle text-status-approved",
  reject: "bg-status-rejected-subtle text-status-rejected",
  return_for_correction: "bg-status-correction-subtle text-status-correction",
};

export function ActionBadge({
  action,
  className,
}: {
  action: DecisionAction;
  className?: string;
}) {
  const labels: Record<DecisionAction, string> = {
    approve: "Approved",
    reject: "Rejected",
    return_for_correction: "Returned for correction",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold",
        ACTION_BADGE_CLASSES[action],
        className
      )}
    >
      {labels[action]}
    </span>
  );
}

export function ResubmissionBadge({ cycle }: { cycle: number }) {
  if (cycle <= 1) return null;
  return (
    <span className="inline-flex items-center rounded-full bg-surface-muted px-3 py-1 text-xs font-semibold text-text-secondary">
      Resubmission #{cycle - 1}
    </span>
  );
}

export function Card({
  title,
  icon,
  actions,
  children,
  className,
}: {
  title: string;
  icon?: React.ReactNode;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cn(
        "rounded-xl border border-border-default bg-surface-card p-5 shadow-subtle",
        className
      )}
    >
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-base font-semibold text-text-primary">
          {icon && (
            <span className="text-brand-primary" aria-hidden="true">
              {icon}
            </span>
          )}
          {title}
        </h2>
        {actions}
      </div>
      {children}
    </section>
  );
}

export function DataRow({
  label,
  value,
  valueClassName,
}: {
  label: string;
  value: React.ReactNode;
  valueClassName?: string;
}) {
  return (
    <div className="flex items-start justify-between gap-4 py-2">
      <dt className="shrink-0 text-sm text-text-secondary">{label}</dt>
      <dd
        className={cn(
          "min-w-0 text-right text-sm font-medium text-text-primary",
          valueClassName
        )}
      >
        {value}
      </dd>
    </div>
  );
}

export function DecidedAt({ value }: { value: string }) {
  return (
    <time dateTime={value} className="text-xs text-text-muted">
      {formatDateTime(value)}
    </time>
  );
}