import { Alert } from "@/components/ui/alert";

/** Form-level error banner: says why the whole submission failed. */
export function FormError({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <Alert tone="rejected" className={className}>
      {children}
    </Alert>
  );
}
