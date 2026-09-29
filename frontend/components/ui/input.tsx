import { cn } from "@/lib/utils";

/** One source of truth for every text control's border, fill and focus ring. */
export const fieldStyles = [
  "w-full rounded-control border border-input-border bg-input-background px-control-x-md py-control-y",
  "text-sm text-text-primary placeholder:text-text-placeholder",
  "transition-[border-color,box-shadow] duration-fast ease-standard",
  "focus-visible:border-input-border-focus focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-input-ring-focus",
  "disabled:cursor-not-allowed disabled:bg-input-disabled disabled:text-text-disabled",
  "aria-[invalid=true]:border-border-error aria-[invalid=true]:focus-visible:ring-status-rejected/20",
] as const;

export function Input({
  className,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn(fieldStyles, className)} {...props} />;
}

export function Select({
  className,
  children,
  ...props
}: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cn(fieldStyles, "cursor-pointer", className)}
      {...props}
    >
      {children}
    </select>
  );
}

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
      <label htmlFor={htmlFor} className="block text-sm font-medium text-text-secondary">
        {label}
      </label>
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
