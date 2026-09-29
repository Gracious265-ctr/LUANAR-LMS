"use client";

import { BellRing, Check, Loader2, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";

import { formatDate } from "@/lib/plans/format";
import { confirmBlock, fetchPendingConfirmations } from "@/lib/plans/service";
import type { PendingConfirmationBlock } from "@/lib/plans/types";
import { cn } from "@/lib/utils";

import { EmptyState } from "@/components/ui/states";

export function PendingConfirmationsPanel({
  onChanged,
}: {
  onChanged?: () => void;
}) {
  const [blocks, setBlocks] = useState<PendingConfirmationBlock[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    fetchPendingConfirmations()
      .then((result) => {
        if (cancelled) return;
        if (result.ok) {
          setBlocks(result.data.results);
          setError("");
        } else {
          setError(result.message);
        }
      })
      .catch(() => {
        if (!cancelled) setError("Failed to load confirmations.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  async function confirm(block: PendingConfirmationBlock) {
    setBusyId(block.id);
    setError("");
    const result = await confirmBlock(block.plan_id, block.id);
    setBusyId(null);
    if (result.ok) {
      setReloadKey((n) => n + 1);
      onChanged?.();
    } else {
      setError(result.message);
      setReloadKey((n) => n + 1);
    }
  }

  return (
    <section className="rounded-xl border border-border-default bg-surface-card p-5 shadow-subtle">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-base font-semibold text-text-primary">
          <BellRing className="size-4 text-brand-primary" />
          Reserve before you go
        </h2>
        {loading ? (
          <Loader2 className="size-4 animate-spin text-text-muted" />
        ) : (
          <button
            type="button"
            onClick={() => setReloadKey((n) => n + 1)}
            className="rounded-md p-1 text-text-muted transition-colors hover:bg-surface-hover hover:text-text-primary"
            aria-label="Refresh confirmations"
          >
            <RefreshCw className="size-4" />
          </button>
        )}
      </div>

      {error && (
        <p className="mb-3 text-sm text-status-rejected">{error}</p>
      )}

      {!loading && blocks.length === 0 && (
        <EmptyState
          icon={<BellRing className="size-8 text-text-muted" />}
          title="Nothing to confirm"
          description="Reserved blocks that allow annual leave need to be confirmed before the confirmation window closes."
          titleAs="h3"
        />
      )}

      <ul className="space-y-2">
        {blocks.map((block) => {
          const windowStart = block.confirmation_window_start;
          return (
            <li
              key={block.id}
              className={cn(
                "rounded-lg border border-border-default bg-surface-page px-3.5 py-2.5"
              )}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="text-sm">
                  <span className="font-medium text-text-primary">
                    {block.leave_type_name || block.leave_type_code || "Leave"}
                  </span>
                  <span className="text-text-secondary">
                    {" "}
                    · {formatDate(block.start_date)} → {formatDate(block.end_date)}
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-text-muted">
                    {block.working_days ?? "—"} days
                    {windowStart &&
                      ` · confirm by ${formatDate(windowStart)} confirmed`}
                  </span>
                  <button
                    type="button"
                    disabled={busyId === block.id}
                    onClick={() => void confirm(block)}
                    className="inline-flex items-center gap-1 rounded-md bg-[#009119] px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-[#008017] disabled:opacity-50"
                  >
                    {busyId === block.id ? (
                      <Loader2 className="size-3.5 animate-spin" />
                    ) : (
                      <Check className="size-3.5" />
                    )}
                    Confirm
                  </button>
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}