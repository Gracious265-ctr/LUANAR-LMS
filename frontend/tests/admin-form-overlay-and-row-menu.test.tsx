import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AdminFormOverlay } from "@/components/hr/AdminFormOverlay";
import { RowActionsMenu } from "@/components/hr/RowActionsMenu";

function SeededForm({ label }: { label: string }) {
  return <input aria-label="Seed" defaultValue={label} />;
}

describe("AdminFormOverlay sizing", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("stays narrow by default, because a short form in a wide dialog reads as unfinished", () => {
    render(
      <AdminFormOverlay
        open
        title="New entitlement"
        description="d"
        onOpenChange={vi.fn()}
      >
        <SeededForm label="a" />
      </AdminFormOverlay>
    );

    const dialog = screen.getByRole("dialog");
    // max-w-lg is DialogContent's own default; the overlay adds nothing.
    expect(dialog.className).not.toContain("max-w-2xl");
    expect(dialog.className).not.toContain("max-w-4xl");
  });

  it("widens and scrolls for md and lg", () => {
    const { unmount } = render(
      <AdminFormOverlay
        open
        size="md"
        title="t"
        description="d"
        onOpenChange={vi.fn()}
      >
        <SeededForm label="a" />
      </AdminFormOverlay>
    );
    expect(screen.getByRole("dialog").className).toContain("max-w-2xl");
    expect(screen.getByRole("dialog").className).toContain("overflow-y-auto");
    unmount();

    render(
      <AdminFormOverlay
        open
        size="lg"
        title="t"
        description="d"
        onOpenChange={vi.fn()}
      >
        <SeededForm label="a" />
      </AdminFormOverlay>
    );
    expect(screen.getByRole("dialog").className).toContain("max-w-4xl");
  });
});

describe("AdminFormOverlay remount key", () => {
  it("discards the previous record's form state when targetKey changes", () => {
    // The forms seed with `defaultValue`, so switching edit targets without a
    // remount would leave the old record's values on screen. Entitlement rows
    // are the sharp case: two bands can read alike while differing in days.
    const { rerender } = render(
      <AdminFormOverlay
        open
        targetKey="3"
        title="Edit G–H"
        description="d"
        onOpenChange={vi.fn()}
      >
        <SeededForm label="21" />
      </AdminFormOverlay>
    );
    expect(screen.getByLabelText("Seed")).toHaveValue("21");

    rerender(
      <AdminFormOverlay
        open
        targetKey="4"
        title="Edit E–F"
        description="d"
        onOpenChange={vi.fn()}
      >
        <SeededForm label="30" />
      </AdminFormOverlay>
    );
    expect(screen.getByLabelText("Seed")).toHaveValue("30");
  });

  it("remounts on identical titles when targetKey differs", () => {
    // The reason `targetKey` exists: the title alone is not a unique identity.
    const { rerender } = render(
      <AdminFormOverlay
        open
        targetKey="3"
        title="Edit rule"
        description="d"
        onOpenChange={vi.fn()}
      >
        <SeededForm label="first" />
      </AdminFormOverlay>
    );
    expect(screen.getByLabelText("Seed")).toHaveValue("first");

    rerender(
      <AdminFormOverlay
        open
        targetKey="4"
        title="Edit rule"
        description="d"
        onOpenChange={vi.fn()}
      >
        <SeededForm label="second" />
      </AdminFormOverlay>
    );
    expect(screen.getByLabelText("Seed")).toHaveValue("second");
  });
});

describe("RowActionsMenu", () => {
  it("renders nothing when there are no actions", () => {
    const { container } = render(
      <RowActionsMenu label="Actions for Annual leave" actions={[]} />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("names the record on the trigger, so rows are distinguishable", () => {
    render(
      <RowActionsMenu
        label="Actions for Annual leave"
        actions={[{ id: "edit", label: "Edit", onSelect: vi.fn() }]}
      />
    );

    expect(
      screen.getByRole("button", { name: "Actions for Annual leave" })
    ).toBeInTheDocument();
  });

  it("opens and runs the chosen action", async () => {
    // Radix opens a menu on `pointerdown`, so a bare `.click()` never opens it.
    // `userEvent` dispatches the real pointer sequence.
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(
      <RowActionsMenu
        label="Actions for Annual leave"
        actions={[{ id: "edit", label: "Edit", onSelect }]}
      />
    );

    await user.click(screen.getByRole("button", { name: /Actions for/ }));
    const item = await screen.findByRole("menuitem", { name: "Edit" });
    await user.click(item);

    expect(onSelect).toHaveBeenCalledTimes(1);
    // Selecting a menu item closes the menu, so it cannot linger over the row.
    await waitFor(() =>
      expect(screen.queryByRole("menu")).not.toBeInTheDocument()
    );
  });

  it("separates a destructive action from the ordinary ones", async () => {
    const user = userEvent.setup();
    render(
      <RowActionsMenu
        label="Actions for Annual leave"
        heading="Annual leave"
        actions={[
          { id: "edit", label: "Edit", onSelect: vi.fn() },
          { id: "del", label: "Deactivate", destructive: true, onSelect: vi.fn() },
        ]}
      />
    );

    await user.click(screen.getByRole("button", { name: /Actions for/ }));

    expect(await screen.findByText("Annual leave")).toBeInTheDocument();
    expect(screen.getByRole("separator")).toBeInTheDocument();
  });
});