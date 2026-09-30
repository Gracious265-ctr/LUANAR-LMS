import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

/**
 * Inline status and error messages.
 *
 * These are the same surfaces that were previously hand-written as
 * `rounded-md bg-status-*-subtle p-3 text-sm` divs, so a converted callout is
 * a visual no-op. `FormError` is a thin wrapper over the `rejected` tone.
 */
const alertVariants = cva(
  [
    "flex gap-2.5 rounded-lg p-3 text-sm",
    "[&_p]:leading-relaxed",
  ],
  {
    variants: {
      tone: {
        neutral: "bg-surface-muted text-text-secondary",
        info: "bg-brand-primary-subtle text-brand-primary",
        pending: "bg-status-pending-subtle text-status-pending",
        approved: "bg-status-approved-subtle text-status-approved",
        rejected: "bg-status-rejected-subtle text-status-rejected",
        correction: "bg-status-correction-subtle text-status-correction",
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
