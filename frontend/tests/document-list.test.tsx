import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DocumentList } from "@/components/leave/document-list";
import type { SupportingDocument } from "@/lib/documents/types";

vi.mock("@/lib/documents/service", () => ({
  documentContentUrl: (appId: string, docId: string) =>
    `/api/leave/leave-applications/${appId}/documents/${docId}/content/`,
}));

const DOC: SupportingDocument = {
  id: "doc-1",
  file_path: "leave-documents/abc/doc-1/cert.pdf",
  file_url: "",
  file_name: "cert.pdf",
  file_size: 2048,
  content_type: "application/pdf",
  uploaded_at: "2026-09-20T09:00:00Z",
  status: "active",
  retired_at: null,
  retired_by: null,
  retire_reason: null,
  replaced_by: null,
  replaced_by_name: null,
};

describe("DocumentList", () => {
  it("renders each document with size and a content link", () => {
    render(<DocumentList applicationId="abc" documents={[DOC]} />);

    expect(screen.getByText("cert.pdf")).toBeInTheDocument();
    expect(screen.getByText(/2\.0 KB/)).toBeInTheDocument();
    expect(screen.getByLabelText("Open cert.pdf")).toHaveAttribute(
      "href",
      "/api/leave/leave-applications/abc/documents/doc-1/content/"
    );
  });

  it("renders an empty state", () => {
    render(<DocumentList applicationId="abc" documents={[]} />);

    expect(screen.getByText("No supporting documents.")).toBeInTheDocument();
  });
});