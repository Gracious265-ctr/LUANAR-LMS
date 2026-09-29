import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PlanApprovalsWorkspace } from "@/components/plans/plan-approvals-workspace";
import { fetchApprovalsList } from "@/lib/plans/service";
import { makeApprovalItem, makeApprovalList } from "@/lib/plans/__fixtures__";

vi.mock("@/lib/plans/service", () => ({
  fetchApprovalsList: vi.fn(),
}));

describe("PlanApprovalsWorkspace", () => {
  it("shows an empty state when nothing is pending", async () => {
    vi.mocked(fetchApprovalsList).mockResolvedValue({
      ok: true,
      data: makeApprovalList({ count: 0, results: [] }),
    });

    render(<PlanApprovalsWorkspace />);

    await waitFor(() =>
      expect(screen.getByText("Nothing pending")).toBeInTheDocument()
    );
  });

  it("renders pending approval rows as links", async () => {
    const item = makeApprovalItem();
    vi.mocked(fetchApprovalsList).mockResolvedValue({
      ok: true,
      data: makeApprovalList({ results: [item] }),
    });

    render(<PlanApprovalsWorkspace />);

    await screen.findByText(item.employee_name);
    expect(screen.getByRole("link", { name: /Mphatso Kachale/ })).toHaveAttribute(
      "href",
      "/dashboard/plans/approvals/plan-1"
    );
    expect(screen.getByText(/with Supervisor/)).toBeInTheDocument();
  });

  it("switches to the decided tab", async () => {
    vi.mocked(fetchApprovalsList).mockResolvedValue({
      ok: true,
      data: makeApprovalList({ tab: "pending", count: 0, results: [] }),
    });

    render(<PlanApprovalsWorkspace />);
    fireEvent.click(screen.getByRole("button", { name: "Decided" }));

    await waitFor(() =>
      expect(fetchApprovalsList).toHaveBeenCalledWith("decided", 1)
    );
  });
});