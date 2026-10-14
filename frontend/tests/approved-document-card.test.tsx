import { act, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApprovedDocumentCard } from "@/components/documents/approved-document-card";
import {
  fetchApprovedDocument,
  fetchHRAapprovedDocument,
  type ApprovedLeaveDocument,
} from "@/lib/documents/approved";

vi.mock("@/lib/documents/approved", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/lib/documents/approved")>();
  return { ...actual, fetchApprovedDocument: vi.fn(), fetchHRAapprovedDocument: vi.fn() };
});

const mockedFetch = vi.mocked(fetchApprovedDocument);
const mockedFetchHR = vi.mocked(fetchHRAapprovedDocument);

beforeEach(() => {
  mockedFetch.mockReset();
  mockedFetchHR.mockReset();
});

function makeDocument(
  overrides: Partial<ApprovedLeaveDocument> = {}
): ApprovedLeaveDocument {
  return {
    id: "7",
    application: "app-1",
    status: "ready",
    available: true,
    file_name: "approved-leave.pdf",
    content_type: "application/pdf",
    file_size: 4096,
    approved_on: "2026-09-25T10:00:00Z",
    rendered_at: "2026-09-25T10:00:05Z",
    created_at: "2026-09-25T10:00:00Z",
    download_url: "https://signed/approved/app-1/approved-leave.pdf",
    ...overrides,
  };
}

describe("ApprovedDocumentCard", () => {
  it("links to the signed URL when the document is ready", async () => {
    mockedFetch.mockResolvedValue({ ok: true, data: makeDocument() });
    render(<ApprovedDocumentCard applicationId="app-1" />);

    const link = await screen.findByRole("link", { name: /open/i });
    expect(link).toHaveAttribute(
      "href",
      "https://signed/approved/app-1/approved-leave.pdf"
    );
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noreferrer");
    expect(screen.getByText("approved-leave.pdf")).toBeInTheDocument();
  });

  it("shows an inline status while the document is still being prepared", async () => {
    mockedFetch.mockResolvedValue({
      ok: true,
      data: makeDocument({ status: "pending", available: false, download_url: "" }),
    });
    render(<ApprovedDocumentCard applicationId="app-1" />);

    expect(await screen.findByText(/being prepared/i)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /open/i })).not.toBeInTheDocument();
  });

  it("polls while pending and reveals the link once the render finishes", async () => {
    vi.useFakeTimers();
    try {
      mockedFetch
        .mockResolvedValueOnce({
          ok: true,
          data: makeDocument({
            status: "pending",
            available: false,
            download_url: "",
          }),
        })
        .mockResolvedValueOnce({ ok: true, data: makeDocument() });
      render(<ApprovedDocumentCard applicationId="app-1" />);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });
      expect(screen.getByText(/being prepared/i)).toBeInTheDocument();

      await act(async () => {
        await vi.advanceTimersByTimeAsync(3000);
      });
      expect(screen.getByRole("link", { name: /open/i })).toBeInTheDocument();
      expect(mockedFetch).toHaveBeenCalledTimes(2);
    } finally {
      vi.useRealTimers();
    }
  });

  it("stops polling once the document reports ready", async () => {
    vi.useFakeTimers();
    try {
      mockedFetch
        .mockResolvedValueOnce({
          ok: true,
          data: makeDocument({
            status: "pending",
            available: false,
            download_url: "",
          }),
        })
        .mockResolvedValue({ ok: true, data: makeDocument() });
      render(<ApprovedDocumentCard applicationId="app-1" />);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(3000);
      });
      expect(mockedFetch).toHaveBeenCalledTimes(2);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(12000);
      });
      expect(mockedFetch).toHaveBeenCalledTimes(2);
    } finally {
      vi.useRealTimers();
    }
  });

  it("tells the reader to contact HR when generation failed", async () => {
    mockedFetch.mockResolvedValue({
      ok: true,
      data: makeDocument({ status: "failed", available: false, download_url: "" }),
    });
    render(<ApprovedDocumentCard applicationId="app-1" />);

    expect(await screen.findByText(/could not be generated/i)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /open/i })).not.toBeInTheDocument();
  });

  it("renders nothing when the caller may not read the document", async () => {
    mockedFetch.mockResolvedValue({ ok: false, kind: "not_found" });
    const { container } = render(
      <ApprovedDocumentCard applicationId="app-1" />
    );

    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });

  it("uses the HR route for the HR audience", async () => {
    mockedFetchHR.mockResolvedValue({ ok: true, data: makeDocument() });
    render(<ApprovedDocumentCard applicationId="app-1" audience="hr" />);

    await screen.findByRole("link", { name: /open/i });
    expect(mockedFetchHR).toHaveBeenCalledWith("app-1");
    expect(mockedFetch).not.toHaveBeenCalled();
  });

  it("never renders an Open link for a ready document with no URL", async () => {
    mockedFetch.mockResolvedValue({
      ok: true,
      data: makeDocument({ download_url: "" }),
    });
    render(<ApprovedDocumentCard applicationId="app-1" />);

    await screen.findByText("approved-leave.pdf");
    expect(screen.queryByRole("link", { name: /open/i })).not.toBeInTheDocument();
  });
});
