import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SupportingDocumentsUploader } from "@/components/leave/SupportingDocumentsUploader";
import type { SupportingDocument } from "@/lib/leave-api";

vi.mock("@/lib/leave-api", () => ({
  uploadDocument: vi.fn(),
  deleteDocument: vi.fn(),
}));

vi.mock("react-dropzone", () => {
  let capturedOnDrop: ((files: File[]) => void) | null = null;
  return {
    useDropzone: vi.fn(({ onDrop }: { onDrop: (files: File[]) => void }) => {
      capturedOnDrop = onDrop;
      return {
        getRootProps: () => ({}),
        getInputProps: () => ({}),
        isDragActive: false,
      };
    }),
    __getOnDrop: () => capturedOnDrop,
  };
});

import { uploadDocument, deleteDocument } from "@/lib/leave-api";
import { __getOnDrop } from "react-dropzone";

const doc: SupportingDocument = {
  id: "doc-1",
  file_path: "/uploads/doc-1.pdf",
  file_url: "/uploads/doc-1.pdf",
  file_name: "letter.pdf",
  file_size: 2048,
  content_type: "application/pdf",
  uploaded_at: "2026-09-20T10:00:00Z",
};

function dropFiles() {
  const onDrop = __getOnDrop();
  if (!onDrop) throw new Error("dropzone onDrop not captured");
  onDrop([new File(["data"], "letter.pdf", { type: "application/pdf" })]);
}

describe("SupportingDocumentsUploader", () => {
  beforeEach(() => {
    vi.mocked(uploadDocument).mockReset();
    vi.mocked(deleteDocument).mockReset();
  });

  it("surfaces an error when an upload fails", async () => {
    vi.mocked(uploadDocument).mockRejectedValueOnce(
      new Error("Storage not configured")
    );

    render(
      <SupportingDocumentsUploader
        applicationId="draft-1"
        documents={[]}
        onDocumentsChange={vi.fn()}
      />
    );

    dropFiles();

    expect(
      await screen.findByText(/storage not configured/i)
    ).toBeInTheDocument();
  });

  it("surfaces an error when document removal fails", async () => {
    vi.mocked(deleteDocument).mockRejectedValueOnce(new Error("boom"));

    render(
      <SupportingDocumentsUploader
        applicationId="draft-1"
        documents={[doc]}
        onDocumentsChange={vi.fn()}
      />
    );

    fireEvent.click(screen.getByRole("button"));

    expect(
      await screen.findByText(/could not remove this document/i)
    ).toBeInTheDocument();
  });
});