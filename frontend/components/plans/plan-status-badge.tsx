import {
  BLOCK_STATUS_META,
  PLAN_STATUS_META,
  STAGE_STATUS_META,
} from "@/lib/plans/labels";
import type { BlockStatus, PlanStatus, StageStatus } from "@/lib/plans/types";
import { cn } from "@/lib/utils";

export function PlanStatusBadge({
  status,
  className,
}: {
  status: PlanStatus;
  className?: string;
}) {
  const meta = PLAN_STATUS_META[status];
  const Icon = meta.icon;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium",
        meta.badgeClass,
        className
      )}
    >
      <Icon className="size-3" />
      {meta.label}
    </span>
  );
}

export function BlockStatusBadge({
  status,
  className,
}: {
  status: BlockStatus;
  className?: string;
}) {
  const meta = BLOCK_STATUS_META[status];
  const Icon = meta.icon;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-medium",
        meta.badgeClass,
        className
      )}
    >
      <Icon className="size-3" />
      {meta.label}
    </span>
  );
}

export function StageStatusBadge({
  status,
  className,
}: {
  status: StageStatus;
  className?: string;
}) {
  const meta = STAGE_STATUS_META[status];
  const Icon = meta.icon;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-medium",
        meta.badgeClass,
        className
      )}
    >
      <Icon className="size-3" />
      {meta.label}
    </span>
  );
}