import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ApprovalsNavItem } from "@/components/approvals/approvals-nav-item";
import { makeCapabilities } from "@/lib/approvals/__fixtures__";
import { fetchCapabilities } from "@/lib/approvals/service";

vi.mock("@/lib/approvals/service", () => ({
  fetchCapabilities: vi.fn(),
}));

const mockedFetchCapabilities = vi.mocked(fetchCapabilities);

describe("ApprovalsNavItem", () => {
  it("renders the link with the pending-count badge when approver", async () => {
    mockedFetchCapabilities.mockResolvedValue(makeCapabilities({ pending_count: 5 }));
    render(<ApprovalsNavItem open />);

    const link = await screen.findByRole("link", { name: /Approvals/ });
    expect(link).toHaveAttribute("href", "/dashboard/approvals");
    expect(screen.getByTestId("approvals-pending-count")).toHaveTextContent("5");
  });

  it("shows a capped badge for large counts", async () => {
    mockedFetchCapabilities.mockResolvedValue(makeCapabilities({ pending_count: 150 }));
    render(<ApprovalsNavItem open />);
    expect(await screen.findByTestId("approvals-pending-count")).toHaveTextContent("99+");
  });

  it("hides the item when the user is not an approver", async () => {
    mockedFetchCapabilities.mockResolvedValue(makeCapabilities({ is_approver: false, pending_count: 0 }));
    render(<ApprovalsNavItem open />);

    await waitFor(() =>
      expect(screen.queryByRole("link", { name: /Approvals/ })).not.toBeInTheDocument()
    );
  });
});