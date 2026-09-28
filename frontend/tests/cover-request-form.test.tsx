import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

import { CoverRequestForm } from "@/components/approvals/cover-request-form";
import type { DelegateCandidate } from "@/lib/delegations";

vi.mock("@/lib/delegations-client", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/lib/delegations-client")>();
  return {
    ...actual,
    createDelegation: vi.fn(),
  };
});

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: vi.fn(), push: vi.fn() }),
}));

import { createDelegation } from "@/lib/delegations-client";

const candidates: DelegateCandidate[] = [
  { id: 5, full_name: "Bob HOD", role: "approver" },
  { id: 6, full_name: "Rita Registrar", role: "approver" },
];

describe("CoverRequestForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(createDelegation).mockResolvedValue({
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
      decision_reason: "",
      decided_by: null,
      decided_at: null,
      status: "requested",
      state: "requested",
      created_at: "2026-09-26T12:00:00Z",
      updated_at: "2026-09-26T12:00:00Z",
    });
  });

  it("renders the cover fields and never asks who the approver is", () => {
    render(<CoverRequestForm candidates={candidates} />);

    expect(screen.getByLabelText("Starts on")).toBeInTheDocument();
    expect(screen.getByLabelText("Ends on")).toBeInTheDocument();
    expect(screen.getByLabelText("Nominate a delegate")).toBeInTheDocument();
    expect(screen.getByLabelText("Reason")).toBeInTheDocument();
    expect(screen.queryByLabelText("Approver")).toBeNull();
    expect(
      screen.getByRole("button", { name: "Request cover" })
    ).toBeInTheDocument();
  });

  it("offers the supplied candidates for nomination", () => {
    render(<CoverRequestForm candidates={candidates} />);

    const select = screen.getByLabelText("Nominate a delegate");
    expect(
      Array.from(select.querySelectorAll("option")).map((o) => o.textContent)
    ).toEqual(["No nomination", "Bob HOD", "Rita Registrar"]);
  });

  it("submits without an approver so the backend can force the requester", () => {
    render(<CoverRequestForm candidates={candidates} />);

    fireEvent.change(screen.getByLabelText("Starts on"), {
      target: { value: "2026-10-01" },
    });
    fireEvent.change(screen.getByLabelText("Nominate a delegate"), {
      target: { value: "5" },
    });
    fireEvent.change(screen.getByLabelText("Reason"), {
      target: { value: "On study leave" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Request cover" }));

    expect(createDelegation).toHaveBeenCalledWith({
      delegate: 5,
      starts_on: "2026-10-01",
      ends_on: null,
      request_reason: "On study leave",
    });
    expect(vi.mocked(createDelegation).mock.calls[0][0]).not.toHaveProperty(
      "approver"
    );
  });

  it("sends null when no delegate or end date is chosen", () => {
    render(<CoverRequestForm candidates={candidates} />);

    fireEvent.change(screen.getByLabelText("Starts on"), {
      target: { value: "2026-10-01" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Request cover" }));

    expect(createDelegation).toHaveBeenCalledWith({
      delegate: null,
      starts_on: "2026-10-01",
      ends_on: null,
      request_reason: "",
    });
  });

  it("surfaces a backend rejection such as the one-open-request rule", async () => {
    vi.mocked(createDelegation).mockRejectedValue(
      new Error("approver: This approver already has an open delegation request.")
    );
    render(<CoverRequestForm candidates={candidates} />);

    fireEvent.change(screen.getByLabelText("Starts on"), {
      target: { value: "2026-10-01" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Request cover" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "already has an open delegation request"
    );
  });
});
