import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DashboardShell } from "@/components/dashboard/dashboard-shell";
import { fetchCapabilities } from "@/lib/approvals/service";

vi.mock("@/lib/approvals/service", () => ({
  fetchCapabilities: vi.fn(),
}));

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

const employeeCapabilities = { is_approver: false, pending_count: 0 };
const approverCapabilities = { is_approver: true, pending_count: 3 };

function renderShell(user: typeof mockUser) {
  return render(
    <DashboardShell user={user}>
      <div>Test content</div>
    </DashboardShell>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(fetchCapabilities).mockResolvedValue(employeeCapabilities);
});

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
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  it("does not show Approvals when the user is not an approver", async () => {
    vi.mocked(fetchCapabilities).mockResolvedValue(employeeCapabilities);
    renderShell(mockUser);

    await waitFor(() => {
      expect(fetchCapabilities).toHaveBeenCalled();
    });
    expect(screen.queryByRole("link", { name: /approvals/i })).not.toBeInTheDocument();
  });

  it("shows Approvals with the pending count for a role with capacity", async () => {
    vi.mocked(fetchCapabilities).mockResolvedValue(approverCapabilities);
    renderShell(mockApproverUser);

    const navItem = await screen.findByRole("link", { name: /approvals/i });
    expect(navItem).toBeInTheDocument();
    expect(screen.getByText("Approvals")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
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
});