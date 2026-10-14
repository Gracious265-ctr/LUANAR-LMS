import { cn } from "@/lib/utils";

import { Label } from "./label";

/** One source of truth for every text control's border, fill and focus ring. */
export const fieldStyles = [
  "w-full rounded-control border border-input-border bg-input-background px-control-x-md py-control-y",
  "text-sm text-text-primary placeholder:text-text-placeholder",
  "transition-[border-color,box-shadow] duration-base ease-standard",
  "focus-visible:border-input-border-focus focus-ring",
  "disabled:cursor-not-allowed disabled:bg-input-disabled disabled:text-text-disabled",
  "aria-[invalid=true]:border-border-error aria-[invalid=true]:shadow-[0_0_0_2px_#ffffff,0_0_0_4px_#DC2626]",
] as const;

export function Input({
  className,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement>) {
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
    <div className={cn("space-y-block", className)}>
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
