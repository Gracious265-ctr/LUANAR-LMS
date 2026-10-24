import { cn } from "@/lib/utils";

/** One source of truth for every content card surface - SARIS design. */
export const cardStyles = [
  "rounded-sm bg-surface-card p-8 shadow-card transition-[transform,box-shadow] duration-base ease-standard hover:-translate-y-px hover:shadow-hover",
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
        interactive && "hover:-translate-y-px hover:shadow-hover",
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
