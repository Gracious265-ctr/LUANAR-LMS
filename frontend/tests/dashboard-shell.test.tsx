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

// A team manager is an ordinary employee whose only claim to the Workflows
// module is a team they are flagged to manage.
const mockTeamManagerUser = {
  id: 4,
  email: "manager@test.luanar",
  role: "employee",
  full_name: "Test Manager",
  manages_teams: true,
};

// The bootstrap administrator: not HR by role, but admitted to every team the
// way HR is, and offered the module's configuration destinations with it.
const mockAdminUser = {
  id: 5,
  email: "admin@test.luanar",
  role: "employee",
  full_name: "Test Admin",
  is_superuser: true,
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
      "/dashboard/teams"
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

    const nav = document.getElementById("dashboard-nav");
    expect(nav).not.toBeNull();
    expect(screen.getByRole("button", { name: "Hide sidebar" })).toBeInTheDocument();
    expect(nav).toHaveClass("w-64", "rounded-3xl", "h-full");
  });

  it("collapses and re-expands the sidebar from the top toggle", () => {
    renderShell(mockUser);

    const nav = document.getElementById("dashboard-nav");
    expect(nav).not.toBeNull();
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

    const drawer = screen.getByRole("dialog");
    expect(drawer).toHaveAttribute("id", "dashboard-nav");
    expect(drawer).toHaveClass("rounded-3xl", "inset-y-4", "left-4");
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

describe("DashboardShell Leave module", () => {
  it("scopes the rail to the launcher plus exactly the five Leave items", () => {
    currentPath = "/dashboard/leave";
    // An HR approver is the strictest case: the module rail must hide their HR
    // and approvals destinations, not merely the employee-only extras.
    renderShell(mockHRUser, { isApprover: true, pendingApprovals: 4 });

    const nav = screen.getByRole("navigation");
    expect(within(nav).getByRole("link", { name: "All apps" })).toHaveAttribute(
      "href",
      "/",
    );
    expect(within(nav).getByRole("link", { name: "Dashboard" })).toHaveAttribute(
      "href",
      "/dashboard/leave",
    );
    expect(
      within(nav).getByRole("link", { name: "My Applications" }),
    ).toHaveAttribute("href", "/dashboard/leave/applications");
    expect(within(nav).getByRole("link", { name: "Drafts" })).toHaveAttribute(
      "href",
      "/dashboard/leave/drafts",
    );
    expect(within(nav).getByRole("link", { name: "On Leave" })).toHaveAttribute(
      "href",
      "/dashboard/leave/on-leave",
    );
    expect(
      within(nav).getByRole("link", { name: "New Application" }),
    ).toHaveAttribute("href", "/dashboard/leave/new");

    // Exactly five destinations and the launcher — nothing leaks in.
    expect(within(nav).getAllByRole("link")).toHaveLength(6);

    for (const hidden of [
      "Approvals",
      "Leave Plans",
      "Request Cover",
      "My Account",
      "Audit View",
      "Teams",
    ]) {
      expect(within(nav).queryByRole("link", { name: hidden })).not.toBeInTheDocument();
    }
  });

  it("keeps the full institutional rail outside the Leave module", () => {
    currentPath = "/dashboard/account";
    renderShell(mockUser);

    const nav = screen.getByRole("navigation");
    expect(within(nav).getByRole("link", { name: "My Account" })).toBeInTheDocument();
    expect(within(nav).queryByRole("link", { name: "All apps" })).not.toBeInTheDocument();
  });

  it.each([
    ["/dashboard/leave/applications"],
    ["/applications/9"],
  ])("marks My Applications active at %s", (path) => {
    currentPath = path;
    renderShell(mockUser);

    const nav = screen.getByRole("navigation");
    expect(
      within(nav).getByRole("link", { name: "My Applications" }),
    ).toHaveAttribute("aria-current", "page");
    expect(within(nav).getByRole("link", { name: "Dashboard" })).not.toHaveAttribute(
      "aria-current",
    );
    expect(within(nav).getByRole("link", { name: "Drafts" })).not.toHaveAttribute(
      "aria-current",
    );
    expect(
      within(nav).getByRole("link", { name: "New Application" }),
    ).not.toHaveAttribute("aria-current");
  });

  it("marks Drafts active on the drafts list", () => {
    currentPath = "/dashboard/leave/drafts";
    renderShell(mockUser);

    const nav = screen.getByRole("navigation");
    expect(within(nav).getByRole("link", { name: "Drafts" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(
      within(nav).getByRole("link", { name: "My Applications" }),
    ).not.toHaveAttribute("aria-current");
    expect(within(nav).getByRole("link", { name: "Dashboard" })).not.toHaveAttribute(
      "aria-current",
    );
  });

  it("marks On Leave active on the on-leave page", () => {
    currentPath = "/dashboard/leave/on-leave";
    renderShell(mockUser);

    const nav = screen.getByRole("navigation");
    expect(within(nav).getByRole("link", { name: "On Leave" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(within(nav).getByRole("link", { name: "Drafts" })).not.toHaveAttribute(
      "aria-current",
    );
    expect(
      within(nav).getByRole("link", { name: "My Applications" }),
    ).not.toHaveAttribute("aria-current");
  });

  it("marks Dashboard active only on the Leave index", () => {
    currentPath = "/dashboard/leave";
    renderShell(mockUser);

    const nav = screen.getByRole("navigation");
    expect(within(nav).getByRole("link", { name: "Dashboard" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(
      within(nav).getByRole("link", { name: "My Applications" }),
    ).not.toHaveAttribute("aria-current");
  });
});

describe("DashboardShell Plans module", () => {
  it("scopes the rail to the launcher plus exactly the three Plans items", () => {
    currentPath = "/dashboard/plans";
    renderShell(mockHRUser, { isApprover: true, pendingApprovals: 4 });

    const nav = screen.getByRole("navigation");
    expect(within(nav).getByRole("link", { name: "All apps" })).toHaveAttribute(
      "href",
      "/",
    );
    expect(within(nav).getByRole("link", { name: "My Plans" })).toHaveAttribute(
      "href",
      "/dashboard/plans",
    );
    expect(
      within(nav).getByRole("link", { name: "Create a Plan" }),
    ).toHaveAttribute("href", "/dashboard/plans/new");
    expect(
      within(nav).getByRole("link", { name: "Team Plans" }),
    ).toHaveAttribute("href", "/dashboard/plans/team");

    // Exactly three destinations and the launcher — nothing leaks in.
    expect(within(nav).getAllByRole("link")).toHaveLength(4);

    for (const hidden of [
      "Approvals",
      "Request Cover",
      "My Account",
      "Audit View",
      "Teams",
    ]) {
      expect(
        within(nav).queryByRole("link", { name: hidden }),
      ).not.toBeInTheDocument();
    }
  });

  it("marks My Plans active on the module index and the emailed detail page", () => {
    for (const path of ["/dashboard/plans", "/dashboard/plans/123"]) {
      currentPath = path;
      const { unmount } = renderShell(mockUser);

      const nav = screen.getByRole("navigation");
      expect(within(nav).getByRole("link", { name: "My Plans" })).toHaveAttribute(
        "aria-current",
        "page",
      );
      expect(
        within(nav).getByRole("link", { name: "Create a Plan" }),
      ).not.toHaveAttribute("aria-current");
      unmount();
    }
  });

  it.each([
    ["/dashboard/plans/new", "Create a Plan"],
    ["/dashboard/plans/team", "Team Plans"],
  ])("marks %s active on its own item", (path, label) => {
    currentPath = path;
    renderShell(mockUser);

    const nav = screen.getByRole("navigation");
    expect(
      within(nav).getByRole("link", { name: label }),
    ).toHaveAttribute("aria-current", "page");
  });
});

describe("DashboardShell Leave Configuration module", () => {
  it("scopes the rail to the launcher plus exactly the three configuration items", () => {
    currentPath = "/leave-config";
    // The strictest visitor again: an HR approver must lose their HR and
    // approvals destinations, not merely the employee-only extras.
    renderShell(mockHRUser, { isApprover: true, pendingApprovals: 4 });

    const nav = screen.getByRole("navigation");
    expect(within(nav).getByRole("link", { name: "All apps" })).toHaveAttribute(
      "href",
      "/",
    );
    expect(within(nav).getByRole("link", { name: "Leave Types" })).toHaveAttribute(
      "href",
      "/leave-config",
    );
    expect(within(nav).getByRole("link", { name: "Annual Days" })).toHaveAttribute(
      "href",
      "/leave-config/annual-days",
    );
    expect(
      within(nav).getByRole("link", { name: "Create Leave Type" }),
    ).toHaveAttribute("href", "/leave-config/new");

    // Exactly three destinations and the launcher — nothing leaks in.
    expect(within(nav).getAllByRole("link")).toHaveLength(4);

    for (const hidden of [
      "Dashboard",
      "My Applications",
      "Drafts",
      "Approvals",
      "Leave Plans",
      "Request Cover",
      "My Account",
      "Audit View",
      "Teams",
    ]) {
      expect(within(nav).queryByRole("link", { name: hidden })).not.toBeInTheDocument();
    }
  });

  it("keeps the full institutional rail outside the module", () => {
    currentPath = "/dashboard";
    renderShell(mockUser);

    const nav = screen.getByRole("navigation");
    expect(within(nav).getByRole("link", { name: "My Account" })).toBeInTheDocument();
    expect(
      within(nav).queryByRole("link", { name: "Leave Types" }),
    ).not.toBeInTheDocument();
    expect(within(nav).queryByRole("link", { name: "All apps" })).not.toBeInTheDocument();
  });

  it.each([
    ["/leave-config"],
    ["/leave-config/7"],
  ])("marks Leave Types active at %s", (path) => {
    currentPath = path;
    renderShell(mockUser);

    const nav = screen.getByRole("navigation");
    expect(within(nav).getByRole("link", { name: "Leave Types" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(
      within(nav).getByRole("link", { name: "Create Leave Type" }),
    ).not.toHaveAttribute("aria-current");
    expect(
      within(nav).getByRole("link", { name: "Annual Days" }),
    ).not.toHaveAttribute("aria-current");
  });

  it.each([
    ["/leave-config/annual-days"],
    ["/leave-config/annual-days/new"],
  ])("marks Annual Days active at %s", (path) => {
    currentPath = path;
    renderShell(mockUser);

    const nav = screen.getByRole("navigation");
    expect(
      within(nav).getByRole("link", { name: "Annual Days" }),
    ).toHaveAttribute("aria-current", "page");
    expect(within(nav).getByRole("link", { name: "Leave Types" })).not.toHaveAttribute(
      "aria-current",
    );
    expect(
      within(nav).getByRole("link", { name: "Create Leave Type" }),
    ).not.toHaveAttribute("aria-current");
  });

  it("marks Create Leave Type active only on the create form", () => {
    currentPath = "/leave-config/new";
    renderShell(mockUser);

    const nav = screen.getByRole("navigation");
    expect(
      within(nav).getByRole("link", { name: "Create Leave Type" }),
    ).toHaveAttribute("aria-current", "page");
    expect(within(nav).getByRole("link", { name: "Leave Types" })).not.toHaveAttribute(
      "aria-current",
    );
    expect(
      within(nav).getByRole("link", { name: "Annual Days" }),
    ).not.toHaveAttribute("aria-current");
  });

  it("does not let an edit path be mistaken for the create form", () => {
    // `/leave-config/new` is static and `/leave-config/[id]` is dynamic, so the
    // router resolves "new" to the form — but the rail decides by string, and
    // a matcher that treated every unknown segment as an id would light the
    // wrong item here.
    currentPath = "/leave-config/42";
    renderShell(mockUser);

    const nav = screen.getByRole("navigation");
    expect(
      within(nav).getByRole("link", { name: "Create Leave Type" }),
    ).not.toHaveAttribute("aria-current", "page");
  });
});

describe("DashboardShell Approvals module", () => {
  it("scopes the rail to the launcher plus the queue and cover destinations", () => {
    currentPath = "/dashboard/approvals";
    // An HR approver is the strictest case: the module rail must hide their HR
    // folio and personal destinations, not merely the employee-only extras.
    renderShell(mockHRUser, { isApprover: true, pendingApprovals: 4 });

    const nav = screen.getByRole("navigation");
    expect(within(nav).getByRole("link", { name: "All apps" })).toHaveAttribute(
      "href",
      "/",
    );
    expect(within(nav).getByRole("link", { name: "Approvals" })).toHaveAttribute(
      "href",
      "/dashboard/approvals",
    );
    expect(
      within(nav).getByRole("link", { name: "Request Cover" }),
    ).toHaveAttribute("href", "/dashboard/cover");

    // Exactly two destinations and the launcher — nothing leaks in.
    expect(within(nav).getAllByRole("link")).toHaveLength(3);

    for (const hidden of [
      "Dashboard",
      "My Applications",
      "Drafts",
      "Leave Plans",
      "Teams",
      "My Account",
      "Audit View",
    ]) {
      expect(within(nav).queryByRole("link", { name: hidden })).not.toBeInTheDocument();
    }
  });

  it("carries the pending count on the queue item", () => {
    currentPath = "/dashboard/approvals";
    renderShell(mockApproverUser, { isApprover: true, pendingApprovals: 4 });

    const nav = screen.getByRole("navigation");
    expect(within(nav).getByTestId("module-nav-badge")).toHaveTextContent("4");
  });

  it("scopes the rail on the cover routes too", () => {
    currentPath = "/dashboard/cover/9";
    renderShell(mockApproverUser, { isApprover: true, pendingApprovals: 4 });

    const nav = screen.getByRole("navigation");
    expect(within(nav).getByRole("link", { name: "All apps" })).toBeInTheDocument();
    expect(
      within(nav).queryByRole("link", { name: "My Account" }),
    ).not.toBeInTheDocument();
  });

  it("marks the queue active on the index and the directory while viewing one", () => {
    currentPath = "/dashboard/approvals/42";
    renderShell(mockApproverUser, { isApprover: true });

    const nav = screen.getByRole("navigation");
    expect(within(nav).getByRole("link", { name: "Approvals" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(
      within(nav).getByRole("link", { name: "Request Cover" }),
    ).not.toHaveAttribute("aria-current");
  });
});

describe("DashboardShell Workflows module", () => {
  it("scopes HR's rail to the launcher plus exactly the four Workflows items", () => {
    currentPath = "/dashboard/teams";
    // The strictest visitor: an HR approver must lose their HR folio and
    // approvals destinations, not merely the employee-only extras.
    renderShell(mockHRUser, { isApprover: true, pendingApprovals: 4 });

    const nav = screen.getByRole("navigation");
    expect(within(nav).getByRole("link", { name: "All apps" })).toHaveAttribute(
      "href",
      "/",
    );
    expect(within(nav).getByRole("link", { name: "Teams" })).toHaveAttribute(
      "href",
      "/dashboard/teams",
    );
    expect(within(nav).getByRole("link", { name: "Campuses" })).toHaveAttribute(
      "href",
      "/dashboard/hr-admin/campuses",
    );
    expect(
      within(nav).getByRole("link", { name: "Approver Roles" }),
    ).toHaveAttribute("href", "/dashboard/hr-admin/roles");
    expect(
      within(nav).getByRole("link", { name: "Role Assignments" }),
    ).toHaveAttribute("href", "/dashboard/hr-admin/approvers");

    // Exactly four destinations and the launcher — nothing leaks in.
    expect(within(nav).getAllByRole("link")).toHaveLength(5);

    for (const hidden of [
      "Dashboard",
      "My Applications",
      "Drafts",
      "Approvals",
      "HR Administration",
      "Audit View",
      "My Account",
    ]) {
      expect(within(nav).queryByRole("link", { name: hidden })).not.toBeInTheDocument();
    }
  });

  it("keeps the module rail while moving between its Teams and HR surfaces", () => {
    // The module is not contiguous: a role assignment page lives under
    // `/dashboard/hr-admin`, but it is still the Workflows module, so the rail
    // must not snap back to the HR folio on the way there.
    currentPath = "/dashboard/hr-admin/roles";
    renderShell(mockHRUser);

    const nav = screen.getByRole("navigation");
    expect(within(nav).getByRole("link", { name: "All apps" })).toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: "Teams" })).toBeInTheDocument();
    expect(within(nav).queryByRole("link", { name: "Employees" })).not.toBeInTheDocument();
  });

  it("offers a team manager only the Teams item, not HR's configuration", () => {
    currentPath = "/dashboard/teams";
    renderShell(mockTeamManagerUser);

    const nav = screen.getByRole("navigation");
    expect(within(nav).getByRole("link", { name: "All apps" })).toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: "Teams" })).toBeInTheDocument();
    // Exactly the launcher and Teams — a manager cannot administer campuses,
    // roles, or institution-wide assignments.
    expect(within(nav).getAllByRole("link")).toHaveLength(2);
    for (const hidden of ["Campuses", "Approver Roles", "Role Assignments"]) {
      expect(within(nav).queryByRole("link", { name: hidden })).not.toBeInTheDocument();
    }
  });

  it("marks the Teams item active on the index and a team's own page", () => {
    for (const path of ["/dashboard/teams", "/dashboard/teams/12"]) {
      currentPath = path;
      const { unmount } = renderShell(mockHRUser);

      const nav = screen.getByRole("navigation");
      expect(within(nav).getByRole("link", { name: "Teams" })).toHaveAttribute(
        "aria-current",
        "page",
      );
      expect(
        within(nav).getByRole("link", { name: "Campuses" }),
      ).not.toHaveAttribute("aria-current");
      unmount();
    }
  });

  it("marks each HR configuration item active on its own page", () => {
    for (const [path, label] of [
      ["/dashboard/hr-admin/campuses", "Campuses"],
      ["/dashboard/hr-admin/roles", "Approver Roles"],
      ["/dashboard/hr-admin/approvers", "Role Assignments"],
    ]) {
      currentPath = path;
      const { unmount } = renderShell(mockHRUser);

      const nav = screen.getByRole("navigation");
      expect(within(nav).getByRole("link", { name: label })).toHaveAttribute(
        "aria-current",
        "page",
      );
      expect(within(nav).getByRole("link", { name: "Teams" })).not.toHaveAttribute(
        "aria-current",
      );
      unmount();
    }
  });

  it("leaves the HR folio intact on its own landing page", () => {
    // `/dashboard/hr-admin` administers everything, so it is deliberately not
    // in the module: HR keeps their full rail until they pick a module page.
    currentPath = "/dashboard/hr-admin";
    renderShell(mockHRUser);

    const nav = screen.getByRole("navigation");
    expect(within(nav).queryByRole("link", { name: "All apps" })).not.toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: "Employees" })).toBeInTheDocument();
  });

  it("gives a team manager a My Team entry in the institutional rail", () => {
    currentPath = "/dashboard";
    renderShell(mockTeamManagerUser);

    expect(screen.getByRole("link", { name: "My Team" })).toHaveAttribute(
      "href",
      "/dashboard/teams",
    );
    // A manager is not HR, so the folio's own "Teams" entry stays hidden.
    expect(screen.queryByRole("link", { name: "Teams" })).not.toBeInTheDocument();
  });

  it("shows HR the Teams entry and not My Team", () => {
    currentPath = "/dashboard";
    renderShell(mockHRUser);

    expect(screen.getByRole("link", { name: "Teams" })).toHaveAttribute(
      "href",
      "/dashboard/teams",
    );
    expect(screen.queryByRole("link", { name: "My Team" })).not.toBeInTheDocument();
  });

  it("gives a superuser the Teams entry and not My Team", () => {
    // The backend admits a superuser to every team; the rail offers the same
    // way in as HR, and their "administrator" reach does not read as a manager.
    currentPath = "/dashboard";
    renderShell(mockAdminUser);

    expect(screen.getByRole("link", { name: "Teams" })).toHaveAttribute(
      "href",
      "/dashboard/teams",
    );
    expect(screen.queryByRole("link", { name: "My Team" })).not.toBeInTheDocument();
  });

  it("offers a superuser the module's HR configuration items", () => {
    currentPath = "/dashboard/teams";
    renderShell(mockAdminUser);

    const nav = screen.getByRole("navigation");
    expect(within(nav).getByRole("link", { name: "Teams" })).toBeInTheDocument();
    for (const label of ["Campuses", "Approver Roles", "Role Assignments"]) {
      expect(within(nav).getByRole("link", { name: label })).toBeInTheDocument();
    }
  });
});

describe("DashboardShell Documents module", () => {
  it("scopes an employee's rail to the launcher plus the three Documents items", () => {
    currentPath = "/dashboard/documents";
    renderShell(mockUser);

    const nav = screen.getByRole("navigation");
    expect(within(nav).getByRole("link", { name: "All apps" })).toHaveAttribute(
      "href",
      "/",
    );
    expect(
      within(nav).getByRole("link", { name: "Supporting Documents" }),
    ).toHaveAttribute("href", "/dashboard/documents/supporting");
    expect(
      within(nav).getByRole("link", { name: "Approved Documents" }),
    ).toHaveAttribute("href", "/dashboard/documents/approved");

    // Exactly three destinations and the launcher — the institutional rail does
    // not leak in behind the module's own.
    expect(within(nav).getAllByRole("link")).toHaveLength(4);
    expect(
      within(nav).queryByRole("link", { name: "My Applications" }),
    ).not.toBeInTheDocument();
  });

  it("marks exactly one item active on the hub and on each list", () => {
    const cases: ReadonlyArray<readonly [string, string]> = [
      ["/dashboard/documents", "Dashboard"],
      ["/dashboard/documents/supporting", "Supporting Documents"],
      ["/dashboard/documents/approved", "Approved Documents"],
    ];
    for (const [path, label] of cases) {
      currentPath = path;
      const { unmount } = renderShell(mockUser);

      const nav = screen.getByRole("navigation");
      expect(within(nav).getByRole("link", { name: label })).toHaveAttribute(
        "aria-current",
        "page",
      );
      const active = within(nav)
        .getAllByRole("link")
        .filter((link) => link.getAttribute("aria-current") === "page");
      expect(active).toHaveLength(1);
      unmount();
    }
  });

  it("keeps the module rail for HR's own visit to the hub", () => {
    // Documents is every account's, HR included: HR gets the module's short
    // rail here rather than their folio, which would promise other pages.
    currentPath = "/dashboard/documents";
    renderShell(mockHRUser, { isApprover: true, pendingApprovals: 3 });

    const nav = screen.getByRole("navigation");
    expect(
      within(nav).getByRole("link", { name: "Supporting Documents" }),
    ).toBeInTheDocument();
    expect(
      within(nav).queryByRole("link", { name: "Role Assignments" }),
    ).not.toBeInTheDocument();
  });
});

describe("DashboardShell Calendar module", () => {
  it("scopes the rail to the launcher plus the Calendar landing item", () => {
    currentPath = "/dashboard/hr-admin/calendar";
    // The strictest visitor: an HR approver must lose their folio, approvals,
    // and every personal destination rather than see them beside the calendar.
    renderShell(mockHRUser, { isApprover: true, pendingApprovals: 4 });

    const nav = screen.getByRole("navigation");
    expect(within(nav).getByRole("link", { name: "All apps" })).toHaveAttribute(
      "href",
      "/",
    );
    expect(within(nav).getByRole("link", { name: "Calendar" })).toHaveAttribute(
      "href",
      "/dashboard/hr-admin/calendar",
    );

    // The launcher and the one entry — nothing else leaks in.
    expect(within(nav).getAllByRole("link")).toHaveLength(2);

    for (const hidden of [
      "Dashboard",
      "My Applications",
      "Approvals",
      "Leave Plans",
      "Request Cover",
      "My Account",
      "Audit View",
      "Teams",
      "Employees",
      "Entitlements",
      "Roles",
    ]) {
      expect(within(nav).queryByRole("link", { name: hidden })).not.toBeInTheDocument();
    }
  });

  it("marks the Calendar item active on the landing page and beneath it", () => {
    for (const path of [
      "/dashboard/hr-admin/calendar",
      "/dashboard/hr-admin/calendar/holidays/new",
    ]) {
      currentPath = path;
      const { unmount } = renderShell(mockAdminUser);

      const nav = screen.getByRole("navigation");
      expect(within(nav).getByRole("link", { name: "Calendar" })).toHaveAttribute(
        "aria-current",
        "page",
      );
      unmount();
    }
  });

  it("leaves the HR folio intact on the HR admin landing page", () => {
    // `/dashboard/hr-admin` administers everything, so it is deliberately not
    // in the module: HR keeps their full rail until they open the Calendar.
    currentPath = "/dashboard/hr-admin";
    renderShell(mockHRUser);

    const nav = screen.getByRole("navigation");
    expect(within(nav).queryByRole("link", { name: "All apps" })).not.toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: "Employees" })).toBeInTheDocument();
  });
});
