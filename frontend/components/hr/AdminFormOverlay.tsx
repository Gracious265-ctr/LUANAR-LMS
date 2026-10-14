"use client";

import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export interface AdminFormOverlayProps {
  open: boolean;
  title: string;
  description: ReactNode;
  onOpenChange: (open: boolean) => void;
  /**
   * Identity of the record being edited, used to key the dialog's contents.
   *
   * Pass the id (or `"new"`). The title is only a fallback, because two
   * records can share one — leave types by code, entitlements by grade band —
   * and remounting only when the title differs would leave the previous
   * record's `defaultValue`s on screen.
   */
  targetKey?: string | null;
  /**
   * `sm` suits the two-or-three-field admin forms and is the default because a
   * short form in a wide dialog looks unfinished. `md` and `lg` are for forms
   * with real layout, and scroll inside the dialog rather than growing past the
   * viewport.
   */
  size?: "sm" | "md" | "lg";
  /**
   * Shown instead of the form when the requested record is not in the list the
   * overlay resolves against — usually because the page's own filters are
   * hiding it. A link to the record's old route stays a valid deep link, so
   * this is reachable, not theoretical.
   */
  notFound?: string;
  /** Label for the "clear filters" escape hatch shown with `notFound`. */
  clearFiltersLabel?: string;
  onClearFilters?: () => void;
  children: ReactNode;
}

const SIZES = {
  sm: "",
  md: "max-w-2xl",
  lg: "max-w-4xl",
} as const;

/**
 * A create/edit dialog for the HR admin forms.
 *
 * Presentational on purpose: the URL state lives in `useOverlayParam`, and the
 * form brings its own submit row, so the only thing this adds is the chrome
 * and the not-found escape hatch.
 *
 * The dialog is deliberately narrower than the leave overlay's `max-w-2xl` by
 * default: a short form in a wide dialog looks unfinished.
 */
export function AdminFormOverlay({
  open,
  title,
  description,
  onOpenChange,
  targetKey,
  size = "sm",
  notFound,
  clearFiltersLabel = "Clear filters",
  onClearFilters,
  children,
}: AdminFormOverlayProps) {
  if (!open) return null;

  return (
    <AdminFormOverlayInner
      // Remounting per target is what discards the previous record's form
      // state. The forms seed their inputs with `defaultValue`, so without this
      // key switching edit targets would keep the old values.
      key={targetKey ?? title}
      title={title}
      description={description}
      onOpenChange={onOpenChange}
      size={size}
      notFound={notFound}
      clearFiltersLabel={clearFiltersLabel}
      onClearFilters={onClearFilters}
    >
      {children}
    </AdminFormOverlayInner>
  );
}

function AdminFormOverlayInner({
  title,
  description,
  onOpenChange,
  size,
  notFound,
  clearFiltersLabel,
  onClearFilters,
  children,
}: Omit<AdminFormOverlayProps, "open" | "targetKey" | "size"> & {
  size: NonNullable<AdminFormOverlayProps["size"]>;
}) {
  const scrollable = size !== "sm";

  return (
    <Dialog open onOpenChange={onOpenChange}>
      <DialogContent className={SIZES[size]} scrollable={scrollable}>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        {notFound ? (
          <div className="space-y-4">
            <p className="text-sm text-text-secondary">{notFound}</p>
            {onClearFilters && (
              <Button variant="secondary" onClick={onClearFilters}>
                {clearFiltersLabel}
              </Button>
            )}
          </div>
        ) : (
          children
        )}
      </DialogContent>
    </Dialog>
  );
}
