import { cn } from "@/lib/utils";

import { Label } from "./label";

/** One source of truth for every text control's border, fill and focus ring - SARIS design. */
export const fieldStyles = [
  "w-full rounded-sm border border-input-border bg-input-background px-4 py-2.5",
  "text-base text-text-primary placeholder:text-text-placeholder",
  "transition-[border-color,box-shadow,background-color,transform] duration-base ease-standard",
  "hover:-translate-y-px hover:shadow-[var(--focus-ring-shadow)_0px_4px_12px]",
  "focus-visible:outline-none focus-visible:border-input-border-focus focus-visible:-translate-y-0.5 focus-visible:shadow-[var(--focus-ring-shadow)_0px_0px_0px_3px,rgba(102,126,234,0.15)_0px_8px_25px] focus-visible:bg-[linear-gradient(135deg,rgba(255,255,255,1)_0%,rgba(240,244,255,1)_100%)]",
  "disabled:cursor-not-allowed disabled:bg-input-disabled disabled:text-text-disabled disabled:translate-y-0 disabled:shadow-none",
  "aria-[invalid=true]:border-border-error",
] as const;

export function Input({
  className,
  ...props
}: React.ComponentPropsWithRef<"input">) {
  return <input className={cn(fieldStyles, className)} {...props} />;
}

/**
 * Label + control + hint/error, the shape every form in the app uses.
 *
 * `htmlFor` must match the `id` on the control, which is what makes
 * `getByLabelText` work. That holds for a Radix `SelectTrigger` too, since a
 * `<button>` is a labelable element, so switching a field from `Input` to
 * `Select` does not move its accessible name.
 */
export function Field({
  label,
  htmlFor,
  hint,
  error,
  children,
  className,
}: {
  label: string;
  htmlFor: string;
  hint?: string;
  error?: string | null;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("space-y-stack", className)}>
      <Label htmlFor={htmlFor} className="block">
        {label}
      </Label>
      {children}
      {hint && !error && (
        <p id={`${htmlFor}-hint`} className="text-xs text-text-muted">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${htmlFor}-error`} role="alert" className="text-xs text-status-rejected">
          {error}
        </p>
      )}
    </div>
  );
}
