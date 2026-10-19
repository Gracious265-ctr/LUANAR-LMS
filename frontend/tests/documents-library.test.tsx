import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/documents/library", () => ({
  listMySupportingDocuments: vi.fn(),
  listMyApprovedDocuments: vi.fn(),
  fetchSupportingDocumentUrl: vi.fn(),
  fetchApprovedDocumentUrl: vi.fn(),
}));

import { DocumentsLibrary } from "@/components/documents/documents-library";
import {
  fetchApprovedDocumentUrl,
  fetchSupportingDocumentUrl,
  listMyApprovedDocuments,
  listMySupportingDocuments,
  type ApprovedDocumentFeedRow,
  type SupportingDocumentFeedRow,
} from "@/lib/documents/library";

const supporting: SupportingDocumentFeedRow = {
  id: "support-1",
  file_url: "",
  file_name: "letter.pdf",
  file_size: 2048,
  content_type: "application/pdf",
  uploaded_at: "2026-09-20T10:00:00Z",
  status: "active",
  retired_at: null,
  retire_reason: null,
  retired_by: null,
  replaced_by: null,
  application: {
    id: "app-1",
    reference_number: "LV-2026-000111",
    status: "draft",
  },
};

const archived: SupportingDocumentFeedRow = {
  ...supporting,
  id: "support-2",
  file_name: "old-letter.pdf",
  status: "retired",
  retire_reason: "replaced",
  retired_at: "2026-09-21T10:00:00Z",
};

const approved: ApprovedDocumentFeedRow = {
  id: "approved-1",
  application: "app-2",
  reference_number: "LV-2026-000222",
  status: "ready",
  available: true,
  file_name: "approved-leave.pdf",
  content_type: "application/pdf",
  file_size: 4096,
  approved_on: "2026-09-25T08:00:00Z",
  rendered_at: "2026-09-25T08:01:00Z",
  created_at: "2026-09-25T08:00:30Z",
  download_url: "",
};

const pendingApproved: ApprovedDocumentFeedRow = {
  ...approved,
  id: "approved-2",
  application: "app-3",
  reference_number: "LV-2026-000333",
  status: "pending",
  available: false,
  download_url: "",
};

function mockFeeds(
  supportingRows: SupportingDocumentFeedRow[],
  approvedRows: ApprovedDocumentFeedRow[]
) {
  vi.mocked(listMySupportingDocuments).mockResolvedValue({
    count: supportingRows.length,
    results: supportingRows,
  });
  vi.mocked(listMyApprovedDocuments).mockResolvedValue({
    count: approvedRows.length,
    results: approvedRows,
  });
}

describe("DocumentsLibrary", () => {
  beforeEach(() => {
    vi.mocked(listMySupportingDocuments).mockReset();
    vi.mocked(listMyApprovedDocuments).mockReset();
    vi.mocked(fetchSupportingDocumentUrl).mockReset();
    vi.mocked(fetchApprovedDocumentUrl).mockReset();
    window.open = vi.fn();
  });

  it("lists supporting and approved documents with their application links", async () => {
    mockFeeds([supporting], [approved]);

    render(<DocumentsLibrary />);

    expect(await screen.findByText("letter.pdf")).toBeInTheDocument();
    expect(screen.getByText("approved-leave.pdf")).toBeInTheDocument();

    expect(
      screen.getByRole("link", { name: "LV-2026-000111" })
    ).toHaveAttribute("href", "/leave/applications/app-1");
    expect(
      screen.getByRole("link", { name: "LV-2026-000222" })
    ).toHaveAttribute("href", "/leave/applications/app-2");
  });

  it("mints the file URL on demand when a row is opened", async () => {
    mockFeeds([supporting], [approved]);
    vi.mocked(fetchSupportingDocumentUrl).mockResolvedValue(
      "https://signed/letter.pdf"
    );
    vi.mocked(fetchApprovedDocumentUrl).mockResolvedValue(
      "https://signed/approved-leave.pdf"
    );

    render(<DocumentsLibrary />);

    await userEvent.click(await screen.findByRole("button", { name: "Open" }));
    expect(fetchSupportingDocumentUrl).toHaveBeenCalledWith("app-1", "support-1");
    expect(window.open).toHaveBeenCalledWith(
      "https://signed/letter.pdf",
      "_blank",
      "noopener,noreferrer"
    );

    await userEvent.click(screen.getByRole("button", { name: "Download" }));
    expect(fetchApprovedDocumentUrl).toHaveBeenCalledWith("app-2");
    expect(window.open).toHaveBeenCalledWith(
      "https://signed/approved-leave.pdf",
      "_blank",
      "noopener,noreferrer"
    );
  });

  it("reports a failure to prepare a document without disturbing the list", async () => {
    mockFeeds([supporting], []);
    vi.mocked(fetchSupportingDocumentUrl).mockRejectedValue(
      new Error("Could not prepare the document. Please try again.")
    );

    render(<DocumentsLibrary />);
    await screen.findByText("letter.pdf");

    await userEvent.click(screen.getByRole("button", { name: /Open/ }));

    expect(
      await screen.findByText("Could not prepare the document. Please try again.")
    ).toBeInTheDocument();
    expect(screen.getByText("letter.pdf")).toBeInTheDocument();
  });

  it("marks retired documents as archived", async () => {
    mockFeeds([supporting, archived], []);

    render(<DocumentsLibrary />);

    expect(await screen.findByText("old-letter.pdf")).toBeInTheDocument();
    expect(screen.getByText("Archived")).toBeInTheDocument();
    expect(screen.getByText(/Replaced/)).toBeInTheDocument();
  });

  it("shows a pending approved document without a download link", async () => {
    mockFeeds([], [pendingApproved]);

    render(<DocumentsLibrary />);

    expect(await screen.findByText("approved-leave.pdf")).toBeInTheDocument();
    expect(screen.getByText("Preparing")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Download/ })).toBeNull();
  });

  it("shows the empty state for each section when there is nothing", async () => {
    mockFeeds([], []);

    render(<DocumentsLibrary />);

    expect(
      await screen.findByText("No supporting documents yet")
    ).toBeInTheDocument();
    expect(screen.getByText("No approved documents yet")).toBeInTheDocument();
  });

  it("shows an error state and refetches on retry", async () => {
    vi.mocked(listMySupportingDocuments)
      .mockRejectedValueOnce(new Error("Network is down"))
      .mockResolvedValue({ count: 0, results: [] });
    vi.mocked(listMyApprovedDocuments).mockResolvedValue({
      count: 0,
      results: [],
    });

    render(<DocumentsLibrary />);

    expect(
      await screen.findByText("Could not load these documents")
    ).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(
      await screen.findByText("No supporting documents yet")
    ).toBeInTheDocument();
    expect(listMySupportingDocuments).toHaveBeenCalledTimes(2);
  });
});
