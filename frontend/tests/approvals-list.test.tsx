import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
      await screen.findByText("No applications are waiting for your decision.")
    ).toBeInTheDocument();
  });

  it("renders your decision columns on the decided tab", async () => {
    mockedFetchApprovals.mockResolvedValue({
      ok: true,
      data: makeListResponse(
        [makeListItem({ status: "approved", my_decision: { action: "approve", decided_at: "2026-09-23T08:00:00Z" } })],
        { tab: "decided" }
      ),
    });
    render(<ApprovalsList />);
    await screen.findAllByText("LV-2026-000123");

    fireEvent.click(screen.getByText("Decided by me"));
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
  });
});