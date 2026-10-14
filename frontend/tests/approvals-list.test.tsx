import { fireEvent, render, screen, waitFor } from "@testing-library/react";
<<<<<<< HEAD
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
=======
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ApprovalsList } from "@/components/approvals/approvals-list";
import { makeListResponse, makeListItem } from "@/lib/approvals/__fixtures__";
import { fetchApprovals } from "@/lib/approvals/service";

vi.mock("@/lib/approvals/service", () => ({
  fetchApprovals: vi.fn(),
}));

const mockedFetchApprovals = vi.mocked(fetchApprovals);

describe("ApprovalsList", () => {
  it("renders tabs, rows and links to the review page", async () => {
    mockedFetchApprovals.mockResolvedValue({
      ok: true,
      data: makeListResponse([makeListItem()]),
    });
    const { container } = render(<ApprovalsList />);

    expect(
      (await screen.findAllByText("LV-2026-000123")).length
    ).toBeGreaterThan(0);
    expect(screen.getAllByText("Chikondi Mbewe").length).toBeGreaterThan(0);
    expect(screen.getByText("Pending my decision")).toBeInTheDocument();
    expect(screen.getByText("Decided by me")).toBeInTheDocument();

    const link = container.querySelector(
      'a[href="/dashboard/approvals/app-1"]'
    );
    expect(link).not.toBeNull();
    expect(mockedFetchApprovals).toHaveBeenCalledWith("pending", "", 1);
  });

  it("never nests a <td> inside a link (hydration-safe tables)", async () => {
    mockedFetchApprovals.mockResolvedValue({
      ok: true,
      data: makeListResponse([makeListItem()]),
    });
    const { container } = render(<ApprovalsList />);

    await screen.findAllByText("LV-2026-000123");

    expect(container.querySelector("a td")).toBeNull();
    expect(container.querySelector("tr > a")).toBeNull();
  });

  it("shows the search query in the request (debounced)", async () => {
    mockedFetchApprovals.mockResolvedValue({
      ok: true,
      data: makeListResponse([makeListItem()]),
    });
    render(<ApprovalsList />);
    await screen.findAllByText("LV-2026-000123");

    fireEvent.change(screen.getByLabelText("Search approvals"), {
      target: { value: "Mbewe" },
    });

    await waitFor(() =>
      expect(mockedFetchApprovals).toHaveBeenLastCalledWith("pending", "Mbewe", 1)
    );
  });

  it("shows the empty state for the pending tab", async () => {
    mockedFetchApprovals.mockResolvedValue({ ok: true, data: makeListResponse([]) });
    render(<ApprovalsList />);
    expect(
      await screen.findByText("Nothing pending your review")
    ).toBeInTheDocument();
  });

  it("offers Clear filters on the search no-results empty state", async () => {
    mockedFetchApprovals.mockResolvedValue({ ok: true, data: makeListResponse([]) });
    const user = userEvent.setup();
    render(<ApprovalsList />);
    await screen.findByText("Nothing pending your review");

    await user.type(screen.getByLabelText("Search approvals"), "Mbewe");
    expect(await screen.findByText('No results for "Mbewe"')).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(screen.getByLabelText("Search approvals")).toHaveValue("");
    await waitFor(() =>
      expect(mockedFetchApprovals).toHaveBeenLastCalledWith("pending", "", 1)
    );
  });

  it("renders your decision columns on the decided tab", async () => {
    const user = userEvent.setup();
    mockedFetchApprovals.mockResolvedValue({
      ok: true,
      data: makeListResponse(
        [makeListItem({ status: "approved", my_decision: { action: "approve", decided_at: "2026-09-23T08:00:00Z" } })],
        { tab: "decided" }
      ),
    });
    render(<ApprovalsList />);
    await screen.findAllByText("LV-2026-000123");

    await user.click(screen.getByText("Decided by me"));
    expect(await screen.findByText("Your decision")).toBeInTheDocument();
    expect((await screen.findAllByText("Approved")).length).toBeGreaterThan(0);
  });

  it("shows an error with a retry button that reloads", async () => {
    mockedFetchApprovals.mockResolvedValueOnce({ ok: false, kind: "error", message: "Boom" });
    render(<ApprovalsList />);

    expect(await screen.findByText("Boom")).toBeInTheDocument();

    mockedFetchApprovals.mockResolvedValueOnce({
      ok: true,
      data: makeListResponse([makeListItem()]),
    });
    fireEvent.click(screen.getByText("Retry"));
    expect(
      (await screen.findAllByText("LV-2026-000123")).length
    ).toBeGreaterThan(0);
>>>>>>> feature/plans-teams
  });
});