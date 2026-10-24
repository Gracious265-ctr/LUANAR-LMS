import { cva, type VariantProps } from "class-variance-authority";
import { Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";

const CONTROL_BASE = [
  "inline-flex items-center justify-center rounded-sm font-medium whitespace-nowrap",
  "transition-[transform,box-shadow,background-color,border-color,color] duration-base ease-standard",
  "hover:-translate-y-px",
  "active:translate-y-0 active:shadow-none",
  "focus-ring",
  "disabled:cursor-not-allowed disabled:opacity-60 disabled:transform-none disabled:shadow-none",
  "[&_svg]:shrink-0",
] as const;

const buttonVariants = cva(CONTROL_BASE, {
  variants: {
    variant: {
      primary: [
        "border border-transparent bg-[linear-gradient(135deg,var(--brand-primary-gradient-start)_0%,var(--brand-primary-gradient-end)_100%)] text-white",
        "hover:shadow-hover",
        "active:bg-[linear-gradient(135deg,var(--brand-primary-gradient-end)_0%,var(--brand-primary-gradient-start)_100%)]",
      ],
      secondary: [
        "border border-border-subtle bg-transparent text-text-secondary",
        "hover:bg-surface-page hover:border-brand-primary-gradient-start hover:text-brand-primary-gradient-start",
        "active:bg-surface-page",
      ],
      ghost: [
        "border border-transparent bg-transparent text-text-secondary",
        "hover:bg-surface-page hover:text-brand-primary-gradient-start",
        "active:bg-surface-page",
      ],
      destructive: [
        "border border-transparent bg-button-destructive text-text-on-brand",
        "hover:bg-button-destructive-hover",
        "active:shadow-pressed",
      ],
      /**
       * Text-only action. The app has many tertiary actions (Retry, Dismiss,
       * "View details") that were plain buttons with no chrome; these keep
       * that weight while still getting the shared focus ring and disabled
       * treatment. The height still comes from `size`, so callers that need
       * the original inline text box pass `h-auto`.
       */
      link: [
        "border border-transparent bg-transparent text-brand-primary",
        "hover:underline",
      ],
    },
    size: {
      sm: "h-control-height-sm gap-control-gap px-control-x-sm text-xs",
      md: "h-control-height-md gap-control-gap px-control-x-md text-sm",
      lg: "h-control-height-lg gap-control-gap px-control-x-lg text-sm",
      icon: "size-control-height-icon",
    },
  },
  defaultVariants: {
    variant: "secondary",
    size: "md",
  },
});

export interface ButtonProps
  extends React.ComponentPropsWithRef<"button">,
    VariantProps<typeof buttonVariants> {
  /** Shows a spinner and blocks interaction without changing the button width. */
  loading?: boolean;
}

export function Button({
  className,
  variant,
  size,
  loading = false,
  disabled,
  type = "button",
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(buttonVariants({ variant, size }), className)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
      {children}
    </button>
  );
}

export { buttonVariants };
