import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import { DelegationTable } from "@/components/hr/delegation-table";
import type { Delegation } from "@/lib/delegations";

const delegate: Delegation = {
  id: 1,
  approver: 3,
  approver_name: "Jane Dean",
  approver_role: "dean",
  delegate: 5,
  delegate_name: "Bob HOD",
  starts_on: "2026-10-01",
  ends_on: "2026-10-31",
  request_reason: "Attending a conference",
  requested_by: 1,
  requested_by_name: "Aisha HR",
  decision_reason: "Approved",
  decided_by: 1,
  decided_at: "2026-09-18T12:00:00Z",
  status: "approved",
  state: "scheduled",
  created_at: "2026-09-17T12:00:00Z",
  updated_at: "2026-09-18T12:00:00Z",
};

const requested: Delegation = {
  ...delegate,
  id: 2,
  delegate: null,
  delegate_name: "",
  state: "requested",
  status: "requested",
};

describe("DelegationTable", () => {
  it("renders approver, delegate, period, and state badge", () => {
    render(<DelegationTable delegations={[delegate]} />);

    expect(screen.getByText("Jane Dean")).toBeInTheDocument();
    expect(screen.getByText("Bob HOD")).toBeInTheDocument();
    expect(screen.getByText("2026-10-01 → 2026-10-31")).toBeInTheDocument();
    expect(screen.getByText("Scheduled")).toBeInTheDocument();
  });

  it("shows an open-ended period label", () => {
    render(
      <DelegationTable
        delegations={[{ ...delegate, ends_on: null, state: "active" }]}
      />
    );

    expect(
      screen.getByText("From 2026-10-01 (open-ended)")
    ).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("shows Not yet assigned until a delegate is set", () => {
    render(<DelegationTable delegations={[requested]} />);

    expect(screen.getByText("Not yet assigned")).toBeInTheDocument();
    expect(screen.getByText("Requested")).toBeInTheDocument();
  });

  it("renders the state badge for a rejected delegation", () => {
    render(
      <DelegationTable
        delegations={[{ ...requested, state: "rejected", status: "rejected" }]}
      />
    );

    expect(screen.getByText("Rejected")).toBeInTheDocument();
  });

  it("links each row to the review page", () => {
    render(<DelegationTable delegations={[delegate]} />);

    const link = screen.getByRole("link", { name: "Jane Dean" });
    expect(link.getAttribute("href")).toBe(
      "/hr-admin/delegations/1"
    );
  });

  it("honours an alternate base href and empty hint", () => {
    render(
      <DelegationTable
        delegations={[delegate]}
        baseHref="/approvals/cover"
      />
    );

    expect(
      screen
        .getByRole("link", { name: "Jane Dean" })
        .getAttribute("href")
    ).toBe("/approvals/cover/1");

    render(
      <DelegationTable delegations={[]} emptyHint="Nothing to hand over yet." />
    );
    expect(screen.getByText("Nothing to hand over yet.")).toBeInTheDocument();
  });

  it("renders an empty state when there are no delegations", () => {
    render(<DelegationTable delegations={[]} />);

    expect(screen.getByText("No delegations found")).toBeInTheDocument();
  });
});
