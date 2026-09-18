import { apiClient } from "./api-client";

export interface AvailableField {
  key: string;
  label: string;
  sample: string;
}

export interface TemplateField {
  key: string;
  label: string;
}

export interface TemplateSignatureArea {
  label: string;
}

export interface LeaveDocumentTemplate {
  title: string;
  header: string;
  intro: string;
  fields: TemplateField[];
  closing: string;
  signature_areas: TemplateSignatureArea[];
  footer: string;
  available_fields: AvailableField[];
  updated_at: string;
}

export interface LeaveDocumentTemplateInput {
  title?: string;
  header?: string;
  intro?: string;
  fields?: TemplateField[];
  closing?: string;
  signature_areas?: TemplateSignatureArea[];
  footer?: string;
}

export async function getLeaveDocumentTemplate(): Promise<LeaveDocumentTemplate> {
  return apiClient<LeaveDocumentTemplate>("/api/v1/leave-document-template/");
}