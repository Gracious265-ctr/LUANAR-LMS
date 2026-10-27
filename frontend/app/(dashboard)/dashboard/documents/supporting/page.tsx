import Link from "next/link";
import { redirect } from "next/navigation";

import { FileText } from "lucide-react";

import { getCurrentUser } from "@/lib/auth";
import {
  formatFileSize,
  listSupportingDocuments,
  retireReasonLabel,
  SUPPORTING_STATUS,
  type HubSupportingDocument,
} from "@/lib/documents/hub";
import { formatDateTime } from "@/lib/tracking/format";
import { DocumentsTable } from "@/components/documents/documents-table";
import { FadeIn } from "@/components/motion/FadeIn";
import {
  EmptyState,
  ErrorState,
} from "@/components/ui/states";

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

  const rows = result.value.map((row) => ({
    id: row.id,
    fileName: row.file_name,
    fileSizeLabel: formatFileSize(row.file_size),
    employeeName: row.employee.full_name,
    reference: row.application.reference_number || row.application.id,
    dateLabel: formatDateTime(row.uploaded_at),
    statusLabel: SUPPORTING_STATUS[row.status].label,
    statusTone: SUPPORTING_STATUS[row.status].tone,
    note:
      row.status === "retired"
        ? `${retireReasonLabel(row.retire_reason)}${
            row.retired_at ? ` · ${formatDateTime(row.retired_at)}` : ""
          }`
        : undefined,
    href: row.file_url,
    unavailableLabel: "Unavailable",
  }));

  return (
    <FadeIn>
      <div className="space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-2xl">
            <h1 className="text-2xl font-bold tracking-tight text-text-primary">
              Supporting Documents
            </h1>
            <p className="mt-1 text-text-secondary">Every file uploaded alongside a leave application.</p>
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
              description="Files uploaded with an application appear here."
            />
          ) : (
            <DocumentsTable
              rows={rows}
              showsApplicant={showsApplicant}
              kind="supporting"
              dateHeading="Uploaded"
              searchLabel="Search supporting documents"
            />
          )}
        </div>
      </div>
    </FadeIn>
  );
}

export default SupportingDocumentsPage;
