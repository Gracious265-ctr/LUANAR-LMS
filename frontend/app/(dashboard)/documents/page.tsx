import Link from "next/link";
import { CheckCircle2, ClipboardList, FileText } from "lucide-react";

import { FadeIn } from "@/components/motion/FadeIn";
import { Card } from "@/components/ui/card";

export default function DocumentsPage() {
  return (
    <FadeIn>
      <div className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold tracking-tight text-text-primary">
            Documents
          </h2>
          <p className="text-text-secondary">
            Supporting documents are attached to individual leave applications,
            and approved leave documents are generated when an application is
            finalized.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Link
            href="/leave/drafts"
            className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle transition-colors hover:bg-surface-hover"
          >
            <div className="mb-3 inline-flex rounded-lg bg-brand-primary-subtle p-2 text-brand-primary">
              <ClipboardList className="h-5 w-5" />
            </div>
            <h3 className="text-lg font-semibold text-text-primary">
              Application documents
            </h3>
            <p className="mt-1 text-sm text-text-secondary">
              Upload, view, replace, or remove the supporting documents required
              by a leave type, from the application itself.
            </p>
          </Link>
          <Link
            href="/approvals"
            className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle transition-colors hover:bg-surface-hover"
          >
            <div className="mb-3 inline-flex rounded-lg bg-brand-primary-subtle p-2 text-brand-primary">
              <CheckCircle2 className="h-5 w-5" />
            </div>
            <h3 className="text-lg font-semibold text-text-primary">
              Approved documents
            </h3>
            <p className="mt-1 text-sm text-text-secondary">
              Download the generated document for finalized leave from the
              application&apos;s approval record.
            </p>
          </Link>
        </div>

        <Card className="flex items-start gap-3 text-sm text-text-muted">
          <FileText className="mt-0.5 h-4 w-4 shrink-0" />
          <p>
            There is no separate document library yet — records live with the
            leave application or approval they belong to.
          </p>
        </Card>
      </div>
    </FadeIn>
  );
}
