"use client";

import { useMemo, useState } from "react";

import { Download, FileCheck2, FileText, Info } from "lucide-react";

import { matchesSearch } from "@/lib/search";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { ListSearch } from "@/components/ui/list-search";
import { EmptyState } from "@/components/ui/states";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

/** One filing-cabinet row, already formatted by the server page. */
export interface DocumentRow {
  id: string;
  fileName: string;
  /** "12.4 KB", formatted where the server's own helper lives. */
  fileSizeLabel: string;
  employeeName: string;
  /** The application reference, or its id while no reference exists. */
  reference: string;
  dateLabel: string;
  statusLabel: string;
  statusTone: BadgeTone;
  /** Extra line under the status, e.g. why a file was retired. */
  note?: string;
  href: string;
  unavailableLabel: string;
}

/**
 * The two document lists share this table.
 *
 * Supporting and approved documents are the same shape — a file, whose it is,
 * the application it belongs to, a date, and whether it can be opened — so the
 * search and the table live here once instead of twice. The server page keeps
 * the fetch, the scope, and the formatting; this component only narrows what
 * it was handed, which also keeps `lib/documents/hub.ts` (and its server-only
 * API client) out of the browser bundle.
 */
export function DocumentsTable({
  rows,
  showsApplicant,
  kind,
  dateHeading,
  searchLabel,
}: {
  rows: DocumentRow[];
  /** False for an employee reading only their own filings. */
  showsApplicant: boolean;
  kind: "supporting" | "approved";
  dateHeading: string;
  searchLabel: string;
}) {
  const [search, setSearch] = useState("");

  const visible = useMemo(
    () =>
      rows.filter((row) =>
        matchesSearch(search, [
          row.fileName,
          row.employeeName,
          row.reference,
          row.dateLabel,
          row.statusLabel,
        ])
      ),
    [rows, search]
  );

  const Icon = kind === "approved" ? FileCheck2 : FileText;

  return (
    <div className="space-y-4">
      <ListSearch
        value={search}
        onChange={setSearch}
        label={searchLabel}
        placeholder="Search by file, employee, reference, or status"
        className="w-full sm:w-80"
      />

      {visible.length === 0 ? (
        <EmptyState
          icon={<Icon className="h-6 w-6" />}
          title="No documents match this search"
          description="Try a different file name, employee, reference, or status."
        />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Document</TableHead>
              {showsApplicant && <TableHead>Employee</TableHead>}
              <TableHead>Application</TableHead>
              <TableHead>{dateHeading}</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>
                <span className="sr-only">Open</span>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {visible.map((row) => (
              <TableRow key={row.id}>
                <TableCell>
                  <div className="flex items-center gap-3">
                    <span
                      className="grid size-8 shrink-0 place-content-center rounded-md bg-surface-muted text-text-muted"
                      aria-hidden="true"
                    >
                      <Icon className="h-4 w-4" />
                    </span>
                    <div className="min-w-0">
                      <p
                        className="truncate font-medium text-text-primary"
                        title={row.fileName}
                      >
                        {row.fileName}
                      </p>
                      <p className="text-xs text-text-muted">
                        {row.fileSizeLabel}
                      </p>
                    </div>
                  </div>
                </TableCell>
                {showsApplicant && (
                  <TableCell className="whitespace-nowrap text-text-primary">
                    {row.employeeName}
                  </TableCell>
                )}
                <TableCell className="whitespace-nowrap font-mono text-xs">
                  {row.reference}
                </TableCell>
                <TableCell className="whitespace-nowrap">
                  {row.dateLabel}
                </TableCell>
                <TableCell>
                  <Badge tone={row.statusTone} size="sm">
                    {row.statusLabel}
                  </Badge>
                  {row.note && (
                    <span className="mt-1 block text-xs text-text-muted">
                      {row.note}
                    </span>
                  )}
                </TableCell>
                <TableCell className="text-right">
                  <RowLink
                    href={row.href}
                    label={row.fileName}
                    unavailableLabel={row.unavailableLabel}
                  />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}

/**
 * The download, pointed straight at storage.
 *
 * The backend signs the URL and the browser opens it as a new tab: the file is
 * never proxied through Next.js, so a document does not occupy a server
 * response while someone reads it.
 */
function RowLink({
  href,
  label,
  unavailableLabel,
}: {
  href: string;
  label: string;
  unavailableLabel: string;
}) {
  if (!href) {
    return (
      <span className="inline-flex items-center gap-1.5 text-sm text-text-muted">
        <Info className="h-4 w-4" aria-hidden="true" />
        {unavailableLabel}
      </span>
    );
  }
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-sm font-medium text-brand-primary hover:bg-surface-hover hover:underline"
    >
      <Download className="h-4 w-4" aria-hidden="true" />
      Open
      <span className="sr-only"> {label} in a new tab</span>
    </a>
  );
}
