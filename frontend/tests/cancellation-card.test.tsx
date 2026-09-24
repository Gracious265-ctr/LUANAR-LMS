import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CancellationCard } from "@/components/cancellation/CancellationCard";
import { fetchCancellations } from "@/lib/cancellation/service";
import type { CancellationRequestSummary } from "@/lib/cancellation/types";

vi.mock("@/lib/cancellation/service", () => ({
  fetchCancellations: vi.fn(),
}));

function stage(order: number, status: CancellationRequestSummary["stages"][number]["status"], roleLabel = "Supervisor") {
  return {
    order,
    role: "supervisor",
    role_label: roleLabel,
    approver_name: order === 1 ? "Mr. Chikondi Banda" : "Dr. Grace Mwale",
    status,
    decided_at: status === "pending" ? null : "2026-10-16T13:40:00Z",
    comment: status === "rejected" ? "Coverage is in place for that week." : "",
  };
}

function request(
  overrides: Partial<CancellationRequestSummary> = {}
): CancellationRequestSummary {
  return {
    id: "req-1",
    kind: "approved_leave",
    status: "pending",
    reason: "I need to travel for family reasons.",
    requested_at: "2026-10-20T08:00:00Z",
    decided_at: null,
    stage_version: 1,
    balance_restored_days: "0",
    restored_financial_year: null,
    employee_notification_state: "pending",
    application_status_at_request: "approved",
    leave_started: false,
    stages: [stage(1, "pending")],
    current_stage_role: "Supervisor",
    application: {
      reference_number: "LV-2026-27-900004",
      start_date: "2026-11-02",
      end_date: "2026-11-06",
      working_days: 5,
    },
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("CancellationCard", () => {
  it("renders nothing when there are no cancellation requests", async () => {
    vi.mocked(fetchCancellations).mockResolvedValue([]);
    const { container } = render(<CancellationCard applicationId="app-1" />);
    await vi.waitFor(() => expect(fetchCancellations).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("shows a pending request with the stage stepper, reason and notification chip", async () => {
    vi.mocked(fetchCancellations).mockResolvedValue([request()]);
    render(<CancellationCard applicationId="app-1" />);

    const card = within(await (await screen.findByText("Leave cancellation")).closest("section") as HTMLElement);
    expect(card.getByText("Pending")).toBeInTheDocument();
    expect(card.getByText("I need to travel for family reasons.")).toBeInTheDocument();
    expect(card.getByLabelText("Cancellation progress")).toBeInTheDocument();
    expect(card.getByText("Supervisor")).toBeInTheDocument();
    expect(card.getByText("Mr. Chikondi Banda")).toBeInTheDocument();
    expect(card.getByText("Awaiting decision")).toBeInTheDocument();
    expect(
      card.getByText("Outcome notification: Pending")
    ).toBeInTheDocument();
  });

  it("renders the approved outcome with restored days and the FY label", async () => {
    vi.mocked(fetchCancellations).mockResolvedValue([
      request({
        status: "approved",
        balance_restored_days: "5",
        restored_financial_year: "2026-27",
        decided_at: "2026-10-24T09:00:00Z",
        employee_notification_state: "sent",
        stages: [
          stage(1, "approved"),
          { order: 2, role: "hod", role_label: "HOD", approver_name: "Dr. Grace Mwale", status: "approved", decided_at: "2026-10-23T10:00:00Z", comment: "" },
        ],
      }),
    ]);
    render(<CancellationCard applicationId="app-1" />);

    const card = within(await (await screen.findByText("Leave cancellation")).closest("section") as HTMLElement);
    expect(card.getByText("Cancelled")).toBeInTheDocument();
    expect(card.getByText("Leave cancelled.")).toBeInTheDocument();
    expect(
      card.getByText("5 annual leave days restored to FY 2026-27 balance.")
    ).toBeInTheDocument();
    expect(card.getByText("Outcome notification: Sent")).toBeInTheDocument();
  });

  it("renders the approved outcome when nothing was restored", async () => {
    vi.mocked(fetchCancellations).mockResolvedValue([
      request({
        status: "approved",
        balance_restored_days: "0",
        restored_financial_year: null,
        employee_notification_state: "not_required",
        stages: [stage(1, "approved", "HOD")],
      }),
    ]);
    render(<CancellationCard applicationId="app-1" />);

    const card = within(await (await screen.findByText("Leave cancellation")).closest("section") as HTMLElement);
    expect(
      card.getByText("No annual leave balance was affected.")
    ).toBeInTheDocument();
    expect(
      card.getByText("Outcome notification: Not required")
    ).toBeInTheDocument();
  });

  it("renders the rejected outcome with the rejecting comment", async () => {
    vi.mocked(fetchCancellations).mockResolvedValue([
      request({
        status: "rejected",
        decided_at: "2026-10-22T11:00:00Z",
        stages: [
          stage(1, "approved", "Supervisor"),
          {
            order: 2,
            role: "hod",
            role_label: "HOD",
            approver_name: "Dr. Grace Mwale",
            status: "rejected",
            decided_at: "2026-10-22T11:00:00Z",
            comment: "Coverage is not yet confirmed for that week.",
          },
          stage(3, "not_reached", "Registrar"),
        ],
      }),
    ]);
    render(<CancellationCard applicationId="app-1" />);

    const card = within(await (await screen.findByText("Leave cancellation")).closest("section") as HTMLElement);
    expect(card.getAllByText("Rejected").length).toBeGreaterThan(0);
    expect(card.getByText("Your leave remains approved.")).toBeInTheDocument();
    expect(
      card.getByText("HOD: “Coverage is not yet confirmed for that week.”")
    ).toBeInTheDocument();
  });

  it("collects earlier requests under a collapsible history", async () => {
    vi.mocked(fetchCancellations).mockResolvedValue([
      request(),
      request({
        id: "req-0",
        status: "rejected",
        reason: "The dates no longer work.",
        requested_at: "2026-10-10T08:00:00Z",
        employee_notification_state: "failed",
        stages: [
          {
            order: 1,
            role: "hod",
            role_label: "HOD",
            approver_name: "Dr. Grace Mwale",
            status: "rejected",
            decided_at: "2026-10-12T08:00:00Z",
            comment: "Please re-apply later.",
          },
        ],
      }),
    ]);
    render(<CancellationCard applicationId="app-1" />);

    const summary = await screen.findByText("Cancellation history (1)");
    expect(summary).toBeInTheDocument();
    // The collapsible is closed by default; nothing of the older request shows yet.
    expect(screen.queryByText("The dates no longer work.")).not.toBeInTheDocument();
  });

  it("shows withdrawal requests with a slate status", async () => {
    vi.mocked(fetchCancellations).mockResolvedValue([
      request({
        kind: "withdrawal",
        status: "approved",
        balance_restored_days: "0",
        restored_financial_year: null,
        stages: [],
      }),
    ]);
    render(<CancellationCard applicationId="app-1" />);

    const card = within(await (await screen.findByText("Leave cancellation")).closest("section") as HTMLElement);
    const badge = card.getByText("Cancelled");
    expect(badge.className).toContain("status-cancelled");
    expect(
      card.getByText("No annual leave balance was affected.")
    ).toBeInTheDocument();
  });
});