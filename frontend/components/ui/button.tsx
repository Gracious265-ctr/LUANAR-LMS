import { cva, type VariantProps } from "class-variance-authority";
import { Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";

const CONTROL_BASE = [
  "inline-flex items-center justify-center rounded-control font-medium whitespace-nowrap",
  "transition-[background-color,border-color,color,box-shadow] duration-fast ease-standard",
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary focus-visible:ring-offset-2",
  "disabled:cursor-not-allowed disabled:opacity-60",
  "[&_svg]:shrink-0",
] as const;

const buttonVariants = cva(CONTROL_BASE, {
  variants: {
    variant: {
      primary: [
        "border border-transparent bg-button-primary text-button-primary-foreground",
        "hover:bg-button-primary-hover",
        "active:bg-brand-primary-active active:shadow-pressed",
      ],
      secondary: [
        "border border-border-default bg-button-secondary text-text-secondary",
        "hover:bg-button-secondary-hover hover:text-text-primary",
        "active:bg-surface-active active:shadow-pressed",
      ],
      ghost: [
        "border border-transparent bg-transparent text-text-secondary",
        "hover:bg-surface-hover hover:text-text-primary",
        "active:bg-surface-active",
      ],
      destructive: [
        "border border-transparent bg-button-destructive text-text-on-brand",
        "hover:bg-button-destructive-hover",
        "active:shadow-pressed",
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
