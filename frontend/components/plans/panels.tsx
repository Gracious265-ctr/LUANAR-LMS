import { cn } from "@/lib/utils";

/** The plan's blocks as a titled panel. */
export function BlocksPanel({
  title = "Planned leave",
  actions,
  children,
  className,
}: {
  title?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("space-y-3", className)}>
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-base font-semibold text-text-primary">{title}</h2>
        {actions}
      </div>
      {children}
    </section>
  );
}

/** A label/value row. `value` may be empty, which renders an em dash. */
export function DetailRow({
  label,
  value,
  className,
}: {
  label: string;
  value: React.ReactNode;
  className?: string;
}) {
  const empty =
    value === null ||
    value === undefined ||
    value === "" ||
    value === false;
  return (
    <div className={cn("flex flex-wrap items-baseline justify-between gap-2 py-1.5", className)}>
      <dt className="text-sm text-text-secondary">{label}</dt>
      <dd className="text-sm font-medium text-text-primary">
        {empty ? "—" : value}
      </dd>
    </div>
  );
}

/**
 * The approval chain, one row per section.
 *
 * An unclaimed stage lists its candidates rather than naming one person,
 * because whoever acts first claims the stage: naming a single "current
 * approver" would be a guess whenever a section has more than one member.
 */
export function StageChain({
  stages,
}: {
  stages: {
    stage_order: number;
    role_label: string;
    status: "waiting" | "pending" | "approved" | "rejected";
    is_claimed: boolean;
    approver_name: string;
    eligible_approvers: { name: string }[];
    is_final: boolean;
  }[];
}) {
  return (
    <ol className="space-y-2" data-testid="plan-stage-chain">
      {stages.map((stage) => (
        <li
          key={stage.stage_order}
          className="flex items-start gap-3 rounded-lg border border-border-default bg-surface-card p-3"
        >
          <span className="mt-0.5 grid h-6 w-6 shrink-0 place-content-center rounded-full bg-surface-muted text-xs font-semibold text-text-secondary">
            {stage.stage_order}
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium text-text-primary">
              {stage.role_label}
              {stage.is_final && (
                <span className="ml-2 text-xs font-normal text-text-muted">
                  final step
                </span>
              )}
            </p>
            <p className="mt-0.5 text-xs text-text-secondary">
              {stage.is_claimed
                ? stage.approver_name
                : stage.eligible_approvers.length > 0
                  ? `Any of ${stage.eligible_approvers.map((a) => a.name).join(", ")}`
                  : "No approver available"}
            </p>
          </div>
        </li>
      ))}
    </ol>
  );
}
