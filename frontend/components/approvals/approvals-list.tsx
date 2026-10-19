"use client";

import { CheckCircle2, ChevronRight, Inbox, RefreshCw, Search, SearchX } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { formatDate, formatDateTime } from "@/lib/approvals/format";
import { fetchApprovals } from "@/lib/approvals/service";
import type {
  ApprovalListItem,
  ApprovalListResponse,
  ApprovalTab,
  BulkApprovalResponse,
} from "@/lib/approvals/types";
import { cn } from "@/lib/utils";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Pagination } from "@/components/ui/pagination";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Alert } from "@/components/ui/alert";
import { EmptyState } from "@/components/ui/states";
import { Avatar } from "@/components/ui/Avatar";
import { pushToast } from "@/components/ui/toast";

import { ActionBadge, StatusBadge } from "./badges";
import { BulkApproveDialog } from "./bulk-approve-dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card } from "@/components/ui/card";

/** A batch approval is capped at 25 applications (spec 3.11). */
const BULK_LIMIT = 25;

const BULK_REASON_LABELS: Record<string, string> = {
  stage_changed: "already decided",
  team_conflict: "team would be over-subscribed",
  not_found: "no longer available",
  workflow_unavailable: "no approver available",
  application_closed: "no longer awaiting your decision",
  already_decided: "already decided",
  not_current_stage: "not with you right now",
  self_application: "you cannot decide your own application",
  validation: "could not be approved",
};

interface BulkFailure {
  reference: string;
  reason: string;
}

function useDebounced(value: string, delay = 300): string {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

export function ApprovalsList({ headerless = false }: { headerless?: boolean }) {
  const [tab, setTab] = useState<ApprovalTab>("pending");
  const [qInput, setQInput] = useState("");
  const q = useDebounced(qInput);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<ApprovalListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  const [selected, setSelected] = useState<Record<string, number>>({});
  const [bulkOpen, setBulkOpen] = useState(false);
  const [bulkLabels, setBulkLabels] = useState<Record<string, string>>({});
  const [bulkResult, setBulkResult] = useState<{
    approved: number;
    failed: number;
    failures: BulkFailure[];
  } | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchApprovals(tab, q, page)
      .then((result) => {
        if (cancelled) return;
        if (result.ok) {
          setData(result.data);
          setError("");
        } else {
          setError(result.message);
        }
      })
      .catch(() => {
        if (!cancelled) setError("Failed to load approvals.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [tab, q, page, reloadKey]);

  const selectedCount = Object.keys(selected).length;
  const bulkItems = Object.entries(selected).map(([id, stage_version]) => ({
    id,
    stage_version,
  }));

  function resetSelection() {
    setSelected({});
    setBulkResult(null);
  }

  function switchTab(next: ApprovalTab) {
    if (next === tab) return;
    setTab(next);
    setPage(1);
    resetSelection();
  }

  function retry() {
    setError("");
    setLoading(true);
    setReloadKey((value) => value + 1);
    resetSelection();
  }

  function onSearchChange(value: string) {
    setQInput(value);
    setPage(1);
    resetSelection();
  }

  /** The "Clear filters" action on the no-results empty state. */
  function clearSearch() {
    setQInput("");
    setPage(1);
    resetSelection();
  }

  function goToPage(next: number) {
    setPage(next);
    resetSelection();
  }

  function toggleRow(row: ApprovalListItem) {
    setSelected((current) => {
      const next = { ...current };
      if (row.id in next) {
        delete next[row.id];
        return next;
      }
      if (row.stage_version == null) return current;
      if (Object.keys(next).length >= BULK_LIMIT) return current;
      next[row.id] = row.stage_version;
      return next;
    });
  }

  function selectAllOnPage() {
    setSelected((current) => {
      const next = { ...current };
      for (const row of data?.results ?? []) {
        if (row.stage_version == null) continue;
        if (Object.keys(next).length >= BULK_LIMIT) break;
        next[row.id] = row.stage_version;
      }
      return next;
    });
  }

  function openBulk() {
    const labels: Record<string, string> = {};
    for (const row of data?.results ?? []) {
      if (row.id in selected) labels[row.id] = row.reference;
    }
    setBulkLabels(labels);
    setBulkOpen(true);
  }

  function handleBulkDone(result: BulkApprovalResponse) {
    setBulkOpen(false);
    const failures: BulkFailure[] = result.results
      .filter((item) => item.status === "failed")
      .map((item) => ({
        reference: bulkLabels[item.id] || item.id,
        reason: item.reason || "unknown",
      }));
    setSelected({});
    setBulkResult({
      approved: result.approved,
      failed: result.failed,
      failures,
    });
    if (result.approved > 0) {
      pushToast(
        `${result.approved} application${result.approved === 1 ? "" : "s"} approved`,
        "success"
      );
    }
    if (result.failed > 0) {
      pushToast(`${result.failed} could not be approved`, "warning");
    }
    setLoading(true);
    setReloadKey((value) => value + 1);
  }

  const showBulkTools =
    tab === "pending" && Boolean(data) && (data?.results.length ?? 0) > 0;
  const atCap = selectedCount >= BULK_LIMIT;
  const hasSelectableRows = (data?.results ?? []).some(
    (row) => row.stage_version != null
  );

  return (
    <div className={cn("space-y-6", !headerless && "mx-auto max-w-5xl")}>
      {!headerless && (
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-text-primary">Approvals</h1>
          <p className="text-sm text-text-secondary">
            Applications waiting for your decision.
          </p>
        </div>
      )}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Tabs
          value={tab}
          className="contents"
          onValueChange={(next) => switchTab(next as ApprovalTab)}
        >
          <TabsList variant="segmented" aria-label="Approvals list">
            <TabsTrigger variant="segmented" value="pending">
              Pending my decision
              {data && tab === "pending" && (
                <span className="inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-brand-primary px-1 text-[10px] font-semibold text-white">
                  {data.count}
                </span>
              )}
            </TabsTrigger>
            <TabsTrigger variant="segmented" value="decided">
              Decided by me
            </TabsTrigger>
          </TabsList>
        </Tabs>

        <div className="relative w-full sm:w-72">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted"
            aria-hidden="true"
          />
          <input
            type="search"
            value={qInput}
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder="Reference or employee name…"
            aria-label="Search approvals"
            className="w-full rounded-md border border-input-border bg-input-background py-2 pl-9 pr-3 text-sm text-text-primary placeholder:text-text-placeholder focus:border-input-border-focus focus:outline-none focus:ring-2 focus:ring-input-ring-focus"
          />
        </div>
      </div>

      {showBulkTools && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border-default bg-surface-card px-3 py-2">
          <div className="flex flex-wrap items-center gap-3">
            <span
              className="text-sm font-medium text-text-primary"
              aria-live="polite"
            >
              {selectedCount} of {BULK_LIMIT} selected
            </span>
            <Button
              type="button"
              variant="link"
              size="sm"
              onClick={selectAllOnPage}
              disabled={atCap || !hasSelectableRows}
            >
              Select all on this page
            </Button>
            {selectedCount > 0 && (
              <Button
                type="button"
                variant="link"
                size="sm"
                onClick={() => setSelected({})}
              >
                Clear
              </Button>
            )}
          </div>
          <Button
            type="button"
            variant="primary"
            size="sm"
            onClick={openBulk}
            disabled={selectedCount === 0}
          >
            Approve selected
          </Button>
        </div>
      )}

      {bulkResult && bulkResult.failures.length > 0 && (
        <Alert tone="rejected">
          <p className="font-medium">
            {bulkResult.failed} could not be approved.
          </p>
          <ul className="mt-1 list-disc space-y-0.5 pl-4">
            {bulkResult.failures.map((failure, index) => (
              <li key={`${failure.reference}-${index}`}>
                {failure.reference} —{" "}
                {BULK_REASON_LABELS[failure.reason] || failure.reason}
              </li>
            ))}
          </ul>
        </Alert>
      )}

      {error ? (
        <Card className="text-center">
          <p className="text-sm text-status-rejected">{error}</p>
          <Button type="button" onClick={retry} variant="primary" className="mt-4">
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Retry
          </Button>
        </Card>
      ) : loading ? (
        <SkeletonRows count={6} />
      ) : !data || data.results.length === 0 ? (
        <Card>
          {q ? (
            <EmptyState
              icon={<SearchX className="h-10 w-10" />}
              title={`No results for "${q}"`}
              description="Check the reference number or employee name and try again."
              action={
                <Button type="button" variant="secondary" onClick={clearSearch}>
                  Clear filters
                </Button>
              }
            />
          ) : tab === "pending" ? (
            <EmptyState
              icon={<CheckCircle2 className="h-10 w-10" />}
              title="Nothing pending your review"
              description="New applications will appear here as they are submitted."
            />
          ) : (
            <EmptyState
              icon={<Inbox className="h-10 w-10" />}
              title="You have not decided on any applications yet"
              description="Applications you have decided on will appear here."
            />
          )}
        </Card>
      ) : (
        <>
          <ApprovalTable
            rows={data.results}
            tab={tab}
            selected={selected}
            atCap={atCap}
            onToggle={toggleRow}
          />
          <Pagination
            page={page}
            hasPrevious={Boolean(data.previous) || page > 1}
            hasNext={Boolean(data.next)}
            onPrevious={() => goToPage(Math.max(1, page - 1))}
            onNext={() => goToPage(page + 1)}
          />
        </>
      )}

      <BulkApproveDialog
        open={bulkOpen}
        items={bulkItems}
        onClose={() => setBulkOpen(false)}
        onDone={handleBulkDone}
      />
    </div>
  );
}

function ApprovalTable({
  rows,
  tab,
  selected,
  atCap,
  onToggle,
}: {
  rows: ApprovalListResponse["results"];
  tab: ApprovalTab;
  selected: Record<string, number>;
  atCap: boolean;
  onToggle: (row: ApprovalListItem) => void;
}) {
  const selectable = tab === "pending";
  return (
    <>
      <Card className="hidden overflow-hidden md:block">
        <Table>
          <TableHeader>
            <TableRow>
              {selectable && (
                <TableHead className="w-10 px-2">
                  <span className="sr-only">Select</span>
                </TableHead>
              )}
              <TableHead>Reference</TableHead>
              <TableHead>Employee</TableHead>
              <TableHead>Leave type</TableHead>
              <TableHead>Dates</TableHead>
              <TableHead>Days</TableHead>
              <TableHead>Submitted</TableHead>
              {tab === "decided" && <TableHead>Your decision</TableHead>}
              <TableHead>Status</TableHead>
              <TableHead className="w-8 px-2" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <ApprovalTableRow
                key={row.id}
                row={row}
                tab={tab}
                selected={selected}
                atCap={atCap}
                onToggle={onToggle}
                desktop
              />
            ))}
          </TableBody>
        </Table>
      </Card>

      <ul className="space-y-3 md:hidden">
        {rows.map((row) => (
          <ApprovalTableRow
            key={row.id}
            row={row}
            tab={tab}
            selected={selected}
            atCap={atCap}
            onToggle={onToggle}
          />
        ))}
      </ul>
    </>
  );
}

function ApprovalTableRow({
  row,
  tab,
  selected,
  atCap,
  onToggle,
  desktop,
}: {
  row: ApprovalListItem;
  tab: ApprovalTab;
  selected: Record<string, number>;
  atCap: boolean;
  onToggle: (row: ApprovalListItem) => void;
  desktop?: boolean;
}) {
  const decision = row.my_decision;
  const selectable = tab === "pending" && row.stage_version != null;
  const isSelected = row.id in selected;
  const checkbox = selectable ? (
    <Checkbox
      aria-label={`Select ${row.reference}`}
      checked={isSelected}
      disabled={!isSelected && atCap}
      onCheckedChange={() => onToggle(row)}
    />
  ) : null;

  if (desktop) {
    return (
      <TableRow className="relative">
        {tab === "pending" && (
          <TableCell className="relative z-10 w-10 px-2">{checkbox}</TableCell>
        )}
        <TableCell className="font-medium text-text-primary">
          <Link
            href={`/dashboard/approvals/${row.id}`}
            className="after:absolute after:inset-0 after:content-['']"
          >
            {row.reference}
          </Link>
        </TableCell>
        <TableCell>
          <div className="flex items-center gap-2">
            <Avatar
              name={row.employee_name}
              userId={row.employee_name}
              size="sm"
            />
            <div className="min-w-0">
              <span className="font-medium text-text-primary">
                {row.employee_name}
              </span>
              <span className="mt-0.5 block text-xs text-text-muted">
                {row.team || "—"}
              </span>
            </div>
          </div>
        </TableCell>
        <TableCell className="text-text-secondary">
          {row.leave_type.name || "—"}
        </TableCell>
        <TableCell className="text-text-secondary">
          {formatDate(row.start_date) || "—"} → {formatDate(row.end_date) || "—"}
        </TableCell>
        <TableCell className="text-text-secondary">{row.working_days}</TableCell>
        <TableCell className="text-text-secondary">
          {formatDateTime(row.submitted_at) || "—"}
        </TableCell>
        {tab === "decided" && (
          <TableCell>
            {decision ? (
              <>
                <ActionBadge action={decision.action} />
                <span className="mt-0.5 block text-xs text-text-muted">
                  {decision.decided_at ? formatDateTime(decision.decided_at) : ""}
                </span>
              </>
            ) : (
              <span className="text-text-muted">—</span>
            )}
          </TableCell>
        )}
        <TableCell>
          <StatusBadge status={row.status} />
        </TableCell>
        <TableCell className="px-2">
          <ChevronRight className="h-4 w-4 text-text-muted" aria-hidden="true" />
        </TableCell>
      </TableRow>
    );
  }

  return (
    <li className="rounded-xl border border-border-default bg-surface-card p-4 shadow-subtle">
      <div className="flex items-start gap-3">
        {tab === "pending" && <div className="pt-0.5">{checkbox}</div>}
        <Link
          href={`/dashboard/approvals/${row.id}`}
          className="flex min-w-0 flex-1 items-center justify-between gap-3"
        >
          <div className="min-w-0">
            <p className="truncate font-medium text-text-primary">{row.reference}</p>
            <p className="truncate text-sm text-text-secondary">{row.employee_name}</p>
            <p className="mt-1 text-xs text-text-muted">
              {row.leave_type.name || "—"} · {formatDate(row.start_date) || "—"} →{" "}
              {formatDate(row.end_date) || "—"}
            </p>
            {tab === "decided" && decision && (
              <p className="mt-1">
                <ActionBadge action={decision.action} />
              </p>
            )}
          </div>
          <div className="flex shrink-0 flex-col items-end gap-2">
            <StatusBadge status={row.status} />
            <ChevronRight className="h-4 w-4 text-text-muted" aria-hidden="true" />
          </div>
        </Link>
      </div>
    </li>
  );
}

function SkeletonRows({ count }: { count: number }) {
  return (
    <div className="space-y-3" aria-busy="true" aria-live="polite">
      {Array.from({ length: count }).map((_, index) => (
        <div
          key={index}
          className="h-14 animate-pulse rounded-xl border border-border-default bg-surface-card"
        />
      ))}
    </div>
  );
}
