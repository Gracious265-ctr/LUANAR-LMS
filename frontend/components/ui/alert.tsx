import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";
import { STATUS_STYLES } from "@/lib/status-styles";

/**
 * Inline status and error messages.
 *
 * These are the same surfaces that were previously hand-written as
 * `rounded-md bg-status-*-subtle p-3 text-sm` divs, so a converted callout is
 * a visual no-op. The status tones come from `STATUS_STYLES`, the single
 * status → colour source. `FormError` is a thin wrapper over the `rejected`
 * tone.
 */
const alertVariants = cva(
  [
    "flex gap-2.5 rounded-sm p-3 text-sm",
    "[&_p]:leading-relaxed",
  ],
  {
    variants: {
      tone: {
        neutral: "bg-surface-muted text-text-secondary",
        info: "bg-brand-primary-subtle text-brand-primary",
        pending: STATUS_STYLES.pending,
        approved: STATUS_STYLES.approved,
<<<<<<< HEAD
        rejected: "bg-status-rejected-subtle text-status-rejected border border-status-rejected/30",
        correction: STATUS_STYLES.correction_required,
=======
        rejected: STATUS_STYLES.rejected,
        notice: STATUS_STYLES.notice,
>>>>>>> features/team-base
      },
    },
    defaultVariants: {
      tone: "neutral",
    },
  }
);

export interface AlertProps
  extends React.ComponentPropsWithRef<"div">,
    VariantProps<typeof alertVariants> {
  /** Announce the message assertively. Defaults to `true` for `rejected`. */
  live?: boolean;
}

export function Alert({ className, tone, live, children, ...props }: AlertProps) {
  const assertive = live ?? tone === "rejected";

  return (
    <div
      data-slot="alert"
      role={assertive ? "alert" : "status"}
      className={cn(alertVariants({ tone }), className)}
      {...props}
    >
      {children}
    </div>
  );
}

export { alertVariants };
