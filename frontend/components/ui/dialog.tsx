"use client";

<<<<<<< HEAD
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
=======
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { XIcon } from "lucide-react";

import { cn } from "@/lib/utils";

export function Dialog({ ...props }: React.ComponentPropsWithRef<typeof DialogPrimitive.Root>) {
  return <DialogPrimitive.Root data-slot="dialog" {...props} />;
}

export function DialogTrigger({
  ...props
}: React.ComponentPropsWithRef<typeof DialogPrimitive.Trigger>) {
  return <DialogPrimitive.Trigger data-slot="dialog-trigger" {...props} />;
}

export function DialogPortal({
  ...props
}: React.ComponentPropsWithRef<typeof DialogPrimitive.Portal>) {
  return <DialogPrimitive.Portal data-slot="dialog-portal" {...props} />;
}

export function DialogClose({
  ...props
}: React.ComponentPropsWithRef<typeof DialogPrimitive.Close>) {
  return <DialogPrimitive.Close data-slot="dialog-close" {...props} />;
}

export function DialogOverlay({
  className,
  ...props
}: React.ComponentPropsWithRef<typeof DialogPrimitive.Overlay>) {
  return (
    <DialogPrimitive.Overlay
      data-slot="dialog-overlay"
      className={cn(
        "fixed inset-0 z-modal-overlay bg-black/40",
        "data-[state=open]:animate-in data-[state=open]:fade-in-0",
        "data-[state=closed]:animate-out data-[state=closed]:fade-out-0",
        className
      )}
      {...props}
    />
  );
}

/**
 * Centred modal surface.
 *
 * Pass `scrollable` for a dialog that can outgrow the viewport. It splits the
 * radius from the scroll: the outer element keeps `rounded-xl` and clips with
 * `overflow-hidden`, while a child carries `overflow-y-auto`. Putting both on
 * one element lets the scrollbar track square off the rounded corners, so the
 * clipping has to live on an ancestor of the scroller.
 *
 * `min-h-0` on the scroller is load-bearing: a flex item defaults to
 * `min-height: auto`, which would stop it shrinking to the available height and
 * leave it overflowing instead of scrolling.
 */
export function DialogContent({
  className,
  children,
  showCloseButton = true,
  scrollable = false,
  scrollClassName,
  ...props
}: React.ComponentPropsWithRef<typeof DialogPrimitive.Content> & {
  showCloseButton?: boolean;
  scrollable?: boolean;
  scrollClassName?: string;
}) {
  return (
    <DialogPortal>
      <DialogOverlay />
      <DialogPrimitive.Content
        data-slot="dialog-content"
        className={cn(
          "fixed left-1/2 top-1/2 z-modal w-full max-w-lg -translate-x-1/2 -translate-y-1/2",
          "rounded-xl border border-border-default bg-surface-card shadow-lg",
          "data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95",
          "data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95",
          scrollable
            ? "flex max-h-[calc(100vh-4rem)] flex-col overflow-hidden"
            : "grid gap-4 p-6",
          className
        )}
        {...props}
      >
        {scrollable ? (
          <div
            data-slot="dialog-scroll"
            className={cn("grid min-h-0 flex-1 gap-4 overflow-y-auto p-6", scrollClassName)}
          >
            {children}
          </div>
        ) : (
          children
        )}
        {showCloseButton ? <DialogCloseButton /> : null}
      </DialogPrimitive.Content>
    </DialogPortal>
  );
}

/**
 * `Dialog.Content` with none of the centred-modal chrome.
 *
 * `DialogContent` is built for a modal that sits in the middle of the screen:
 * fixed, centred, `max-w-lg`, animated as a zoom. A drawer is a full-height
 * edge-anchored panel, so it needs to own its own positioning. This keeps Radix's
 * focus trap, scroll lock and `aria-modal` wiring while letting the caller supply
 * every visual decision.
 */
export function DialogSurface({
  className,
  children,
  ...props
}: React.ComponentPropsWithRef<typeof DialogPrimitive.Content>) {
  return (
    <DialogPrimitive.Content
      data-slot="dialog-surface"
      className={cn("z-modal outline-none", className)}
      {...props}
    >
      {children}
    </DialogPrimitive.Content>
  );
}

function DialogCloseButton({
  className,
  ...props
}: React.ComponentPropsWithRef<typeof DialogPrimitive.Close>) {
  return (
    <DialogPrimitive.Close
      data-slot="dialog-close"
      aria-label="Close"
      className={cn(
        "absolute right-4 top-4 grid size-8 place-content-center rounded-control",
        "text-text-muted transition-colors",
        "hover:bg-surface-hover hover:text-text-primary",
        "focus-ring",
        "disabled:pointer-events-none",
        className
      )}
      {...props}
    >
      <XIcon className="size-5" aria-hidden="true" />
      <span className="sr-only">Close</span>
    </DialogPrimitive.Close>
  );
}

export function DialogHeader({ className, ...props }: React.ComponentPropsWithRef<"div">) {
  return (
    <div
      data-slot="dialog-header"
      className={cn("flex flex-col gap-1.5 text-left", className)}
      {...props}
    />
  );
}

export function DialogFooter({ className, ...props }: React.ComponentPropsWithRef<"div">) {
  return (
    <div
      data-slot="dialog-footer"
      className={cn("flex flex-col-reverse gap-2 sm:flex-row sm:justify-end", className)}
      {...props}
    />
  );
}

export function DialogTitle({
  className,
  ...props
}: React.ComponentPropsWithRef<typeof DialogPrimitive.Title>) {
  return (
    <DialogPrimitive.Title
      data-slot="dialog-title"
      className={cn("text-lg font-semibold leading-none text-text-primary", className)}
      {...props}
    />
  );
}

export function DialogDescription({
  className,
  ...props
}: React.ComponentPropsWithRef<typeof DialogPrimitive.Description>) {
  return (
    <DialogPrimitive.Description
      data-slot="dialog-description"
      className={cn("text-sm text-text-secondary", className)}
      {...props}
    />
  );
}
>>>>>>> feature/plans-teams
