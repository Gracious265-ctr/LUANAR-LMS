"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { CheckCircle2, Info, TriangleAlert, X } from "lucide-react";

import { cn } from "@/lib/utils";

const TOAST_TONES = {
  success: { surface: "bg-status-approved", icon: CheckCircle2 },
  warning: { surface: "bg-status-correction", icon: TriangleAlert },
  error: { surface: "bg-status-rejected", icon: TriangleAlert },
  info: { surface: "bg-surface-card text-text-primary", icon: Info },
} as const;

export type ToastTone = keyof typeof TOAST_TONES;

/**
 * Transient confirmation, anchored top-centre and announced politely.
 *
 * `animated` is opt-in: the enter transition is a visual change, so it is only
 * turned on where it has been reviewed. Auto-dismiss belongs to `useToast`, so
 * a refresh-driven message is never cut short.
 */
export function Toast({
  tone = "success",
  children,
  onDismiss,
  dismissLabel = "Dismiss notification",
  hideIcon = false,
  animated = false,
  className,
}: {
  tone?: ToastTone;
  children: React.ReactNode;
  onDismiss?: () => void;
  dismissLabel?: string;
  hideIcon?: boolean;
  animated?: boolean;
  className?: string;
}) {
  const { surface, icon: Icon } = TOAST_TONES[tone];

  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "fixed top-4 left-1/2 z-toast flex -translate-x-1/2 items-center gap-2 rounded-lg px-4 py-3",
        "text-sm font-semibold text-text-on-brand shadow-lg",
        surface,
        animated && "motion-safe:animate-toast-in",
        className
      )}
    >
      {!hideIcon && <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />}
      {children}
      {onDismiss && (
        <button
          type="button"
          onClick={onDismiss}
          aria-label={dismissLabel}
          // `bg-current/10` rather than a fixed `black/10`: the wash has to be
          // legible on the toast's own surface, which is near-white in light and
          // near-black in dark. Deriving it from `currentColor` follows the
          // surface automatically instead of being right in one theme only.
          className="shrink-0 rounded-control transition-colors hover:bg-current/10 focus-ring"
        >
          <X className="h-4 w-4" aria-hidden="true" />
        </button>
      )}
    </div>
  );
}

/**
 * Toast state with a timed dismiss. Each call restarts the countdown, so a
 * second message is never cut short by the first one's timer.
 */
export function useToast(timeout = 4000) {
  const [toast, setToast] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const showToast = useCallback(
    (message: string) => {
      clearTimer();
      timerRef.current = setTimeout(() => setToast(null), timeout);
      setToast(message);
    },
    [clearTimer, timeout]
  );

  const dismissToast = useCallback(() => {
    clearTimer();
    setToast(null);
  }, [clearTimer]);

  useEffect(() => clearTimer, [clearTimer]);

  return { toast, showToast, dismissToast };
}
