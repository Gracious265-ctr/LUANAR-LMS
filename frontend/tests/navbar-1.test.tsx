import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { Navbar1 } from "@/components/ui/navbar-1";

const navigation = vi.hoisted(() => ({ pathname: "/" }));

vi.mock("next/navigation", () => ({
  usePathname: () => navigation.pathname,
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}));

vi.mock("next/link", () => ({
  default: ({
    href,
    ...props
  }: React.ComponentProps<"a"> & { href: string }) => (
    <a href={href} {...props} />
  ),
}));

vi.mock("@/components/theme-toggle", () => ({
  ThemeToggle: () => (
    <button type="button" aria-label="Switch theme">
      Theme
    </button>
  ),
}));

vi.mock("@/components/notifications/NotificationBell", () => ({
  NotificationBell: () => (
    <button type="button" aria-label="Notifications">
      Notifications
    </button>
  ),
}));

beforeEach(() => {
  navigation.pathname = "/";
});

describe("Navbar1 shared app header", () => {
  it("shows notifications on the launcher", () => {
    render(
      <Navbar1
        user={{
          id: 5,
          email: "staff@example.test",
          role: "employee",
          full_name: "Test Staff Member",
        }}
      />
    );

    expect(
      screen.getByRole("button", { name: "Notifications" })
    ).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "All Apps" })).not.toBeInTheDocument();
  });

  it("shows profile details and opens a dismissible password-change dialog", () => {
    navigation.pathname = "/dashboard";
    render(
      <Navbar1
        user={{
          id: 5,
          email: "staff@example.test",
          role: "employee",
          full_name: "Test Staff Member",
        }}
        showWelcome
      />
    );

    fireEvent.click(
      screen.getByRole("button", { name: "Open profile for Test Staff Member" })
    );
    expect(screen.getByText("staff@example.test")).toBeInTheDocument();
    expect(screen.getAllByText("Employee").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "Change password" }));
    const dialog = screen.getByRole("dialog", {
      name: "Change your password",
    });
    expect(within(dialog).getByLabelText("Current password")).toBeInTheDocument();
    expect(within(dialog).getByLabelText("New password")).toBeInTheDocument();
    expect(
      within(dialog).getByLabelText("Confirm new password")
    ).toBeInTheDocument();

    fireEvent.click(within(dialog).getByRole("button", { name: "Close" }));
    expect(
      screen.queryByRole("dialog", { name: "Change your password" })
    ).not.toBeInTheDocument();
    navigation.pathname = "/";
  });

  it("uses the avatar to open real app and account actions on mobile", () => {
    const onLogout = vi.fn();

    render(
      <Navbar1
        user={{
          id: 5,
          email: "staff@example.test",
          role: "employee",
          full_name: "Test Staff Member",
        }}
        onLogout={onLogout}
        showAllApps
      />
    );

    expect(screen.queryByRole("link", { name: "All Apps" })).not.toBeInTheDocument();
    const accountButton = screen.getByRole("button", {
      name: "Open account menu",
    });
    expect(within(accountButton).getByText("TS")).toBeInTheDocument();
    fireEvent.click(accountButton);

    const dialog = screen.getByRole("dialog", { name: "Account" });
    expect(within(dialog).getByText("Test Staff Member")).toBeInTheDocument();
    expect(within(dialog).getByText("staff@example.test")).toBeInTheDocument();
    expect(within(dialog).queryByRole("link", { name: "All Apps" })).not.toBeInTheDocument();

    fireEvent.click(
      within(dialog).getByRole("button", { name: "Change password" })
    );
    expect(
      screen.getByRole("dialog", { name: "Change your password" })
    ).toBeInTheDocument();

    const passwordDialog = screen.getByRole("dialog", {
      name: "Change your password",
    });
    fireEvent.click(within(passwordDialog).getByRole("button", { name: "Close" }));
    expect(
      screen.queryByRole("dialog", { name: "Account" })
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Open account menu" }));
    fireEvent.click(
      within(screen.getByRole("dialog", { name: "Account" })).getByRole(
        "button",
        { name: "Sign out" }
      )
    );
    expect(onLogout).toHaveBeenCalledOnce();
  });

  it("shows All Apps and the existing drawer action on the dashboard", () => {
    navigation.pathname = "/dashboard";
    const onOpenNav = vi.fn();
    const { unmount } = render(
      <Navbar1
        user={{
          id: 5,
          email: "staff@example.test",
          role: "employee",
          full_name: "Test Staff Member",
        }}
        showAllApps
        showNavToggle
        onOpenNav={onOpenNav}
      />
    );

    expect(screen.getByRole("link", { name: "All Apps" })).toHaveAttribute(
      "href",
      "/"
    );
    fireEvent.click(screen.getByRole("button", { name: "Open navigation" }));
    expect(onOpenNav).toHaveBeenCalledOnce();
    unmount();
    navigation.pathname = "/";
  });
});
