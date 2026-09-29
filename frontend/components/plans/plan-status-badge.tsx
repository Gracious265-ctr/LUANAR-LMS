import { Badge } from "@/components/ui/badge";
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
    <Badge size="compact" tone={meta.badgeTone} className={className}>
      <Icon className="size-3" aria-hidden="true" />
      {meta.label}
    </Badge>
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
    <Badge
      size="xs"
      tone={meta.badgeTone}
      className={cn("font-medium whitespace-nowrap", className)}
    >
      <Icon className="size-3" aria-hidden="true" />
      {meta.label}
    </Badge>
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
    <Badge
      size="xs"
      tone={meta.badgeTone}
      className={cn("font-medium whitespace-nowrap", className)}
    >
      <Icon className="size-3" aria-hidden="true" />
      {meta.label}
    </Badge>
  );
}
