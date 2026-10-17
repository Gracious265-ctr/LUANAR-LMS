import { cn } from "@/lib/utils";

/**
 * A single conic progress ring for one leave balance: `used` days swept in the
 * brand colour out of `total`. Built from plain SVG strokes (no chart library)
 * so it renders on the server and needs no layout measurement — the arc is a
 * `stroke-dasharray` on a circle rather than a path.
 *
 * A zero `total` (an employee with no entitlement for that type) renders as an
 * empty track with a `0` centre instead of a divide-by-zero sweep.
 */
export function BalanceRing({
  label,
  used,
  total,
  className,
}: {
  label: string;
  used: number;
  total: number;
  className?: string;
}) {
  const size = 120;
  const stroke = 10;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const ratio = total > 0 ? Math.min(Math.max(used / total, 0), 1) : 0;
  const remaining = Math.max(total - used, 0);

  return (
    <div className={cn("flex flex-col items-center gap-2", className)}>
      <div className="relative" style={{ width: size, height: size }}>
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
          <span className="text-xl font-semibold text-text-primary">
            {remaining}
          </span>
          <span className="text-xs text-text-muted">days left</span>
        </div>
      </div>
      <span className="text-sm font-medium text-text-secondary">{label}</span>
      <span className="text-xs text-text-muted">
        {used} of {total} days used
      </span>
    </div>
  );
}
