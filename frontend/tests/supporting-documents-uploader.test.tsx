import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SupportingDocumentsUploader } from "@/components/leave/SupportingDocumentsUploader";
import type { SupportingDocument } from "@/lib/leave-api";

const dropzoneMock = vi.hoisted(() => ({
  onDrop: null as ((files: File[]) => void) | null,
}));

vi.mock("@/lib/leave-api", () => ({
  uploadDocument: vi.fn(),
  deleteDocument: vi.fn(),
  replaceDocument: vi.fn(),
  listDocuments: vi.fn(),
}));

vi.mock("react-dropzone", () => ({
  useDropzone: vi.fn(({ onDrop }: { onDrop: (files: File[]) => void }) => {
    dropzoneMock.onDrop = onDrop;
    return {
      getRootProps: () => ({}),
      getInputProps: () => ({}),
      isDragActive: false,
    };
  }),
}));

import { deleteDocument, listDocuments, replaceDocument, uploadDocument } from "@/lib/leave-api";

const doc: SupportingDocument = {
  id: "doc-1",
  file_url: "https://signed/doc-1.pdf",
  file_name: "letter.pdf",
  file_size: 2048,
  content_type: "application/pdf",
  uploaded_at: "2026-09-20T10:00:00Z",
  status: "active",
  retired_at: null,
  retire_reason: null,
  retired_by: null,
  replaced_by: null,
};

function dropFiles() {
  if (!dropzoneMock.onDrop) throw new Error("dropzone onDrop not captured");
  dropzoneMock.onDrop([new File(["data"], "letter.pdf", { type: "application/pdf" })]);
}

beforeEach(() => {
  vi.mocked(uploadDocument).mockReset();
  vi.mocked(deleteDocument).mockReset();
  vi.mocked(replaceDocument).mockReset();
  vi.mocked(listDocuments).mockReset();
  vi.mocked(listDocuments).mockResolvedValue([doc]);
});

describe("SupportingDocumentsUploader", () => {
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

  it("maps a file-too-large detail message inline", async () => {
    vi.mocked(uploadDocument).mockRejectedValueOnce(
      new Error("Files may not exceed 10 MB.")
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
      await screen.findByText("Files may not exceed 10 MB.")
    ).toBeInTheDocument();
  });

  it("refetches the server-side document list after a successful upload", async () => {
    vi.mocked(uploadDocument).mockResolvedValue(doc);
    const onDocumentsChange = vi.fn();

    render(
      <SupportingDocumentsUploader
        applicationId="draft-1"
        documents={[]}
        onDocumentsChange={onDocumentsChange}
      />
    );

    dropFiles();

    await vi.waitFor(() => expect(listDocuments).toHaveBeenCalledWith("draft-1"));
    await vi.waitFor(() => expect(onDocumentsChange).toHaveBeenCalledWith([doc]));
  });

  it("asks for confirmation in an in-app dialog before removing a document", async () => {
    vi.mocked(deleteDocument).mockResolvedValue(undefined);
    vi.mocked(listDocuments).mockResolvedValue([]);
    const onDocumentsChange = vi.fn();

    render(
      <SupportingDocumentsUploader
        applicationId="draft-1"
        documents={[doc]}
        onDocumentsChange={onDocumentsChange}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Remove document letter.pdf" }));

    const dialog = await screen.findByRole("alertdialog");
    expect(dialog).toHaveTextContent("Remove letter.pdf?");
    expect(deleteDocument).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Remove" }));

    await vi.waitFor(() => expect(deleteDocument).toHaveBeenCalledWith("draft-1", "doc-1"));
    await vi.waitFor(() => expect(onDocumentsChange).toHaveBeenCalledWith([]));
  });

  it("does not delete when the confirmation is cancelled", async () => {
    render(
      <SupportingDocumentsUploader
        applicationId="draft-1"
        documents={[doc]}
        onDocumentsChange={vi.fn()}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Remove document letter.pdf" }));

    fireEvent.click(await screen.findByRole("button", { name: "Cancel" }));

    await vi.waitFor(() =>
      expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument()
    );
    expect(deleteDocument).not.toHaveBeenCalled();
  });

  it("warns that a replaced document is archived rather than deleted", async () => {
    render(
      <SupportingDocumentsUploader
        applicationId="draft-1"
        documents={[doc]}
        canReplace
        onDocumentsChange={vi.fn()}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Remove document letter.pdf" }));

    expect(await screen.findByRole("alertdialog")).toHaveTextContent(
      /stays archived under the previous submission/i
    );
  });

  it("surfaces an error when document removal fails", async () => {
    vi.mocked(deleteDocument).mockRejectedValueOnce(
      new Error("Could not remove this document. Please try again.")
    );

    render(
      <SupportingDocumentsUploader
        applicationId="draft-1"
        documents={[doc]}
        onDocumentsChange={vi.fn()}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Remove document letter.pdf" }));
    fireEvent.click(await screen.findByRole("button", { name: "Remove" }));

    expect(
      await screen.findByText(/could not remove this document/i)
    ).toBeInTheDocument();
  });

  it("shows the replaces-hint and calls replaceDocument on a rejected application", async () => {
    vi.mocked(replaceDocument).mockResolvedValue(doc);
    const replacement = { ...doc, id: "doc-2", file_name: "letter-v2.pdf" };
    vi.mocked(listDocuments).mockResolvedValue([replacement]);
    const onDocumentsChange = vi.fn();

    render(
      <SupportingDocumentsUploader
        applicationId="draft-1"
        documents={[doc]}
        canReplace
        onDocumentsChange={onDocumentsChange}
      />
    );

    expect(screen.getByText(/rejected/i)).toBeInTheDocument();

    const picker = screen.getByLabelText("Replace document letter.pdf");
    fireEvent.change(picker, {
      target: {
        files: [new File(["new"], "letter-v2.pdf", { type: "application/pdf" })],
      },
    });

    await vi.waitFor(() =>
      expect(replaceDocument).toHaveBeenCalledWith("draft-1", "doc-1", expect.any(File))
    );
    await vi.waitFor(() => expect(listDocuments).toHaveBeenCalledWith("draft-1"));
    await vi.waitFor(() => expect(onDocumentsChange).toHaveBeenCalledWith([replacement]));
  });

  it("renders no controls when editable is false", () => {
    render(
      <SupportingDocumentsUploader
        applicationId="draft-1"
        documents={[doc]}
        editable={false}
        onDocumentsChange={vi.fn()}
      />
    );

    expect(screen.queryByText(/drag & drop files/i)).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Remove document letter.pdf" })
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Replace" })).not.toBeInTheDocument();
  });
});