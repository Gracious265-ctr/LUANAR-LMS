<<<<<<< HEAD
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
=======
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
>>>>>>> feature/plans-teams
        documents={[]}
        onDocumentsChange={vi.fn()}
      />
    );

<<<<<<< HEAD
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
=======
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
>>>>>>> feature/plans-teams
        onDocumentsChange={vi.fn()}
      />
    );

<<<<<<< HEAD
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
=======
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
>>>>>>> feature/plans-teams
        onDocumentsChange={onDocumentsChange}
      />
    );

<<<<<<< HEAD
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
=======
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

  it("warns that a correction document is archived rather than deleted", async () => {
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

  it("shows the replaces-hint and calls replaceDocument on a correction application", async () => {
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

    expect(screen.getByText(/returned for correction/i)).toBeInTheDocument();

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
>>>>>>> feature/plans-teams
        onDocumentsChange={vi.fn()}
      />
    );

<<<<<<< HEAD
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
=======
    expect(screen.queryByText(/drag & drop files/i)).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Remove document letter.pdf" })
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Replace" })).not.toBeInTheDocument();
>>>>>>> feature/plans-teams
  });
});