import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApprovalsList } from "@/components/approvals/approvals-list";
import { fetchApprovalsList } from "@/lib/approvals/service";
import type { ApprovalListResponse } from "@/lib/approvals/types";

vi.mock("@/lib/approvals/service", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/lib/approvals/service")>();
  return {
    ...actual,
    fetchApprovalsList: vi.fn(),
    fetchCapabilities: vi.fn(),
    fetchApprovalDetail: vi.fn(),
    submitDecision: vi.fn(),
    fetchDocumentDownload: vi.fn(),
  };
});

import listDecided from "@/lib/approvals/__fixtures__/list-decided.json";
import listPending from "@/lib/approvals/__fixtures__/list-pending.json";

const pendingFixture = listPending as unknown as ApprovalListResponse;
const decidedFixture = listDecided as unknown as ApprovalListResponse;

function mockList(data: ApprovalListResponse) {
  vi.mocked(fetchApprovalsList).mockResolvedValue(data);
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ApprovalsList", () => {
  it("renders the header, tabs and pending rows", async () => {
    mockList(pendingFixture);
    render(<ApprovalsList />);

    expect(screen.getByRole("tab", { name: "Pending" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Decided" })).toBeInTheDocument();
    expect(screen.getByLabelText("Search approvals")).toBeInTheDocument();

    expect(await screen.findByRole("link", { name: "LEA-2026-0041" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "LEA-2026-0042" })).toBeInTheDocument();
    expect(screen.getAllByText("Miriam Banda").length).toBeGreaterThan(0);
    expect(screen.getAllByText("John Mumba").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Computer Science").length).toBeGreaterThan(0);
  });

  it("shows status badges for pending items", async () => {
    mockList(pendingFixture);
    render(<ApprovalsList />);

    expect((await screen.findAllByText("Pending Approval")).length).toBeGreaterThan(0);
  });

  it("shows your decision on the decided tab", async () => {
    mockList(decidedFixture);
    render(<ApprovalsList />);

    fireEvent.click(screen.getByRole("tab", { name: "Decided" }));

    expect((await screen.findAllByText("Approved")).length).toBeGreaterThan(0);
    await waitFor(() => {
      expect(fetchApprovalsList).toHaveBeenLastCalledWith(
        expect.objectContaining({ tab: "decided" })
      );
    });
  });

  it("filters by the debounced search query", async () => {
    mockList(pendingFixture);
    render(<ApprovalsList />);

    const input = screen.getByLabelText("Search approvals");
    fireEvent.change(input, { target: { value: "miriam" } });

    await waitFor(
      () => {
        expect(fetchApprovalsList).toHaveBeenLastCalledWith(
          expect.objectContaining({ q: "miriam", page: 1 })
        );
      },
      { timeout: 1500 }
    );
  });

  it("shows an empty state when there are no pending items", async () => {
    mockList({ count: 0, next: null, previous: null, results: [] });
    render(<ApprovalsList />);

    expect(
      await screen.findByText("Nothing waiting for you right now")
    ).toBeInTheDocument();
  });

  it("shows a dedicated empty state when search matches nothing", async () => {
    mockList({ count: 0, next: null, previous: null, results: [] });
    render(<ApprovalsList />);

    fireEvent.change(screen.getByLabelText("Search approvals"), {
      target: { value: "zzzz" },
    });

    expect(await screen.findByText("No results found")).toBeInTheDocument();
    expect(screen.getByText("Try adjusting your search or switching tabs.")).toBeInTheDocument();
  });

  it("shows an error state and retries", async () => {
    vi.mocked(fetchApprovalsList).mockRejectedValue(
      new Error("boom")
    );
    render(<ApprovalsList />);

    expect(await screen.findByText("Could not load approvals")).toBeInTheDocument();

    vi.mocked(fetchApprovalsList).mockResolvedValue(pendingFixture);
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    await screen.findByRole("link", { name: "LEA-2026-0041" });
    expect(fetchApprovalsList).toHaveBeenCalled();
  });

  it("paginates with previous/next controls", async () => {
    mockList(pendingFixture);
    render(<ApprovalsList />);

    const previous = await screen.findByRole("button", { name: "Previous" });
    const next = screen.getByRole("button", { name: "Next" });

    expect(previous).toBeDisabled();
    expect(next).not.toBeDisabled();
    expect(screen.getByText(/Showing 1–2 of 2/)).toBeInTheDocument();

    fireEvent.click(next);
    await waitFor(() => {
      expect(fetchApprovalsList).toHaveBeenLastCalledWith(
        expect.objectContaining({ page: 2 })
      );
    });
  });
});