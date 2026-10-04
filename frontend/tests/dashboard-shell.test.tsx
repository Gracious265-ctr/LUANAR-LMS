import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DashboardShell } from "@/components/dashboard/dashboard-shell";

/** The route the mocked `usePathname` reports; tests move it to assert that a
 *  navigation closes the drawer. */
let currentPath = "/dashboard";

vi.mock("next/navigation", async (importOriginal) => {
  const actual = await importOriginal<typeof import("next/navigation")>();
  return {
    ...actual,
    usePathname: () => currentPath,
    useRouter: () => ({
      push: vi.fn(),
      refresh: vi.fn(),
      replace: vi.fn(),
      back: vi.fn(),
      forward: vi.fn(),
      prefetch: vi.fn(),
    }),
  };
});

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
  });

  it("offers My Account to every role, since it is nobody's job", () => {
    // Not inside the HR group: this is the one destination that does not depend
    // on what the person can do, so hiding it from an ordinary employee would
    // make their own password unreachable.
    renderShell(mockUser);
    expect(screen.getByText("My Account")).toBeInTheDocument();

    renderShell({ ...mockUser, role: "hr" });
    expect(screen.getAllByText("My Account").length).toBeGreaterThanOrEqual(1);
  });

  it("links My Account to the account page", () => {
    renderShell(mockUser);

    expect(screen.getByText("My Account").closest("a")).toHaveAttribute(
      "href",
      "/dashboard/account",
    );
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

  it("offers HR the Departments item, because a team is scoped by one", () => {
    renderShell(mockHRUser);

    expect(screen.getByRole("link", { name: "Departments" })).toHaveAttribute(
      "href",
      "/dashboard/hr-admin/departments"
    );
  });

  it("keeps Departments out of a non-HR sidebar", () => {
    renderShell(mockUser);

    expect(screen.queryByRole("link", { name: "Departments" })).toBeNull();
  });

  it("renders a sign-out control", () => {
    renderShell(mockUser);

    expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
  });

  it("offers a theme toggle that repaints the document and persists the choice", async () => {
    renderShell(mockUser);

    const toggle = screen.getByRole("button", {
      name: /switch to dark theme/i,
    });
    expect(toggle).toBeInTheDocument();
    expect(document.documentElement).not.toHaveClass("dark");

    fireEvent.click(toggle);

    // The MutationObserver behind `useTheme` reports asynchronously, so the
    // assertion waits rather than reading the class in the same tick.
    await waitFor(() =>
      expect(document.documentElement).toHaveClass("dark")
    );
    expect(document.cookie).toMatch(/theme=dark/);

    // And the control now offers the way back, so it is not a one-way switch.
    expect(
      screen.getByRole("button", { name: /switch to light theme/i })
    ).toBeInTheDocument();
  });

  it("places the theme toggle beside sign-out in the header, not in the rail", () => {
    renderShell(mockUser);

    const toggle = screen.getByRole("button", { name: /switch to dark theme/i });
    const signOut = screen.getByRole("button", { name: "Sign out" });

    // Same parent, so they are adjacent controls in the header's action group.
    expect(toggle.parentElement).toBe(signOut.parentElement);
    expect(screen.getByRole("banner")).toContainElement(toggle);
    expect(screen.getByRole("navigation")).not.toContainElement(toggle);
  });

  it("keeps the theme toggle reachable when the rail collapses into a drawer", () => {
    // Below `md` the rail is a drawer, so a rail-hosted control would only be
    // reachable after opening it. The header renders at every breakpoint, so the
    // control stays reachable either way.
    setNarrowViewport(true);
    renderShell(mockUser);

    expect(
      screen.getByRole("button", { name: /switch to dark theme/i })
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Hide sidebar" }));
    expect(
      screen.getByRole("button", { name: /switch to dark theme/i })
    ).toHaveAccessibleName(/switch to dark theme/i);
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

/**
 * The drawer is only reachable below the `md` breakpoint, which is measured with
 * `matchMedia`. The global mock starts wide so the rest of this file keeps
 * testing the desktop rail; these cases opt into a narrow viewport explicitly.
 */
function setNarrowViewport(narrow: boolean) {
  (window.matchMedia as unknown as { setNarrow: (v: boolean) => void }).setNarrow(
    narrow,
  );
}

beforeEach(() => {
  currentPath = "/dashboard";
});

afterEach(() => {
  setNarrowViewport(false);
  // The theme lives on the document, so it outlives the render and would leak
  // into the next test unless it is cleared alongside the viewport.
  document.documentElement.classList.remove("light", "dark");
  document.cookie = "theme=; path=/; max-age=0";
});

describe("DashboardShell mobile drawer", () => {
  it("keeps the rail hidden and the drawer closed on a phone", () => {
    setNarrowViewport(true);
    renderShell(mockUser);

    const hamburger = screen.getByRole("button", { name: "Open navigation" });
    expect(hamburger).toBeInTheDocument();
    // No dialog is mounted while it is closed, so the nav links exist only once.
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "My Account" })).toHaveLength(1);
  });

  it("opens on the hamburger and offers the same destinations as the rail", () => {
    setNarrowViewport(true);
    renderShell(mockHRUser, { isApprover: true });

    fireEvent.click(screen.getByRole("button", { name: "Open navigation" }));

    const drawer = screen.getByRole("dialog");
    expect(drawer).toBeInTheDocument();
    // The point of sharing NavLinks: HR destinations must not be rail-only.
    expect(
      within(drawer).getByRole("link", { name: "Audit View" })
    ).toHaveAttribute("href", "/dashboard/hr-admin/audit");
    expect(within(drawer).getByRole("link", { name: "Teams" })).toBeInTheDocument();
  });

  it("labels the drawer for a screen reader and marks the trigger state", () => {
    setNarrowViewport(true);
    renderShell(mockUser);

    const hamburger = screen.getByRole("button", { name: "Open navigation" });
    // The trigger is wired to the region it controls, and the region exists in
    // the accessibility tree even before the drawer opens.
    expect(hamburger).toHaveAttribute("aria-controls", "dashboard-nav");
    expect(hamburger).toHaveAttribute("aria-expanded", "false");

    fireEvent.click(hamburger);

    expect(screen.getByRole("dialog")).toHaveAttribute("id", "dashboard-nav");
    expect(
      screen.getByRole("heading", { name: /Navigation for Test Employee/ })
    ).toBeInTheDocument();
    // Radix marks the rest of the document `aria-hidden` while a modal is open,
    // so the trigger is deliberately unreachable -- that is the modal contract,
    // not a bug, and it is why `aria-expanded` needs no special-casing while open.
    expect(
      screen.queryByRole("button", { name: "Open navigation" })
    ).not.toBeInTheDocument();

    fireEvent.keyDown(document, { key: "Escape" });
    expect(
      screen.getByRole("button", { name: "Open navigation" })
    ).toHaveAttribute("aria-expanded", "false");
  });

  it("closes on Escape", () => {
    setNarrowViewport(true);
    renderShell(mockUser);

    fireEvent.click(screen.getByRole("button", { name: "Open navigation" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("closes from its own close button", () => {
    setNarrowViewport(true);
    renderShell(mockUser);

    fireEvent.click(screen.getByRole("button", { name: "Open navigation" }));
    fireEvent.click(screen.getByRole("button", { name: "Close navigation" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("closes on a route change so it cannot sit over the new page", () => {
    setNarrowViewport(true);
    const { rerender } = render(
      <DashboardShell user={mockUser} isApprover={false} pendingApprovals={0}>
        <div>Test content</div>
      </DashboardShell>
    );

    fireEvent.click(screen.getByRole("button", { name: "Open navigation" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    // Next's router is the only party that knows a navigation happened, and it
    // reports it by changing the value `usePathname` returns.
    act(() => {
      currentPath = "/dashboard/leave/new";
      rerender(
        <DashboardShell user={mockUser} isApprover={false} pendingApprovals={0}>
          <div>Test content</div>
        </DashboardShell>
      );
    });

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
