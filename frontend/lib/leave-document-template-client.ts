import type {
  LeaveDocumentTemplate,
  LeaveDocumentTemplateInput,
} from "./leave-document-template";
import { apiErrorMessage } from "./utils";

export async function updateLeaveDocumentTemplate(
  input: LeaveDocumentTemplateInput
): Promise<LeaveDocumentTemplate> {
  const response = await fetch("/api/hr/leave-document-template", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(apiErrorMessage(data));
  }
  return response.json();
}