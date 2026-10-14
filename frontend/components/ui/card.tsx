import { cn } from "@/lib/utils";

/** One source of truth for every content card surface. The elevation token
 *  carries its own 1px ring, so the card is borderless by design. */
export const cardStyles = [
  "rounded-xl bg-surface-card p-6 shadow-card",
] as const;

export function Card({
  className,
  interactive = false,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { interactive?: boolean }) {
  return (
    <div
      className={cn(
        cardStyles,
        interactive && "hover-float",
        className,
      )}
      {...props}
    />
  );
}

export function CardHeader({
  title,
  icon,
  actions,
  className,
}: {
  title: string;
  icon?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("mb-4 flex items-center justify-between gap-3", className)}>
      <h2 className="flex items-center gap-2 text-base font-semibold text-text-primary">
        {icon && (
          <span className="text-brand-primary" aria-hidden="true">
            {icon}
          </span>
        )}
        {title}
      </h2>
      {actions}
    </div>
  );
}
