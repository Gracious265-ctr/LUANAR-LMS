import { Card, cardStyles } from "@/components/ui/card";
import { STATUS_STYLES } from "@/lib/status-styles";
import { cn } from "@/lib/utils";

/**
 * The one stat-card shape used across the dashboards: a title, a tinted icon
 * tile, a large figure and a caption. The icon tile carries `shadow-xs` so it
 * reads as a raised chip rather than a flat swatch.
 *
 * A card is interactive only when it is given somewhere to go (`onClick`);
 * without one it renders as a plain surface with no hover lift, so a figure the
 * user cannot act on does not invite a click.
 */
const STAT_CARD_VARIANTS = {
  primary: "bg-brand-primary-subtle text-brand-primary",
  pending: STATUS_STYLES.pending,
  info: "bg-status-info-subtle text-status-info",
  secondary: "bg-brand-secondary-subtle text-brand-secondary",
} as const;

export type StatCardVariant = keyof typeof STAT_CARD_VARIANTS;

interface StatCardProps {
  title: string;
  value: string;
  subtitle: React.ReactNode;
  icon: React.ReactNode;
  variant: StatCardVariant;
  onClick?: () => void;
  className?: string;
}

export function StatCard({
  title,
  value,
  subtitle,
  icon,
  variant,
  onClick,
  className,
}: StatCardProps) {
  const body = (
    <>
      <div className="mb-3 flex items-center justify-between">
        <span className="text-sm font-medium text-text-secondary">{title}</span>
        <div
          className={cn(
            "rounded-lg p-2 shadow-xs",
            STAT_CARD_VARIANTS[variant]
          )}
        >
          {icon}
        </div>
      </div>
      <div className="text-3xl font-semibold tracking-tight text-text-primary">
        {value}
      </div>
      <p className="mt-1 text-sm text-text-muted">{subtitle}</p>
    </>
  );

  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        className={cn(cardStyles, "hover-float focus-ring w-full text-left", className)}
      >
        {body}
      </button>
    );
  }

  return <Card className={className}>{body}</Card>;
}
