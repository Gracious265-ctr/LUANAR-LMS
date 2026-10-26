import { redirect } from "next/navigation";

import { LeaveDocumentTemplateEditor } from "@/components/hr/leave-document-template-editor";
import { getCurrentUser } from "@/lib/auth";
import { getLeaveDocumentTemplate } from "@/lib/leave-document-template";
import { Card } from "@/components/ui/card";
import { FadeIn } from "@/components/motion/FadeIn";

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
    <FadeIn>
      <div className="mx-auto max-w-3xl space-y-6">
        <div>
          <h2 className="text-xl font-semibold tracking-tight text-text-primary">
            Approved Leave Document Template
          </h2>
          <p className="text-text-secondary">Configure the approved leave document template.</p>
        </div>

        {templateError ? (
          <div className="rounded-lg bg-status-rejected-subtle py-12 text-center text-sm text-status-rejected">
            {templateError}
          </div>
        ) : template ? (
          <Card>
            <LeaveDocumentTemplateEditor template={template} />
          </Card>
        ) : null}
      </div>
    </FadeIn>
  );
}