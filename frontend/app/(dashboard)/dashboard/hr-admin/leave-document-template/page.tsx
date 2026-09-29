import { redirect } from "next/navigation";

import { LeaveDocumentTemplateEditor } from "@/components/hr/leave-document-template-editor";
import { getCurrentUser } from "@/lib/auth";
import { getLeaveDocumentTemplate } from "@/lib/leave-document-template";

export default async function LeaveDocumentTemplatePage() {
  const user = await getCurrentUser();

  if (!user) {
    redirect("/login");
  }
  if (user.role !== "hr") {
    redirect("/dashboard");
  }

  let template;
  let templateError = "";
  try {
    template = await getLeaveDocumentTemplate();
  } catch {
    templateError = "Unable to load the document template. Please try again.";
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold tracking-tight text-text-primary">
          Approved Leave Document Template
        </h2>
        <p className="text-text-secondary">
          Configure the official template used for approved leave documents:
          branding wording, official text, data fields, and signature areas.
          The data itself always comes from the approved application record;
          values are never edited here.
        </p>
      </div>

      {templateError ? (
        <div className="rounded-md bg-status-rejected-subtle py-12 text-center text-sm text-status-rejected">
          {templateError}
        </div>
      ) : template ? (
        <div className="rounded-xl border border-border-default bg-surface-card p-6 shadow-subtle">
          <LeaveDocumentTemplateEditor template={template} />
        </div>
      ) : null}
    </div>
  );
}