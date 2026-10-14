import { Badge } from "@/components/ui/badge";
import { ACTION_META, STATUS_META } from "@/lib/approvals/labels";
import type { StatusMeta } from "@/lib/approvals/labels";
import type { ApprovalAction, ApprovalStatus } from "@/lib/approvals/types";

const FALLBACK_META: StatusMeta = {
  label: "Submitted",
  icon: STATUS_META.submitted.icon,
  badgeTone: STATUS_META.submitted.badgeTone,
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
    <Badge tone={meta.badgeTone} className={className}>
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      {meta.label}
    </Badge>
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
    <Badge size="sm" tone={meta.badgeTone} className={className}>
      <Icon className="h-3 w-3" aria-hidden="true" />
      {meta.label}
    </Badge>
  );
}
