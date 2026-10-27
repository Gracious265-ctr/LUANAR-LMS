import { redirect } from "next/navigation";

import { FileCheck2 } from "lucide-react";

import { getCurrentUser } from "@/lib/auth";
import {
  APPROVED_STATUS,
  formatFileSize,
  listApprovedDocuments,
  type HubApprovedDocument,
} from "@/lib/documents/hub";
import { formatDateTime } from "@/lib/tracking/format";
import { DocumentsTable } from "@/components/documents/documents-table";
import { FadeIn } from "@/components/motion/FadeIn";
import { EmptyState, ErrorState } from "@/components/ui/states";

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

  const rows = result.value.map((row) => ({
    id: row.id,
    fileName: row.file_name,
    fileSizeLabel: formatFileSize(row.file_size),
    employeeName: row.employee.full_name,
    reference: row.application.reference_number || row.application.id,
    dateLabel: row.approved_on ? formatDateTime(row.approved_on) : "—",
    statusLabel: APPROVED_STATUS[row.status].label,
    statusTone: APPROVED_STATUS[row.status].tone,
    note: row.available
      ? undefined
      : row.status === "failed"
        ? "It could not be generated. Ask HR to re-run it."
        : "Generated on approval; open it once it is ready.",
    href: row.download_url,
    unavailableLabel: "Not available",
  }));

  return (
    <FadeIn>
      <div className="space-y-6">
        <div className="max-w-2xl">
          <h1 className="text-2xl font-bold tracking-tight text-text-primary">
            Approved Documents
          </h1>
          <p className="mt-1 text-text-secondary">Leave documents generated for approved applications.</p>
        </div>

        <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
          {result.error ? (
            <ErrorState title={LOAD_ERROR} message={result.error} />
          ) : result.value.length === 0 ? (
            <EmptyState
              icon={<FileCheck2 className="h-6 w-6" />}
              title="No approved documents yet"
              description="Generated documents are filed here once an application is approved."
            />
          ) : (
            <DocumentsTable
              rows={rows}
              showsApplicant={showsApplicant}
              kind="approved"
              dateHeading="Approved"
              searchLabel="Search approved documents"
            />
          )}
        </div>
      </div>
    </FadeIn>
  );
}

export default ApprovedDocumentsPage;
