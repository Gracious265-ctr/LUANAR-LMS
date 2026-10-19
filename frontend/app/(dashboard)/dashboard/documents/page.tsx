import Link from "next/link";
import { redirect } from "next/navigation";

import { ArrowRight, FileCheck2, FileText } from "lucide-react";

import { getCurrentUser } from "@/lib/auth";
import {
  listApprovedDocuments,
  listSupportingDocuments,
  type HubApprovedDocument,
  type HubSupportingDocument,
} from "@/lib/documents/hub";
import { FadeIn } from "@/components/motion/FadeIn";
import { Card } from "@/components/ui/card";

const SUPPORTING_ERROR = "Could not be counted right now.";
const APPROVED_ERROR = "Could not be counted right now.";

const TWO_COLUMN =
  "grid gap-4 md:grid-cols-2 lg:max-w-4xl lg:grid-cols-2";

/**
 * The Documents hub: the two lists, side by side.
 *
 * Both are counted here so the cards answer "is there anything for me?" before
 * the click, and a viewer always sees the same scope on the card that they
 * will see on the list — the count and the table come from one query each.
 * The counting is best-effort: a list that fails still opens normally, it just
 * says so here rather than blocking the route.
 */
export default async function DocumentsHubPage() {
  const user = await getCurrentUser();
  if (!user) {
    redirect("/login");
  }

  const [supportingResult, approvedResult] = await Promise.all([
    listSupportingDocuments().then(
      (value) => ({ value, error: "" }),
      () => ({ value: [] as HubSupportingDocument[], error: SUPPORTING_ERROR })
    ),
    listApprovedDocuments().then(
      (value) => ({ value, error: "" }),
      () => ({ value: [] as HubApprovedDocument[], error: APPROVED_ERROR })
    ),
  ]);

  return (
    <FadeIn>
      <div className="space-y-6">
        <div className="max-w-2xl">
          <h1 className="text-2xl font-bold tracking-tight text-text-primary">
            Documents
          </h1>
          <p className="mt-1 text-text-secondary">
            Everything filed against a leave application — your own, and the
            people you cover if you manage a team. Choose a list to open it.
          </p>
        </div>

        <div className={TWO_COLUMN}>
          <HubCard
            href="/dashboard/documents/supporting"
            icon={<FileText className="h-5 w-5" />}
            title="Supporting Documents"
            description="Receipts, letters, and every other file uploaded alongside an application."
            count={supportingResult.value.length}
            countLabel={(n) => (n === 1 ? "1 on file" : `${n} on file`)}
            error={supportingResult.error}
          />
          <HubCard
            href="/dashboard/documents/approved"
            icon={<FileCheck2 className="h-5 w-5" />}
            title="Approved Documents"
            description="The generated leave documents ready to open and print."
            count={approvedResult.value.length}
            countLabel={(n) => (n === 1 ? "1 ready" : `${n} ready`)}
            error={approvedResult.error}
          />
        </div>
      </div>
    </FadeIn>
  );
}

/**
 * One destination, described.
 *
 * Whole-card link rather than a button, so the count and the description are
 * all part of the same target.
 */
function HubCard({
  href,
  icon,
  title,
  description,
  count,
  countLabel,
  error,
}: {
  href: string;
  icon: React.ReactNode;
  title: string;
  description: string;
  count: number;
  countLabel: (count: number) => string;
  error?: string;
}) {
  return (
    <Link href={href} className="group block h-full">
      <Card interactive className="flex h-full flex-col gap-4">
        <div className="flex items-start justify-between gap-3">
          <span
            className="grid size-10 shrink-0 place-content-center rounded-md bg-brand-primary-subtle text-brand-primary"
            aria-hidden="true"
          >
            {icon}
          </span>
          <ArrowRight className="h-4 w-4 text-text-muted transition group-hover:translate-x-0.5 group-hover:text-brand-primary" />
        </div>

        <div>
          <h2 className="text-lg font-semibold text-text-primary">{title}</h2>
          <p className="mt-1 text-sm text-text-secondary">{description}</p>
        </div>

        <p className="mt-auto pt-2 text-sm font-medium text-text-muted">
          {error ? (
            <span className="text-status-rejected">{error}</span>
          ) : (
            countLabel(count)
          )}
        </p>
      </Card>
    </Link>
  );
}
