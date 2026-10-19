import { redirect } from "next/navigation";

import { Download, FileCheck2, Info } from "lucide-react";

import { getCurrentUser } from "@/lib/auth";
import {
  APPROVED_STATUS,
  formatFileSize,
  listApprovedDocuments,
  type HubApprovedDocument,
} from "@/lib/documents/hub";
import { formatDateTime } from "@/lib/tracking/format";
import { FadeIn } from "@/components/motion/FadeIn";
import { Badge } from "@/components/ui/badge";
import { EmptyState, ErrorState } from "@/components/ui/states";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

const LOAD_ERROR = "Unable to load approved documents.";

async function ApprovedDocumentsPage() {
  const user = await getCurrentUser();
  if (!user) {
    redirect("/login");
  }

  const result = await listApprovedDocuments().then(
    (value) => ({ value, error: "" }),
    () => ({ value: [] as HubApprovedDocument[], error: LOAD_ERROR })
  );

  // An employee's list is their own; the applicant column only earns its width
  // once the viewer can read other people's documents.
  const showsApplicant =
    user.role === "hr" ||
    user.is_superuser === true ||
    user.manages_teams === true;

  return (
    <FadeIn>
      <div className="space-y-6">
        <div className="max-w-2xl">
          <h1 className="text-2xl font-bold tracking-tight text-text-primary">
            Approved Documents
          </h1>
          <p className="mt-1 text-text-secondary">
            The leave documents generated once an application is approved. A
            document still being prepared stays on this list rather than
            disappearing until it is ready.
          </p>
        </div>

        <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
          {result.error ? (
            <ErrorState title={LOAD_ERROR} message={result.error} />
          ) : result.value.length === 0 ? (
            <EmptyState
              icon={<FileCheck2 className="h-6 w-6" />}
              title="No approved documents yet"
              description="Once an application is approved, its generated leave document is filed here."
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Document</TableHead>
                  {showsApplicant && <TableHead>Employee</TableHead>}
                  <TableHead>Application</TableHead>
                  <TableHead>Approved</TableHead>
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
                          <FileCheck2 className="h-4 w-4" />
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
                      {row.approved_on ? (
                        formatDateTime(row.approved_on)
                      ) : (
                        <span className="text-text-muted">—</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge tone={APPROVED_STATUS[row.status].tone} size="sm">
                        {APPROVED_STATUS[row.status].label}
                      </Badge>
                      {!row.available && (
                        <span className="mt-1 block text-xs text-text-muted">
                          {row.status === "failed"
                            ? "It could not be generated. Ask HR to re-run it."
                            : "Generated on approval; open it once it is ready."}
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <RowLink href={row.download_url} label={row.file_name} />
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
 * Only offered while the backend promises the URL opens now: a signed link is
 * re-minted at read time, and a row that is still being prepared has none to
 * give, so the cell says so instead of handing over a dead button.
 */
function RowLink({ href, label }: { href: string; label: string }) {
  if (!href) {
    return (
      <span className="inline-flex items-center gap-1.5 text-sm text-text-muted">
        <Info className="h-4 w-4" aria-hidden="true" />
        Not available
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

export default ApprovedDocumentsPage;
