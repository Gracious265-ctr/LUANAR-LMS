import { cn } from "@/lib/utils";
import { ACTION_META, STATUS_META } from "@/lib/approvals/labels";
import type { StatusMeta } from "@/lib/approvals/labels";
import type { ApprovalAction, ApprovalStatus } from "@/lib/approvals/types";

const FALLBACK_META: StatusMeta = {
  label: "Submitted",
  icon: STATUS_META.submitted.icon,
  badgeClass: STATUS_META.submitted.badgeClass,
  textClass: STATUS_META.submitted.textClass,
  dotClass: STATUS_META.submitted.dotClass,
};

export function StatusBadge({
  status,
  className,
}: {
  status: ApprovalStatus;
  className?: string;
}) {
  const meta = STATUS_META[status] ?? FALLBACK_META;
  const Icon = meta.icon;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold",
        meta.badgeClass,
        className
      )}
    >
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      {meta.label}
    </span>
  );
}

export function ActionBadge({
  action,
  className,
}: {
  action: ApprovalAction;
  className?: string;
}) {
  const meta = ACTION_META[action];
  const Icon = meta.icon;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold",
        meta.badgeClass,
        className
      )}
    >
      <Icon className="h-3 w-3" aria-hidden="true" />
      {meta.label}
    </span>
  );
}