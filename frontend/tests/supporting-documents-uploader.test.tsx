import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SupportingDocumentsUploader } from "@/components/leave/SupportingDocumentsUploader";
import { DEFAULT_UPLOAD_CONFIG } from "@/lib/documents/config";
import type { SupportingDocument } from "@/lib/documents/types";

const service = vi.hoisted(() => {
  class DocumentRequestError extends Error {
    readonly status: number;
    readonly code?: string;
    readonly field?: string;
    constructor(status: number, message: string, code?: string, field?: string) {
      super(message);
      this.name = "DocumentRequestError";
      this.status = status;
      this.code = code;
      this.field = field;
    }
  }
  return {
    DocumentRequestError,
    getDocumentConfig: vi.fn(),
    uploadDocument: vi.fn(),
    removeDocument: vi.fn(),
    replaceDocument: vi.fn(),
    documentContentUrl: vi.fn(),
  };
});

vi.mock("@/lib/documents/service", () => service);

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

beforeEach(() => {
  vi.clearAllMocks();
  service.getDocumentConfig.mockResolvedValue(DEFAULT_UPLOAD_CONFIG);
});

describe("SupportingDocumentsUploader", () => {
  it("renders editable mode with a dropzone and config size hint", async () => {
    render(
      <SupportingDocumentsUploader
        applicationId="abc"
        documents={[]}
        onDocumentsChange={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/Max file size: 10.0 MB/)).toBeInTheDocument();
    });
    expect(screen.getByText(/Drag & drop files here/)).toBeInTheDocument();
    expect(screen.getByText(/No supporting documents yet/)).toBeInTheDocument();
  });

  it("renders documents with open link and action buttons", async () => {
    service.documentContentUrl.mockReturnValue("/api/leave/.../content/");
    render(
      <SupportingDocumentsUploader
        applicationId="abc"
        documents={[DOC]}
        onDocumentsChange={vi.fn()}
      />
    );

    expect(screen.getByText("cert.pdf")).toBeInTheDocument();
    expect(screen.getByLabelText("Open cert.pdf")).toHaveAttribute(
      "href",
      "/api/leave/.../content/"
    );
    expect(
      screen.getByRole("button", { name: "Replace cert.pdf" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Remove cert.pdf" })
    ).toBeInTheDocument();
  });

  it("removes a document and reports the new list upward", async () => {
    service.removeDocument.mockResolvedValue(undefined);
    const onDocumentsChange = vi.fn();
    render(
      <SupportingDocumentsUploader
        applicationId="abc"
        documents={[DOC]}
        onDocumentsChange={onDocumentsChange}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Remove cert.pdf" }));

    await waitFor(() => {
      expect(service.removeDocument).toHaveBeenCalledWith("abc", "doc-1");
      expect(onDocumentsChange).toHaveBeenCalledWith([]);
    });
  });

  it("shows a read-only banner when the backend rejects with 409", async () => {
    service.removeDocument.mockRejectedValue(
      new service.DocumentRequestError(409, "Locked.", "document_read_only")
    );
    render(
      <SupportingDocumentsUploader
        applicationId="abc"
        documents={[DOC]}
        onDocumentsChange={vi.fn()}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Remove cert.pdf" }));

    await screen.findByText("Locked.");
  });

  it("does not render actions in readonly mode", async () => {
    render(
      <SupportingDocumentsUploader
        applicationId="abc"
        documents={[DOC]}
        mode="readonly"
        onDocumentsChange={vi.fn()}
      />
    );

    expect(screen.getByText("cert.pdf")).toBeInTheDocument();
    expect(screen.getByLabelText("Open cert.pdf")).toBeInTheDocument();
    expect(screen.queryByLabelText("Remove cert.pdf")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Replace cert.pdf")).not.toBeInTheDocument();
    expect(screen.queryByText(/Drag & drop files here/)).not.toBeInTheDocument();
  });
});