import { Button } from "@/components/ui/button";

import { cn } from "@/lib/utils";

/**
 * Previous/next pager used by the list views.
 *
 * Replaces the two hand-rolled copies that each re-spelled the same three
 * buttons; the controls are real `Button`s so focus rings, disabled styling
 * and the pill radius come from the shared primitive.
 */
export function Pagination({
  page,
  hasPrevious,
  hasNext,
  onPrevious,
  onNext,
  className,
}: {
  page: number;
  hasPrevious: boolean;
  hasNext: boolean;
  onPrevious: () => void;
  onNext: () => void;
  className?: string;
}) {
  return (
    <nav
      aria-label="Pagination"
      className={cn("flex items-center justify-between", className)}
    >
      <Button size="sm" disabled={!hasPrevious} onClick={onPrevious}>
        Previous
      </Button>
      <span className="text-sm text-text-muted">Page {page}</span>
      <Button size="sm" disabled={!hasNext} onClick={onNext}>
        Next
      </Button>
    </nav>
  );
}
