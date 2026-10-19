"use client";

import { useState } from "react";

import { Button, type ButtonProps } from "@/components/ui/button";

/**
 * A destructive action behind an inline confirmation.
 *
 * The first click only reveals the confirm; nothing is written until the second
 * click lands on the destructive button. This is the confirm step the app owes
 * every irreversible action, kept inline (rather than a dialog that has to be
 * portalled, focused and dismissed) so it reads in the same place the action
 * lives — the pattern `WorkflowRoutingActions` already uses for switching chains.
 *
 * The caller keeps owning the work: `onConfirm` is the same handler a bare
 * button would call, and `loading` is the caller's own busy flag, so a slow
 * write disables both the confirm and the cancel rather than pretending it is
 * finished.
 */
export function ConfirmButton({
  onConfirm,
  loading = false,
  disabled = false,
  prompt,
  confirmLabel = "Yes, continue",
  cancelLabel = "Cancel",
  variant = "secondary",
  size = "sm",
  className,
  children,
  ...props
}: Omit<ButtonProps, "onClick" | "children"> & {
  /** Runs only on the confirming click. May be async. */
  onConfirm: () => Promise<void> | void;
  /** The caller's busy flag for the in-flight write. */
  loading?: boolean;
  /** The sentence shown beside the confirm, naming what is about to happen. */
  prompt?: React.ReactNode;
  /** The label on the button that actually writes. */
  confirmLabel?: string;
  cancelLabel?: string;
  children: React.ReactNode;
}) {
  const [confirming, setConfirming] = useState(false);

  if (!confirming) {
    return (
      <Button
        variant={variant}
        size={size}
        className={className}
        disabled={disabled}
        loading={loading}
        onClick={() => setConfirming(true)}
        {...props}
      >
        {children}
      </Button>
    );
  }

  async function confirm() {
    await onConfirm();
    setConfirming(false);
  }

  return (
    <span className="inline-flex flex-wrap items-center justify-end gap-2">
      {prompt ? (
        <span className="text-xs text-text-secondary">{prompt}</span>
      ) : null}
      <Button
        variant="destructive"
        size={size}
        loading={loading}
        disabled={disabled}
        onClick={() => void confirm()}
      >
        {confirmLabel}
      </Button>
      <Button
        variant="secondary"
        size={size}
        disabled={loading || disabled}
        onClick={() => setConfirming(false)}
      >
        {cancelLabel}
      </Button>
    </span>
  );
}
