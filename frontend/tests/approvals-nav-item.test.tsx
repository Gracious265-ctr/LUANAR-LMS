import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ApprovalsNavItem } from "@/components/approvals/approvals-nav-item";

describe("ApprovalsNavItem", () => {
  it("renders the link with the pending-count badge when approver", () => {
    render(<ApprovalsNavItem open isApprover pendingCount={5} />);

    const link = screen.getByRole("link", { name: /Approvals/ });
    expect(link).toHaveAttribute("href", "/approvals");
    expect(screen.getByTestId("approvals-pending-count")).toHaveTextContent("5");
  });

  it("shows a capped badge for large counts", () => {
    render(<ApprovalsNavItem open isApprover pendingCount={150} />);
    expect(screen.getByTestId("approvals-pending-count")).toHaveTextContent("99+");
  });

  it("hides the item when the user is not an approver", () => {
    const { container } = render(<ApprovalsNavItem open isApprover={false} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows no badge when the count is unknown or zero", () => {
    render(<ApprovalsNavItem open isApprover pendingCount={0} />);
    expect(
      screen.queryByTestId("approvals-pending-count")
    ).not.toBeInTheDocument();
  });

  it("hides the badge while the sidebar is collapsed", () => {
    render(<ApprovalsNavItem open={false} isApprover pendingCount={5} />);
    expect(
      screen.queryByTestId("approvals-pending-count")
    ).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Approvals/ })).toBeInTheDocument();
  });
});
