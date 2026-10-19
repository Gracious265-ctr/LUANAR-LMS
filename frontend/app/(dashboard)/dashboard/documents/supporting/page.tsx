import Link from "next/link";
import { redirect } from "next/navigation";

import { Download, FileText, Info } from "lucide-react";

import { getCurrentUser } from "@/lib/auth";
import {
  formatFileSize,
  listSupportingDocuments,
  retireReasonLabel,
  SUPPORTING_STATUS,
  type HubSupportingDocument,
} from "@/lib/documents/hub";
import { formatDateTime } from "@/lib/tracking/format";
import { FadeIn } from "@/components/motion/FadeIn";
import {
  EmptyState,
  ErrorState,
} from "@/components/ui/states";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const LOAD_ERROR = "Unable to load supporting documents.";

async function SupportingDocumentsPage({
  searchParams,
}: {
  searchParams: Promise<{ retired?: string }>;
}) {
  const user = await getCurrentUser();
  if (!user) {
    redirect("/login");
  }

  const { retired } = await searchParams;
  const includeRetired = retired === "1";

  const result = await listSupportingDocuments({ includeRetired }).then(
    (value) => ({ value, error: "" }),
    () => ({ value: [] as HubSupportingDocument[], error: LOAD_ERROR })
  );

  // An employee's list is their own; the applicant column only earns its width
  // once the viewer can read other people's documents.
  const showsApplicant =
    user.role === "hr" ||
    user.is_superuser === true ||
    user.manages_teams === true;

  const filters = [
    {
      label: "On file",
      href: "/dashboard/documents/supporting",
      current: !includeRetired,
    },
    {
      label: "Including retired",
      href: "/dashboard/documents/supporting?retired=1",
      current: includeRetired,
    },
  ];

  return (
    <FadeIn>
      <div className="space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-2xl">
            <h1 className="text-2xl font-bold tracking-tight text-text-primary">
              Supporting Documents
            </h1>
            <p className="mt-1 text-text-secondary">
              Every file uploaded alongside a leave application. Retirement
              keeps the record of what was replaced instead of deleting it.
            </p>
          </div>

          <div
            className="flex flex-wrap gap-1 rounded-lg border border-border-default bg-surface-card p-1"
            role="group"
            aria-label="Filter supporting documents"
          >
            {filters.map((filter) => (
              <Link
                key={filter.href}
                href={filter.href}
                aria-pressed={filter.current}
                className={
                  filter.current
                    ? "rounded-md bg-brand-primary-subtle px-3 py-1.5 text-sm font-medium text-brand-primary"
                    : "rounded-md px-3 py-1.5 text-sm font-medium text-text-secondary hover:bg-surface-hover hover:text-text-primary"
                }
              >
                {filter.label}
              </Link>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
          {result.error ? (
            <ErrorState title={LOAD_ERROR} message={result.error} />
          ) : result.value.length === 0 ? (
            <EmptyState
              icon={<FileText className="h-6 w-6" />}
              title="No supporting documents yet"
              description="A file uploaded with an application appears here, along with the application it belongs to."
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Document</TableHead>
                  {showsApplicant && <TableHead>Employee</TableHead>}
                  <TableHead>Application</TableHead>
                  <TableHead>Uploaded</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>
                    <span className="sr-only">Open</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {result.value.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell>
                      <div className="flex items-center gap-3">
                        <span
                          className="grid size-8 shrink-0 place-content-center rounded-md bg-surface-muted text-text-muted"
                          aria-hidden="true"
                        >
                          <FileText className="h-4 w-4" />
                        </span>
                        <div className="min-w-0">
                          <p
                            className="truncate font-medium text-text-primary"
                            title={row.file_name}
                          >
                            {row.file_name}
                          </p>
                          <p className="text-xs text-text-muted">
                            {formatFileSize(row.file_size)}
                          </p>
                        </div>
                      </div>
                    </TableCell>
                    {showsApplicant && (
                      <TableCell className="whitespace-nowrap text-text-primary">
                        {row.employee.full_name}
                      </TableCell>
                    )}
                    <TableCell className="whitespace-nowrap font-mono text-xs">
                      {row.application.reference_number || row.application.id}
                    </TableCell>
                    <TableCell className="whitespace-nowrap">
                      {formatDateTime(row.uploaded_at)}
                    </TableCell>
                    <TableCell>
                      <Badge
                        tone={SUPPORTING_STATUS[row.status].tone}
                        size="sm"
                      >
                        {SUPPORTING_STATUS[row.status].label}
                      </Badge>
                      {row.status === "retired" && (
                        <span className="mt-1 block text-xs text-text-muted">
                          {retireReasonLabel(row.retire_reason)}
                          {row.retired_at
                            ? ` · ${formatDateTime(row.retired_at)}`
                            : ""}
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <RowLink href={row.file_url} label={row.file_name} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </div>
      </div>
    </FadeIn>
  );
}

/**
 * The download, pointed straight at storage.
 *
 * The backend signs the URL and the browser opens it as a new tab: the file is
 * never proxied through Next.js, so a document does not occupy a server
 * response while someone reads it.
 */
function RowLink({ href, label }: { href: string; label: string }) {
  if (!href) {
    return (
      <span className="inline-flex items-center gap-1.5 text-sm text-text-muted">
        <Info className="h-4 w-4" aria-hidden="true" />
        Unavailable
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

export default SupportingDocumentsPage;
