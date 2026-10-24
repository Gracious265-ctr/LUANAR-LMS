"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { ConfirmButton } from "@/components/ui/confirm-button";

/**
 * A row's destructive action, behind an inline confirmation.
 *
 * The caller owns the write (`onDelete`) so the same button serves holidays,
 * events, and financial years. The backend is the authority on whether a row
 * may go: a financial year referenced by an entitlement or plan answers 409 and
 * that sentence is shown beside the button rather than swallowed.
 */
export function DeleteRowButton({
  label,
  prompt,
  onDelete,
}: {
  /** Accessible name for the trigger when the visible text is just "Delete". */
  label: string;
  /** The sentence shown beside the confirm, naming what is about to happen. */
  prompt: React.ReactNode;
  onDelete: () => Promise<void>;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function remove() {
    setBusy(true);
    setError("");
    try {
      await onDelete();
      router.refresh();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "An error occurred. Please try again."
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="inline-flex flex-col items-end gap-1">
      <ConfirmButton
        size="sm"
        onConfirm={remove}
        loading={busy}
        prompt={prompt}
        confirmLabel="Delete"
        aria-label={label}
      >
        Delete
      </ConfirmButton>
      {error && (
        <span className="max-w-xs text-right text-xs text-status-rejected">
          {error}
        </span>
      )}
    </span>
  );
}
