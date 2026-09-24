import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CancellationRequestsTable } from "@/components/cancellations/cancellation-requests-table";
import { makeListResponse, makeRow } from "@/lib/cancellations/__fixtures__";
import { fetchCancellations } from "@/lib/cancellations/service";

vi.mock("@/lib/cancellations/service", () => ({
  fetchCancellations: vi.fn(),
}));

const mockedFetchCancellations = vi.mocked(fetchCancellations);

describe("CancellationRequestsTable", () => {
  it("renders rows and links to the cancellation review entry", async () => {
    mockedFetchCancellations.mockResolvedValue({
      ok: true,
      data: makeListResponse([makeRow()]),
    });
    const { container } = render(<CancellationRequestsTable />);

    expect((await screen.findAllByText("LV-2026-27-800123")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Chikondi Mbewe").length).toBeGreaterThan(0);
    expect(screen.getByText("Decided by me")).toBeInTheDocument();

    const link = container.querySelector(
      'a[href="/dashboard/approvals/app-1?cancellation=canc-1"]'
    );
    expect(link).not.toBeNull();
    expect(mockedFetchCancellations).toHaveBeenCalledWith("pending", 1);
  });

  it("switches tabs and resets the page", async () => {
    mockedFetchCancellations
      .mockResolvedValueOnce({ ok: true, data: makeListResponse([makeRow()]) })
      .mockResolvedValueOnce({
        ok: true,
        data: makeListResponse([], { tab: "decided" }),
      });
    render(<CancellationRequestsTable />);
    await screen.findAllByText("LV-2026-27-800123");

    fireEvent.click(screen.getByText("Decided by me"));
    await waitFor(() =>
      expect(mockedFetchCancellations).toHaveBeenLastCalledWith("decided", 1)
    );
    expect(
      await screen.findByText("You haven't decided any cancellation requests yet.")
    ).toBeInTheDocument();
  });

  it("labels how soon leave starts", async () => {
    mockedFetchCancellations.mockResolvedValue({
      ok: true,
      data: makeListResponse([
        makeRow({ starts_in_days: 2 }),
        makeRow({ starts_in_days: 20, request_id: "canc-2" }),
        makeRow({ leave_started: true, starts_in_days: null, request_id: "canc-3" }),
        makeRow({ starts_in_days: null, request_id: "canc-4" }),
      ]),
    });
    render(<CancellationRequestsTable />);
    await screen.findAllByText("LV-2026-27-800123");

    expect(screen.getAllByText("Starts in 2 days").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Starts in 20 days").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Started").length).toBeGreaterThan(0);
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("shows the empty state and the error retry", async () => {
    mockedFetchCancellations.mockResolvedValueOnce({
      ok: false,
      kind: "error",
      message: "Boom",
    });
    render(<CancellationRequestsTable />);
    expect(await screen.findByText("Boom")).toBeInTheDocument();

    mockedFetchCancellations.mockResolvedValueOnce({
      ok: true,
      data: makeListResponse([makeRow()]),
    });
    fireEvent.click(screen.getByText("Retry"));
    expect((await screen.findAllByText("LV-2026-27-800123")).length).toBeGreaterThan(0);
  });

  it("navigates pages", async () => {
    mockedFetchCancellations.mockResolvedValue({
      ok: true,
      data: makeListResponse([makeRow()], {
        next: "http://sandbox.local/api/v1/approvals/cancellations/?tab=pending&page=2",
        previous: null,
      }),
    });
    render(<CancellationRequestsTable />);
    await screen.findAllByText("LV-2026-27-800123");

    expect(screen.getByText("Previous")).toBeDisabled();
    fireEvent.click(screen.getByText("Next"));
    await waitFor(() =>
      expect(mockedFetchCancellations).toHaveBeenLastCalledWith("pending", 2)
    );
    expect(screen.getByText("Page 2")).toBeInTheDocument();
  });
});