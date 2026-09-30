import { fireEvent, render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import { DashboardShell } from "@/components/dashboard/dashboard-shell";

const mockUser = {
  id: 1,
  email: "employee@test.luanar",
  role: "employee",
  full_name: "Test Employee",
};

// An approver position is held as data, so this account's own role stays
// `employee` while the server reports it as an approver.
const mockApproverUser = {
  id: 2,
  email: "staff@test.luanar",
  role: "employee",
  full_name: "Test Approver",
};

const mockHRUser = {
  id: 3,
  email: "hr@test.luanar",
  role: "hr",
  full_name: "Test HR",
};

/**
 * Renders the shell with the approver access the layout already resolved on
 * the server, so the sidebar is settled on the first paint and no read is
 * repeated in the browser.
 */
function renderShell(
  user: (typeof mockUser),
  approver: { isApprover: boolean; pendingApprovals?: number } = {
    isApprover: false,
  }
) {
  return render(
    <DashboardShell
      user={user}
      isApprover={approver.isApprover}
      pendingApprovals={approver.pendingApprovals ?? 0}
    >
      <div>Test content</div>
    </DashboardShell>
  );
}

describe("DashboardShell", () => {
  it("renders the user's name and role", () => {
    renderShell(mockUser);

    expect(screen.getAllByText("Test Employee").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Employee").length).toBeGreaterThanOrEqual(1);
  });

  it("renders Dashboard nav item for all roles", () => {
    renderShell(mockUser);

    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("My Applications")).toBeInTheDocument();
    expect(screen.getByText("New Application")).toBeInTheDocument();
    expect(screen.queryByText("Settings")).not.toBeInTheDocument();
    expect(screen.queryByText("Account")).not.toBeInTheDocument();
  });

  it("hides Approvals from a caller the server does not call an approver", () => {
    renderShell(mockUser);

    expect(screen.queryByText("Approvals")).not.toBeInTheDocument();
  });

  it("shows Approvals to an approver whose account role is plain employee", () => {
    renderShell(mockApproverUser, { isApprover: true });

    expect(screen.getByText("Approvals")).toBeInTheDocument();
  });

  it("badges Approvals with the pending count the layout resolved", () => {
    renderShell(mockApproverUser, { isApprover: true, pendingApprovals: 4 });

    expect(screen.getByTestId("approvals-pending-count")).toHaveTextContent("4");
  });

  it("shows the Audit View item for HR role", () => {
    renderShell(mockHRUser);

    const link = screen.getByRole("link", { name: "Audit View" });
    expect(link).toHaveAttribute("href", "/dashboard/hr-admin/audit");
  });

  it("shows Request Cover to an approver but not to an ordinary employee", () => {
    const { unmount } = renderShell(mockApproverUser, { isApprover: true });

    expect(screen.getByRole("link", { name: "Request Cover" })).toHaveAttribute(
      "href",
      "/dashboard/cover"
    );
    unmount();

    renderShell(mockUser);

    expect(
      screen.queryByRole("link", { name: "Request Cover" })
    ).not.toBeInTheDocument();
  });

  it("keeps the HR Delegations item and adds Request Cover for HR", () => {
    renderShell(mockHRUser, { isApprover: true });

    // HR gets both: the management list and their own cover page.
    expect(screen.getByRole("link", { name: "Delegations" })).toHaveAttribute(
      "href",
      "/dashboard/hr-admin/delegations"
    );
    expect(screen.getByRole("link", { name: "Request Cover" })).toBeInTheDocument();
  });

  it("offers HR the Teams and Roles items", () => {
    renderShell(mockHRUser, { isApprover: true });

    expect(screen.getByRole("link", { name: "Teams" })).toHaveAttribute(
      "href",
      "/dashboard/hr-admin/teams"
    );
    expect(screen.getByRole("link", { name: "Roles" })).toHaveAttribute(
      "href",
      "/dashboard/hr-admin/roles"
    );
  });

  it("renders a sign-out control", () => {
    renderShell(mockUser);

    expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
  });

  it("does not render a theme toggle", () => {
    renderShell(mockUser);

    expect(
      screen.queryByRole("button", { name: /theme|dark mode/i })
    ).not.toBeInTheDocument();
  });

  it("renders the hide toggle at the top of the sidebar", () => {
    renderShell(mockUser);

    const nav = screen.getByRole("navigation");
    expect(screen.getByRole("button", { name: "Hide sidebar" })).toBeInTheDocument();
    expect(nav).toHaveClass("w-64");
  });

  it("collapses and re-expands the sidebar from the top toggle", () => {
    renderShell(mockUser);

    const nav = screen.getByRole("navigation");
    fireEvent.click(screen.getByRole("button", { name: "Hide sidebar" }));
    expect(nav).toHaveClass("w-16");
    expect(screen.getByRole("button", { name: "Show sidebar" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Show sidebar" }));
    expect(nav).toHaveClass("w-64");
    expect(screen.getByRole("button", { name: "Hide sidebar" })).toBeInTheDocument();
  });
});