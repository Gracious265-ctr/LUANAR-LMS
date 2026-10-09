"use client";

import { CalendarCheck, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { formatDate, formatPeriod } from "@/lib/plans/format";
import {
  confirmBlock,
  fetchPendingConfirmations,
  releaseBlock,
} from "@/lib/plans/service";
import type { PendingConfirmation } from "@/lib/plans/types";
import { STATUS_TEXT } from "@/lib/status-styles";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { useToast } from "@/components/ui/toast";

/**
 * The blocks an approved plan has reserved that the owner has not confirmed.
 *
 * This is the caller's own list across every plan, so it is one read rather
 * than a per-plan question — and it is the only place the confirmation window
 * is surfaced as a deadline, because that is the thing that lapses.
 */
export function PlanConfirmationsPanel({
  headerless = false,
  reloadKey = 0,
}: {
  headerless?: boolean;
  /** Bumped by the parent when a block changes, to re-read the list. */
  reloadKey?: number;
}) {
  const [rows, setRows] = useState<PendingConfirmation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const { showToast } = useToast();
  const [busy, setBusy] = useState("");
  const [localKey, setLocalKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    fetchPendingConfirmations()
      .then((result) => {
        if (cancelled) return;
        if (result.ok) {
          setRows(result.data.results);
          setError("");
        } else {
          setError(result.message);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey, localKey]);

  function refresh() {
    setError("");
    setLoading(true);
    setLocalKey((value) => value + 1);
  }

  async function act(
    block: PendingConfirmation,
    action: "confirm" | "release"
  ) {
    setBusy(block.id);
    const result =
      action === "confirm"
        ? await confirmBlock(block.plan_id, block.id)
        : await releaseBlock(block.plan_id, block.id);
    if (result.ok) {
      showToast(action === "confirm" ? "Block confirmed" : "Block released");
      setRows((current) => current.filter((row) => row.id !== block.id));
    } else {
      setError(result.message);
    }
    setBusy("");
  }

  return (
    <div className="space-y-6">
      {!headerless && (
        <div>
          <h2 className="text-lg font-semibold tracking-tight text-text-primary">
            Blocks awaiting your confirmation
          </h2>
          <p className="text-sm text-text-secondary">
            An approved plan holds your balance, but each block only becomes
            real once you confirm it.
          </p>
        </div>
      )}

      {error ? (
        <ErrorState message={error} onRetry={refresh} />
      ) : loading ? (
        <div className="space-y-3" aria-busy="true" aria-label="Loading confirmations">
          {Array.from({ length: 2 }).map((_, index) => (
            <div
              key={index}
              className="h-20 animate-pulse rounded-xl border border-border-default bg-surface-card"
            />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <Card>
          <EmptyState
            icon={<CalendarCheck className="h-8 w-8 text-text-muted" aria-hidden="true" />}
            title="Nothing to confirm"
            description="Blocks reserved by an approved plan will appear here until you confirm or release them."
          />
        </Card>
      ) : (
        <ul className="space-y-3">
          {rows.map((block) => (
            <li key={block.id}>
              <Card>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-medium text-text-primary">
                      {block.leave_type_name || "—"}
                    </p>
                    <p className="mt-0.5 text-sm text-text-secondary">
                      {formatDate(block.start_date)} – {formatDate(block.end_date)}
                    </p>
                    <p className="mt-1 text-xs text-text-muted">
                      Plan {formatPeriod(block.plan_period_start, block.plan_period_end)}
                    </p>
                    {block.confirmation_window_start && (
                      <p className={`mt-1 text-xs font-medium ${STATUS_TEXT.pending}`}>
                        Confirm by {formatDate(block.confirmation_window_start)}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="secondary"
                      size="sm"
                      loading={busy === block.id}
                      disabled={busy === block.id}
                      onClick={() => act(block, "confirm")}
                    >
                      Confirm
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      loading={busy === block.id}
                      disabled={busy === block.id}
                      onClick={() => act(block, "release")}
                    >
                      Release
                    </Button>
                    <Link
                      href={`/dashboard/plans/${block.plan_id}`}
                      className="inline-flex items-center gap-1 text-xs font-medium text-brand-primary hover:underline"
                    >
                      Plan
                      <RefreshCw className="h-3 w-3" aria-hidden="true" />
                    </Link>
                  </div>
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
