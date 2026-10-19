import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ModuleShell, type NavItem } from "@/components/module-shell";

/** The route the mocked `usePathname` reports; tests move it to assert the
 *  active link and that a navigation closes the drawer. */
let currentPath = "/leave";

vi.mock("next/navigation", async (importOriginal) => {
  const actual = await importOriginal<typeof import("next/navigation")>();
  return {
    ...actual,
    usePathname: () => currentPath,
  };
});

const navItems: NavItem[] = [
  { href: "/leave", label: "My Leave" },
  { href: "/leave/drafts", label: "Drafts" },
];

function renderShell() {
  return render(
    <ModuleShell navItems={navItems} moduleName="Leave">
      <p>page body</p>
    </ModuleShell>
  );
}

/** The global `matchMedia` mock exposes `setNarrow`, mirroring the dashboard
 *  shell tests, so the drawer can be opted into explicitly. */
function setNarrowViewport(narrow: boolean) {
  (window.matchMedia as unknown as { setNarrow: (v: boolean) => void }).setNarrow(
    narrow
  );
}

beforeEach(() => {
  currentPath = "/leave";
});

afterEach(() => {
  setNarrowViewport(false);
});

describe("ModuleShell", () => {
  it("renders the module name in the header and every nav item as a link", () => {
    renderShell();

    expect(
      screen.getByRole("heading", { level: 1, name: "Leave" })
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "My Leave" })).toHaveAttribute(
      "href",
      "/leave"
    );
    expect(screen.getByRole("link", { name: "Drafts" })).toHaveAttribute(
      "href",
      "/leave/drafts"
    );
  });

  it("marks only the current route as the active page", () => {
    currentPath = "/leave/drafts";
    renderShell();

    expect(screen.getByRole("link", { name: "Drafts" })).toHaveAttribute(
      "aria-current",
      "page"
    );
    expect(
      screen.getByRole("link", { name: "My Leave" })
    ).not.toHaveAttribute("aria-current");
  });

  it("offers a way back to the app launcher", () => {
    renderShell();

    expect(screen.getByRole("link", { name: /all apps/i })).toHaveAttribute(
      "href",
      "/"
    );
  });

  it("hides the rail on a phone and puts the nav in a menu-triggered drawer", () => {
    setNarrowViewport(true);
    renderShell();

    // The rail's wrapper carries the responsive visibility, so the nav itself
    // can stay a plain `md:block` column.
    const rail = screen.getByRole("navigation", { hidden: true });
    expect(rail.parentElement).toHaveClass("md:hidden");

    const trigger = screen.getByRole("button", { name: "Open navigation" });
    expect(trigger).toHaveAttribute("aria-controls", "module-nav");
    expect(trigger).toHaveAttribute("aria-expanded", "false");

    fireEvent.click(trigger);

    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveAttribute("id", "module-nav");
    expect(within(dialog).getByRole("link", { name: "Drafts" })).toHaveAttribute(
      "href",
      "/leave/drafts"
    );
  });
});
