import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApprovalsHub } from "@/components/approvals/approvals-hub";
import { fetchApprovalsList } from "@/lib/approvals/service";
import { fetchCancellationApprovalsList } from "@/lib/cancellation/service";
import type { CancellationApprovalListResponse } from "@/lib/cancellation/types";

vi.mock("@/lib/approvals/service", async (importOriginal) => {
  const mod = await importOriginal<typeof import("@/lib/approvals/service")>();
  return { ...mod, fetchApprovalsList: vi.fn() };
});

vi.mock("@/lib/cancellation/service", async (importOriginal) => {
  const mod = await importOriginal<typeof import("@/lib/cancellation/service")>();
  return { ...mod, fetchCancellationApprovalsList: vi.fn() };
});

const listFixture: CancellationApprovalListResponse = {
  count: 2,
  next: null,
  previous: null,
  results: [
    {
      id: "canc-1",
      kind: "approved_leave",
      status: "pending",
      reason: "Family emergency.",
      requested_at: "2026-10-20T08:00:00Z",
      decided_at: null,
      application_id: "app-9",
      application_reference: "LV-2026-27-900009",
      employee_name: "Thoko Mbewe",
      leave_type: "Annual Leave",
      start_date: "2040-01-15",
      end_date: "2040-01-25",
      working_days: 8,
      leave_started: false,
      current_stage_role: "Supervisor",
      stage_version: 1,
      my_decision: null,
    },
    {
      id: "canc-2",
      kind: "approved_leave",
      status: "pending",
      reason: "Coverage already exists.",
      requested_at: "2026-10-21T09:00:00Z",
      decided_at: null,
      application_id: "app-10",
      application_reference: "LV-2026-27-900010",
      employee_name: "Limbani Phiri",
      leave_type: "Annual Leave",
      start_date: null,
      end_date: null,
      working_days: 5,
      leave_started: true,
      current_stage_role: "HOD",
      stage_version: 1,
      my_decision: null,
    },
  ],
};

function mockQueuesEmpty() {
  vi.mocked(fetchApprovalsList).mockResolvedValue({
    count: 0,
    next: null,
    previous: null,
    results: [],
  });
  vi.mocked(fetchCancellationApprovalsList).mockResolvedValue({
    count: 0,
    next: null,
    previous: null,
    results: [],
  });
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ApprovalsHub", () => {
  it("opens on the Applications section with the Unit 16 queue", async () => {
    mockQueuesEmpty();
    render(<ApprovalsHub />);

    expect(
      screen.getAllByRole("heading", { name: "Approvals" }).length
    ).toBeGreaterThan(0);
    expect(
      screen.getAllByText("Applications waiting for your decision.").length
    ).toBeGreaterThan(0);
    expect(
      await screen.findByText("Nothing waiting for you right now")
    ).toBeInTheDocument();

    expect(fetchApprovalsList).toHaveBeenCalledTimes(1);
    expect(fetchCancellationApprovalsList).not.toHaveBeenCalled();
  });

  it("switches to the cancellation requests section", async () => {
    mockQueuesEmpty();
    render(<ApprovalsHub />);
    await screen.findByText("Nothing waiting for you right now");

    fireEvent.click(
      screen.getByRole("tab", { name: "Cancellation requests" })
    );

    expect(
      await screen.findByText(
        "No cancellation requests are waiting for you"
      )
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Leave cancellation requests waiting for your decision."
      )
    ).toBeInTheDocument();
    expect(fetchCancellationApprovalsList).toHaveBeenCalledWith(
      "pending",
      1,
      20
    );
  });

  it("lists pending requests with routing, stages and started warnings", async () => {
    mockQueuesEmpty();
    vi.mocked(fetchCancellationApprovalsList).mockResolvedValue(listFixture);
    render(<ApprovalsHub />);
    fireEvent.click(
      screen.getByRole("tab", { name: "Cancellation requests" })
    );

    const row = (await screen.findByText("LV-2026-27-900009")).closest(
      "tr"
    ) as HTMLElement;
    const cells = within(row);
    expect(cells.getByText("Thoko Mbewe")).toBeInTheDocument();
    expect(cells.getByText("Annual Leave")).toBeInTheDocument();
    expect(cells.getByText("Supervisor")).toBeInTheDocument();
    expect(cells.getByText(/Starts in \d+ days/)).toBeInTheDocument();

    const link = cells.getByRole("link", { name: "LV-2026-27-900009" });
    expect(link).toHaveAttribute(
      "href",
      "/approvals/app-9?cancellation=canc-1"
    );

    const startedRow = (await screen.findByText("LV-2026-27-900010")).closest(
      "tr"
    ) as HTMLElement;
    expect(within(startedRow).getByText("Started")).toBeInTheDocument();
    expect(screen.getByText(/Showing 1–2 of 2/)).toBeInTheDocument();
  });

  it("returns to the applications queue when the section is toggled back", async () => {
    mockQueuesEmpty();
    render(<ApprovalsHub />);
    await screen.findByText("Nothing waiting for you right now");

    fireEvent.click(
      screen.getByRole("tab", { name: "Cancellation requests" })
    );
    await screen.findByText("No cancellation requests are waiting for you");

    fireEvent.click(screen.getByRole("tab", { name: "Applications" }));
    expect(
      await screen.findByText("Nothing waiting for you right now")
    ).toBeInTheDocument();
    expect(fetchApprovalsList).toHaveBeenCalledTimes(2);
  });
});