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
    expect(screen.getByText("Settings")).toBeInTheDocument();
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
