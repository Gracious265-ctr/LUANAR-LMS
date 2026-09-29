import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  [
    "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold",
    "transition-colors duration-fast ease-standard",
  ],
  {
    variants: {
      tone: {
        neutral: "bg-surface-muted text-text-secondary",
        brand: "bg-brand-primary-subtle text-brand-primary",
        pending: "bg-status-pending-subtle text-status-pending",
        approved: "bg-status-approved-subtle text-status-approved",
        rejected: "bg-status-rejected-subtle text-status-rejected",
        correction: "bg-status-correction-subtle text-status-correction",
        cancelled: "bg-status-cancelled-subtle text-text-secondary",
      },
    },
    defaultVariants: {
      tone: "neutral",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}

export { badgeVariants };
