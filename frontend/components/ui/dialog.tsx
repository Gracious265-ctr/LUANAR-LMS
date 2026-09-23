"use client";

import { useEffect, useRef } from "react";

import { X } from "lucide-react";

import { cn } from "@/lib/utils";

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(", ");

export function Dialog({
  open,
  onClose,
  labelledBy,
  describedBy,
  children,
  blockDismiss = false,
  ariaLabel,
}: {
  open: boolean;
  onClose: () => void;
  labelledBy?: string;
  describedBy?: string;
  children: React.ReactNode;
  /** When true (e.g. a request is in flight) outside clicks and Escape are ignored. */
  blockDismiss?: boolean;
  ariaLabel?: string;
}) {
  const panelRef = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);
  const blockDismissRef = useRef(blockDismiss);

  useEffect(() => {
    onCloseRef.current = onClose;
    blockDismissRef.current = blockDismiss;
  });

  useEffect(() => {
    if (!open) return;

    const previouslyFocused = document.activeElement as HTMLElement | null;
    const panel = panelRef.current;
    panel?.focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape" || blockDismissRef.current) return;
      event.preventDefault();
      onCloseRef.current();
    }

    function onPointerDown(event: PointerEvent) {
      if (blockDismissRef.current) return;
      if (panel && event.target instanceof Node && !panel.contains(event.target)) {
        onCloseRef.current();
      }
    }

    function trapFocus(event: KeyboardEvent) {
      if (event.key !== "Tab" || !panel) return;
      const focusables = Array.from(
        panel.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)
      ).filter((el) => el.offsetParent !== null);
      if (focusables.length === 0) {
        event.preventDefault();
        panel.focus();
        return;
      }
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("keydown", trapFocus);
    document.addEventListener("pointerdown", onPointerDown);

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("keydown", trapFocus);
      document.removeEventListener("pointerdown", onPointerDown);
      document.body.style.overflow = previousOverflow;
      previouslyFocused?.focus();
    };
  }, [open]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      aria-hidden={false}
    >
      <div className="absolute inset-0 bg-text-primary/40" aria-hidden="true" />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={ariaLabel}
        aria-labelledby={labelledBy}
        aria-describedby={describedBy}
        tabIndex={-1}
        className="z-10 w-full max-w-lg rounded-xl bg-surface-card shadow-lg border border-border-default outline-none focus-visible:ring-2 focus-visible:ring-brand-primary"
      >
        {children}
      </div>
    </div>
  );
}

export function DialogHeader({
  titleId,
  title,
  subtitle,
  onClose,
  blockDismiss = false,
}: {
  titleId: string;
  title: string;
  subtitle?: string;
  onClose: () => void;
  blockDismiss?: boolean;
}) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-border-default px-6 py-4">
      <div>
        <h2 id={titleId} className="text-lg font-semibold text-text-primary">
          {title}
        </h2>
        {subtitle && (
          <p className="mt-0.5 text-sm text-text-secondary">{subtitle}</p>
        )}
      </div>
      <button
        type="button"
        onClick={onClose}
        disabled={blockDismiss}
        aria-label="Close dialog"
        className={cn(
          "flex h-9 w-9 items-center justify-center rounded-lg text-text-secondary transition-colors",
          "hover:bg-surface-hover hover:text-text-primary",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary",
          blockDismiss && "cursor-not-allowed opacity-50"
        )}
      >
        <X className="h-5 w-5" aria-hidden="true" />
      </button>
    </div>
  );
}