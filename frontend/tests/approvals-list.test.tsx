import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ApprovalsList } from "@/components/approvals/approvals-list";
import { makeListResponse, makeListItem } from "@/lib/approvals/__fixtures__";
import { fetchApprovals, approveApprovals } from "@/lib/approvals/service";

vi.mock("@/lib/approvals/service", () => ({
  fetchApprovals: vi.fn(),
  approveApprovals: vi.fn(),
}));

const mockedFetchApprovals = vi.mocked(fetchApprovals);
const mockedApproveApprovals = vi.mocked(approveApprovals);

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

  it("shows selection tools only on the pending tab", async () => {
    mockedFetchApprovals.mockResolvedValue({
      ok: true,
      data: makeListResponse([makeListItem()]),
    });
    const user = userEvent.setup();
    render(<ApprovalsList />);
    await screen.findAllByText("LV-2026-000123");

    expect(screen.getByText("0 of 25 selected")).toBeInTheDocument();
    expect(
      screen.getAllByRole("checkbox", { name: "Select LV-2026-000123" }).length
    ).toBeGreaterThan(0);

    await user.click(
      screen.getAllByRole("checkbox", { name: "Select LV-2026-000123" })[0]
    );
    expect(screen.getByText("1 of 25 selected")).toBeInTheDocument();

    await user.click(screen.getByText("Decided by me"));
    await waitFor(() => expect(screen.queryByText("0 of 25 selected")).toBeNull());
    expect(screen.queryByRole("checkbox")).toBeNull();
  });

  it("selects every row on the page from the toolbar", async () => {
    mockedFetchApprovals.mockResolvedValue({
      ok: true,
      data: makeListResponse([
        makeListItem(),
        makeListItem({ id: "app-2", reference: "LV-2026-000200" }),
      ]),
    });
    const user = userEvent.setup();
    render(<ApprovalsList />);
    await screen.findAllByText("LV-2026-000123");

    await user.click(screen.getByRole("button", { name: "Select all on this page" }));
    expect(screen.getByText("2 of 25 selected")).toBeInTheDocument();
  });

  it("caps a select-all at the batch limit", async () => {
    const rows = Array.from({ length: 30 }, (_, index) =>
      makeListItem({ id: `app-${index}`, reference: `LV-2026-${index}` })
    );
    mockedFetchApprovals.mockResolvedValue({ ok: true, data: makeListResponse(rows) });
    const user = userEvent.setup();
    render(<ApprovalsList />);
    await screen.findAllByText("LV-2026-0");

    await user.click(screen.getByRole("button", { name: "Select all on this page" }));
    expect(screen.getByText("25 of 25 selected")).toBeInTheDocument();
  });

  it("approves the selected applications through the confirmation gate", async () => {
    mockedFetchApprovals.mockResolvedValue({
      ok: true,
      data: makeListResponse([makeListItem()]),
    });
    mockedApproveApprovals.mockResolvedValue({
      ok: true,
      data: {
        results: [{ id: "app-1", status: "approved" }],
        approved: 1,
        failed: 0,
        limit: 25,
      },
    });
    const user = userEvent.setup();
    render(<ApprovalsList />);
    await screen.findAllByText("LV-2026-000123");

    await user.click(
      screen.getAllByRole("checkbox", { name: "Select LV-2026-000123" })[0]
    );
    await user.click(screen.getByRole("button", { name: "Approve selected" }));

    await user.type(await screen.findByLabelText("Type to confirm"), "APPROVE");
    await user.click(screen.getByRole("button", { name: "Approve 1" }));

    await waitFor(() =>
      expect(mockedApproveApprovals).toHaveBeenCalledWith([
        { id: "app-1", stage_version: 1 },
      ])
    );
  });

  it("surfaces batch failures separately from successes", async () => {
    mockedFetchApprovals.mockResolvedValue({
      ok: true,
      data: makeListResponse([
        makeListItem(),
        makeListItem({ id: "app-2", reference: "LV-2026-000200" }),
      ]),
    });
    mockedApproveApprovals.mockResolvedValue({
      ok: true,
      data: {
        results: [
          { id: "app-1", status: "approved" },
          { id: "app-2", status: "failed", reason: "stage_changed" },
        ],
        approved: 1,
        failed: 1,
        limit: 25,
      },
    });
    const user = userEvent.setup();
    render(<ApprovalsList />);
    await screen.findAllByText("LV-2026-000123");

    await user.click(screen.getByRole("button", { name: "Select all on this page" }));
    await user.click(screen.getByRole("button", { name: "Approve selected" }));
    await user.type(await screen.findByLabelText("Type to confirm"), "APPROVE");
    await user.click(screen.getByRole("button", { name: "Approve 2" }));

    expect(
      await screen.findByText("1 could not be approved.")
    ).toBeInTheDocument();
    expect(screen.getAllByText(/LV-2026-000200/).length).toBeGreaterThan(0);
    expect(screen.getByText(/already decided/)).toBeInTheDocument();
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