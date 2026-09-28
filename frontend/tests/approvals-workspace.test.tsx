import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApprovalsWorkspace } from "@/components/approvals/approvals-workspace";
import type { DelegateCandidate, Delegation } from "@/lib/delegations";

vi.mock("@/components/approvals/approvals-list", () => ({
  ApprovalsList: () => <div>applications queue</div>,
}));

vi.mock("@/components/cancellations/cancellation-requests-table", () => ({
  CancellationRequestsTable: () => <div>cancellations queue</div>,
}));

const delegation: Delegation = {
  id: 9,
  approver: 3,
  approver_name: "Jane Dean",
  approver_role: "dean",
  delegate: 5,
  delegate_name: "Bob HOD",
  starts_on: "2026-10-01",
  ends_on: "2026-11-01",
  request_reason: "On study leave",
  requested_by: 3,
  requested_by_name: "Jane Dean",
  decision_reason: "Approved",
  decided_by: 1,
  decided_at: "2026-09-26T12:05:00Z",
  status: "approved",
  state: "scheduled",
  created_at: "2026-09-26T12:00:00Z",
  updated_at: "2026-09-26T12:05:00Z",
};

const candidates: DelegateCandidate[] = [
  { id: 5, full_name: "Bob HOD", role: "approver" },
];

describe("ApprovalsWorkspace", () => {
  it("hides the cover tab from a non-approver", () => {
    render(<ApprovalsWorkspace />);

    expect(screen.queryByRole("tab", { name: "Cover" })).toBeNull();
    expect(screen.getByText("applications queue")).toBeInTheDocument();
  });

  it("shows the cover tab to an approver", () => {
    render(<ApprovalsWorkspace canRequestCover />);

    expect(screen.getByRole("tab", { name: "Cover" })).toBeInTheDocument();
  });

  it("opens straight onto the cover tab when initialView says so", () => {
    render(
      <ApprovalsWorkspace
        canRequestCover
        initialView="cover"
        delegations={[delegation]}
        candidates={candidates}
      />
    );

    expect(screen.getByText("Your delegations")).toBeInTheDocument();
    expect(screen.queryByText("applications queue")).not.toBeInTheDocument();
  });

  it("opens the cover panel with the request form and the approver's rows", () => {
    render(
      <ApprovalsWorkspace
        canRequestCover
        delegations={[delegation]}
        candidates={candidates}
      />
    );

    fireEvent.click(screen.getByRole("tab", { name: "Cover" }));

    expect(
      screen.getByRole("button", { name: "Request cover" })
    ).toBeInTheDocument();
    expect(screen.getByText("Your delegations")).toBeInTheDocument();
    expect(screen.getByText("Jane Dean")).toBeInTheDocument();
    // A row links into the approver's own view, never the HR review page.
    expect(screen.getByRole("link", { name: "Jane Dean" }).getAttribute("href")).toBe(
      "/dashboard/cover/9"
    );
  });

  it("shows the load error instead of a stale empty list", () => {
    render(
      <ApprovalsWorkspace
        canRequestCover
        delegations={null}
        candidates={[]}
        delegationsError="Unable to load your delegations."
      />
    );

    fireEvent.click(screen.getByRole("tab", { name: "Cover" }));

    expect(screen.getByText("Unable to load your delegations.")).toBeInTheDocument();
    expect(screen.queryByText("No delegations found")).toBeNull();
  });

  it("keeps the other queues reachable", () => {
    render(<ApprovalsWorkspace canRequestCover delegations={[]} candidates={[]} />);

    fireEvent.click(
      screen.getByRole("tab", { name: "Cancellation requests" })
    );
    expect(screen.getByText("cancellations queue")).toBeInTheDocument();
  });
});
