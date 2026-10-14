import { cn } from "@/lib/utils";

interface BalanceRingProps {
  /** Days already consumed from the entitlement. */
  used: number;
  /** Gross entitlement the ring is measured against. */
  total: number;
  /** Human label for the balance, e.g. "Annual leave". */
  label?: string;
  /** Outer diameter in pixels. */
  size?: number;
  /** Arc thickness in pixels. */
  strokeWidth?: number;
  className?: string;
}

/**
 * A small SVG radial progress dial for a leave balance.
 *
 * Deliberately pairs with — never replaces — the numeric balance already on
 * screen: the ring is the glance-able cue, the "N of M days remaining" text
 * beside it is the exact figure. The filled arc shows the *remaining* share of
 * the entitlement, so a full dial means a full balance and it empties as days
 * are consumed; the arc uses the brand primary stroke and the remaining track
 * the muted stroke, both theme tokens so the dial follows light/dark mode.
 */
export function BalanceRing({
  used,
  total,
  label,
  size = 56,
  strokeWidth = 6,
  className,
}: BalanceRingProps) {
  const safeTotal = Math.max(total, 0);
  const safeUsed = Math.min(Math.max(used, 0), safeTotal);
  const remaining = Math.max(safeTotal - safeUsed, 0);
  const remainingRatio = safeTotal > 0 ? remaining / safeTotal : 0;

  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const dashOffset = circumference * (1 - remainingRatio);
  const center = size / 2;

  const description = `${remaining} of ${safeTotal} days remaining`;

  return (
    <div className={cn("flex items-center gap-3", className)} role="img" aria-label={label ? `${label}: ${description}` : description}>
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        className="shrink-0 -rotate-90"
        aria-hidden="true"
        focusable="false"
      >
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          strokeWidth={strokeWidth}
          className="stroke-muted"
        />
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={dashOffset}
          className="stroke-primary transition-[stroke-dashoffset] duration-500 motion-reduce:transition-none"
        />
      </svg>
      <div className="min-w-0">
        {label && (
          <p className="text-xs font-medium text-text-secondary truncate">
            {label}
          </p>
        )}
        <p className="text-sm font-semibold tracking-tight text-text-primary">
          {remaining}
          <span className="text-text-muted font-normal"> of {safeTotal} days</span>
        </p>
      </div>
    </div>
  );
}
