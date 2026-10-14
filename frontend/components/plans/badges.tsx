import { Badge } from "@/components/ui/badge";

import {
  ACTION_META,
  BLOCK_STATUS_META,
  PLAN_STATUS_META,
  STAGE_STATUS_META,
} from "@/lib/plans/labels";
import type {
  BlockStatus,
  PlanAction,
  PlanStageStatus,
  PlanStatus,
} from "@/lib/plans/types";

/**
 * Every plan status pill renders through the shared `Badge` primitive and the
 * label maps, so a tone is never hand-written here and a new status only needs
 * one entry in `lib/plans/labels.ts`.
 */
export function PlanStatusBadge({
  status,
  className,
}: {
  status: PlanStatus;
  className?: string;
}) {
  const meta = PLAN_STATUS_META[status];
  if (!meta) return null;
  const Icon = meta.icon;
  return (
    <Badge size="compact" tone={meta.badgeTone} className={className}>
      <Icon className="h-3 w-3" aria-hidden="true" />
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
  if (!meta) return null;
  const Icon = meta.icon;
  return (
    <Badge size="compact" tone={meta.badgeTone} className={className}>
      <Icon className="h-3 w-3" aria-hidden="true" />
      {meta.label}
    </Badge>
  );
}

export function StageStatusBadge({
  status,
  className,
}: {
  status: PlanStageStatus;
  className?: string;
}) {
  const meta = STAGE_STATUS_META[status];
  if (!meta) return null;
  const Icon = meta.icon;
  return (
    <Badge size="compact" tone={meta.badgeTone} className={className}>
      <Icon className="h-3 w-3" aria-hidden="true" />
      {meta.label}
    </Badge>
  );
}

export function ActionBadge({
  action,
  className,
}: {
  action: PlanAction;
  className?: string;
}) {
  const meta = ACTION_META[action];
  if (!meta) return null;
  const Icon = meta.icon;
  return (
    <Badge size="compact" tone={meta.badgeTone} className={className}>
      <Icon className="h-3 w-3" aria-hidden="true" />
      {meta.label}
    </Badge>
  );
}
