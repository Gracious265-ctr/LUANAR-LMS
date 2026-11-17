import { cn } from "@/lib/utils";

/**
 * A single conic progress ring for one leave balance: `used` days swept in the
 * brand colour out of `total`. Built from plain SVG strokes (no chart library)
 * so it renders on the server and needs no layout measurement — the arc is a
 * `stroke-dasharray` on a circle rather than a path.
 *
 * The label and the used/total caption sit beside the dial rather than beneath
 * it, so the block can be dropped into a card without making that card taller
 * than the stat cards beside it. `size` shrinks the dial to that footprint; the
 * stroke thins with it so the ring keeps its proportions.
 *
 * A zero `total` (an employee with no entitlement for that type) renders as an
 * empty track with a `0` centre instead of a divide-by-zero sweep.
 */
export function BalanceRing({
  label,
  used,
  total,
  size = 120,
  className,
}: {
  label: string;
  used: number;
  total: number;
  size?: number;
  className?: string;
}) {
  const stroke = size <= 96 ? 8 : 10;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const ratio = total > 0 ? Math.min(Math.max(used / total, 0), 1) : 0;
  const remaining = Math.max(total - used, 0);

  return (
    <div className={cn("flex items-center gap-4", className)}>
      <div className="relative shrink-0" style={{ width: size, height: size }}>
        <svg
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
          role="img"
          aria-label={`${label}: ${used} of ${total} days used`}
          className="-rotate-90"
        >
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            strokeWidth={stroke}
            stroke="var(--color-muted)"
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            strokeWidth={stroke}
            strokeLinecap="round"
            stroke="var(--color-primary)"
            strokeDasharray={circumference}
            strokeDashoffset={circumference * (1 - ratio)}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-xl font-semibold leading-none tabular-nums text-text-primary">
            {remaining}
          </span>
          <span className="mt-0.5 text-[10px] leading-none text-text-muted">
            days left
          </span>
        </div>
      </div>
      <div className="min-w-0">
        <p className="text-sm font-medium text-text-secondary">{label}</p>
        <p className="mt-0.5 text-xs text-text-muted">
          {used} of {total} days used
        </p>
      </div>
    </div>
  );
}
