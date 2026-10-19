import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";
import { STATUS_STYLES } from "@/lib/status-styles";

/**
 * Every status pill renders through `tone`, and the label maps in
 * lib/*\/labels.ts carry a `badgeTone` rather than a hand-written class
 * string, so a new status only needs a new entry here. The five status tones
 * are `STATUS_STYLES` from `lib/status-styles.ts` — the one place status →
 * colour is defined; the two icon tiles that need the same colours on a
 * square (rather than a pill) call `badgeVariants` directly instead of
 * restating the classes. Non-status tones (neutral, brand, info…) stay local:
 * they are not part of the status palette.
 *
 * `size` carries the four pill densities the app actually uses. Anything
 * denser than `xs` is a deliberate design decision, not an accident.
 */
const badgeVariants = cva(
  [
    // Status is a label, not a control: a 4px radius reads as a tag and stops
    // these from competing with the real pill-shaped controls in the same row.
    "inline-flex items-center rounded-sm",
    "transition-colors duration-fast ease-standard",
  ],
  {
    variants: {
      tone: {
        neutral: "bg-surface-muted text-text-secondary",
        draft: "bg-surface-subtle text-text-secondary",
        muted: "bg-surface-muted text-text-muted",
        brand: "bg-brand-primary-subtle text-brand-primary",
        info: "bg-brand-secondary-subtle text-brand-secondary",
        pending: STATUS_STYLES.pending,
        approved: STATUS_STYLES.approved,
        rejected: STATUS_STYLES.rejected,
        correction: STATUS_STYLES.correction_required,
        cancelled: STATUS_STYLES.cancelled,
      },
      size: {
        default: "gap-1.5 px-3 py-1 text-xs font-semibold",
        sm: "gap-1.5 px-2.5 py-0.5 text-xs font-semibold",
        compact: "gap-1 px-2.5 py-0.5 text-xs font-medium whitespace-nowrap",
        xs: "gap-1 px-2 py-0.5 text-[11px] font-semibold",
      },
    },
    defaultVariants: {
      tone: "neutral",
      size: "default",
    },
  }
);

/** The status colour keys accepted by the `tone` variant. */
export type BadgeTone = NonNullable<VariantProps<typeof badgeVariants>["tone"]>;

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, size, tone, ...props }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ size, tone }), className)} {...props} />
  );
}

export { badgeVariants };
