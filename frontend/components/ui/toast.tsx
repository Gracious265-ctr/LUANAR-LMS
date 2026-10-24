"use client";

import { useCallback, useSyncExternalStore } from "react";
import { CheckCircle2, Info, TriangleAlert, X } from "lucide-react";

import { cn } from "@/lib/utils";
import { STATUS_SOLID } from "@/lib/status-styles";

const TOAST_TONES = {
  success: { surface: STATUS_SOLID.approved, icon: CheckCircle2 },
  warning: { surface: STATUS_SOLID.notice, icon: TriangleAlert },
  error: { surface: STATUS_SOLID.rejected, icon: TriangleAlert },
  info: { surface: "bg-surface-card text-text-primary", icon: Info },
} as const;

export type ToastTone = keyof typeof TOAST_TONES;

interface ToastItem {
  id: number;
  message: string;
  tone: ToastTone;
  /** `out` keeps the toast mounted while its exit animation plays. */
  phase: "in" | "out";
}

/** How long a dismissed toast stays mounted for the exit animation
 *  (`--duration-base` is 200ms; keep the two in step). */
const EXIT_MS = 200;
/** The stack keeps the most recent few messages, oldest dropped first. */
const MAX_STACK = 4;

let nextId = 1;
let items: ToastItem[] = [];
const listeners = new Set<() => void>();
const autoTimers = new Map<number, ReturnType<typeof setTimeout>>();
const exitTimers = new Map<number, ReturnType<typeof setTimeout>>();

const EMPTY: ToastItem[] = [];

function emit() {
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

const getSnapshot = () => items;
const getServerSnapshot = () => EMPTY;

function clearAutoTimer(id: number) {
  const timer = autoTimers.get(id);
  if (timer) {
    clearTimeout(timer);
    autoTimers.delete(id);
  }
}

function removeNow(id: number) {
  clearAutoTimer(id);
  const exitTimer = exitTimers.get(id);
  if (exitTimer) {
    clearTimeout(exitTimer);
    exitTimers.delete(id);
  }
  if (items.some((item) => item.id === id)) {
    items = items.filter((item) => item.id !== id);
    emit();
  }
}

export function dismissToast(id: number) {
  clearAutoTimer(id);
  const item = items.find((entry) => entry.id === id);
  if (!item || item.phase === "out") return;
  items = items.map((entry) =>
    entry.id === id ? { ...entry, phase: "out" } : entry
  );
  emit();
  exitTimers.set(
    id,
    setTimeout(() => removeNow(id), EXIT_MS)
  );
}

/**
 * Show a toast in the global bottom-right stack.
 *
 * An identical message replaces the one already showing (its countdown
 * restarts) rather than piling up a duplicate. `timeout` is the visible
 * duration before the exit animation plays.
 */
export function pushToast(
  message: string,
  tone: ToastTone = "success",
  timeout = 4000
) {
  for (const existing of [...items]) {
    if (existing.message === message) removeNow(existing.id);
  }
  while (items.length >= MAX_STACK) {
    removeNow(items[0].id);
  }
  const id = nextId++;
  items = [...items, { id, message, tone, phase: "in" }];
  autoTimers.set(
    id,
    setTimeout(() => dismissToast(id), timeout)
  );
  emit();
}

/** Clear every toast and its timers. Exported for tests. */
export function resetToasts() {
  for (const timer of autoTimers.values()) clearTimeout(timer);
  for (const timer of exitTimers.values()) clearTimeout(timer);
  autoTimers.clear();
  exitTimers.clear();
  if (items.length > 0) {
    items = [];
    emit();
  }
}

function useToasts() {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}

/**
 * The toast card itself: tone surface, icon, dismiss control, announced
 * politely. Positioning and stacking belong to `Toaster`; the enter/exit
 * slide+fade is driven by the `animate-toast-*` classes so it honours
 * `prefers-reduced-motion` through `motion-safe:`.
 */
export function Toast({
  tone = "success",
  children,
  onDismiss,
  dismissLabel = "Dismiss notification",
  hideIcon = false,
  exiting = false,
  className,
}: {
  tone?: ToastTone;
  children: React.ReactNode;
  onDismiss?: () => void;
  dismissLabel?: string;
  hideIcon?: boolean;
  /** True while the toast is animating out; swaps the enter class for the exit one. */
  exiting?: boolean;
  className?: string;
}) {
  const { surface, icon: Icon } = TOAST_TONES[tone];

  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "pointer-events-auto flex items-center gap-2 rounded-lg px-4 py-3",
        "text-sm font-semibold text-text-on-brand shadow-lg",
        surface,
        exiting
          ? "motion-safe:animate-toast-out"
          : "motion-safe:animate-toast-in",
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
 * The one place toasts render: a bottom-right stack, newest at the bottom
 * corner, each message auto-dismissing on its own timer. Mounted once by the
 * dashboard shell; call `pushToast` (or `useToast`) from anywhere.
 */
export function Toaster() {
  const toasts = useToasts();
  if (toasts.length === 0) return null;

  return (
    <div
      aria-label="Notifications"
      className={cn(
        "pointer-events-none fixed right-4 bottom-4 z-toast",
        "flex w-[min(24rem,calc(100vw-2rem))] flex-col items-end gap-2",
        "sm:right-6 sm:bottom-6"
      )}
    >
      {toasts.map((toast) => (
        <Toast
          key={toast.id}
          tone={toast.tone}
          exiting={toast.phase === "out"}
          onDismiss={() => dismissToast(toast.id)}
          className="w-full"
        >
          {toast.message}
        </Toast>
      ))}
    </div>
  );
}

/**
 * Show toasts from a component. Each caller's `timeout` applies to the
 * messages it pushes; the stack itself is global, so a message survives
 * navigation away from the caller.
 */
export function useToast(timeout = 4000) {
  const showToast = useCallback(
    (message: string, tone: ToastTone = "success") => {
      pushToast(message, tone, timeout);
    },
    [timeout]
  );

  return { showToast };
}
