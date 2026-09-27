import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import { DashboardShell } from "@/components/dashboard/dashboard-shell";

const mockUser = {
  id: 1,
  email: "employee@test.luanar",
  role: "employee",
  full_name: "Test Employee",
};

const mockApproverUser = {
  id: 2,
  email: "supervisor@test.luanar",
  role: "supervisor",
  full_name: "Test Supervisor",
};

const mockHRUser = {
  id: 3,
  email: "hr@test.luanar",
  role: "hr",
  full_name: "Test HR",
};

describe("DashboardShell", () => {
  it("renders the user's name and role", () => {
    render(
      <DashboardShell user={mockUser}>
        <div>Test content</div>
      </DashboardShell>
    );

    expect(screen.getAllByText("Test Employee").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Employee").length).toBeGreaterThanOrEqual(1);
  });

  it("renders Dashboard nav item for all roles", () => {
    render(
      <DashboardShell user={mockUser}>
        <div>Test content</div>
      </DashboardShell>
    );

    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("My Applications")).toBeInTheDocument();
    expect(screen.getByText("New Application")).toBeInTheDocument();
    expect(screen.queryByText("Settings")).not.toBeInTheDocument();
    expect(screen.queryByText("Account")).not.toBeInTheDocument();
  });

  it("does not show Approvals for employee role", () => {
    render(
      <DashboardShell user={mockUser}>
        <div>Test content</div>
      </DashboardShell>
    );

    expect(screen.queryByText("Approvals")).not.toBeInTheDocument();
  });

  it("shows Approvals for supervisor role", () => {
    render(
      <DashboardShell user={mockApproverUser}>
        <div>Test content</div>
      </DashboardShell>
    );

    expect(screen.getByText("Approvals")).toBeInTheDocument();
  });

  it("shows the Audit View item for HR role", () => {
    render(
      <DashboardShell user={mockHRUser}>
        <div>Test content</div>
      </DashboardShell>
    );

    const link = screen.getByRole("link", { name: "Audit View" });
    expect(link).toHaveAttribute("href", "/dashboard/hr-admin/audit");
  });

  it("shows Request Cover for an approver but not for an employee", () => {
    const { unmount } = render(
      <DashboardShell user={mockApproverUser}>
        <div>Test content</div>
      </DashboardShell>
    );

    expect(screen.getByRole("link", { name: "Request Cover" })).toHaveAttribute(
      "href",
      "/dashboard/cover"
    );
    unmount();

    render(
      <DashboardShell user={mockUser}>
        <div>Test content</div>
      </DashboardShell>
    );

    expect(
      screen.queryByRole("link", { name: "Request Cover" })
    ).not.toBeInTheDocument();
  });

  it("keeps the HR Delegations item and adds Request Cover for HR", () => {
    render(
      <DashboardShell user={mockHRUser}>
        <div>Test content</div>
      </DashboardShell>
    );

    // HR gets both: the management list and their own cover page.
    expect(screen.getByRole("link", { name: "Delegations" })).toHaveAttribute(
      "href",
      "/dashboard/hr-admin/delegations"
    );
    expect(screen.getByRole("link", { name: "Request Cover" })).toBeInTheDocument();
  });

  it("renders a sign-out control", () => {
    render(
      <DashboardShell user={mockUser}>
        <div>Test content</div>
      </DashboardShell>
    );

    expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
  });

  it("does not render a theme toggle", () => {
    render(
      <DashboardShell user={mockUser}>
        <div>Test content</div>
      </DashboardShell>
    );

    expect(
      screen.queryByRole("button", { name: /theme|dark mode/i })
    ).not.toBeInTheDocument();
  });
});
