import { cn } from "@/lib/utils";

/** Form-level error banner: says why the whole submission failed. */
export function FormError({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      role="alert"
      className={cn(
        "rounded-md bg-status-rejected-subtle p-3 text-sm text-status-rejected",
        className
      )}
    >
      {children}
    </div>
  );
}