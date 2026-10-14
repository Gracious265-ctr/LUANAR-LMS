import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";

function renderDialog(props: Partial<React.ComponentProps<typeof DialogContent>> = {}) {
  render(
    <Dialog open>
      <DialogContent {...props}>
        <DialogTitle>t</DialogTitle>
        <DialogDescription>d</DialogDescription>
        <p>body</p>
      </DialogContent>
    </Dialog>
  );
  const outer = screen.getByRole("dialog");
  const scroller = outer.querySelector('[data-slot="dialog-scroll"]');
  return { outer, scroller };
}

describe("DialogContent scrollable clipping", () => {
  it("splits the radius from the scroll so the scrollbar corners stay round", () => {
    const { outer, scroller } = renderDialog({ scrollable: true });

    // The outer owns the radius and the clipping.
    expect(outer.className).toContain("rounded-xl");
    expect(outer.className).toContain("overflow-hidden");
    expect(outer.className).toContain("max-h-[calc(100vh-4rem)]");

    // The outer must never be the scroller, or the track squares off the corners.
    expect(outer.className).not.toContain("overflow-y-auto");

    // The child scrolls and deliberately carries no radius of its own.
    expect(scroller).not.toBeNull();
    expect(scroller?.className).toContain("overflow-y-auto");
    expect(scroller?.className).not.toMatch(/rounded/);
  });

  it("lets the scroller shrink so it actually scrolls instead of overflowing", () => {
    // A flex item defaults to min-height: auto, which would refuse to shrink
    // below its content and push past the viewport rather than scroll.
    const { scroller } = renderDialog({ scrollable: true });
    expect(scroller?.className).toContain("min-h-0");
    expect(scroller?.className).toContain("flex-1");
  });

  it("keeps the close button outside the scroller so it stays pinned", () => {
    const { scroller } = renderDialog({ scrollable: true });
    expect(scroller?.querySelector('[data-slot="dialog-close"]')).toBeNull();
    expect(screen.getByRole("dialog").querySelector('[data-slot="dialog-close"]')).not.toBeNull();
  });

  it("routes scrollClassName to the content grid, not the outer", () => {
    // Callers that space their children with explicit margins pass gap-0 so the
    // content grid does not add another 1rem between blocks.
    const { outer, scroller } = renderDialog({ scrollable: true, scrollClassName: "gap-0" });
    expect(scroller?.className).toContain("gap-0");
    expect(outer.className).not.toContain("gap-0");
  });

  it("keeps default spacing for callers that do not override it", () => {
    const { scroller } = renderDialog({ scrollable: true });
    expect(scroller?.className).toContain("gap-4");
  });

  it("leaves non-scrollable dialogs on the original padded grid", () => {
    const { outer, scroller } = renderDialog();

    expect(scroller).toBeNull();
    expect(outer.className).toContain("p-6");
    expect(outer.className).toContain("gap-4");
    expect(outer.className).toContain("rounded-xl");
    expect(outer.className).not.toContain("overflow-hidden");
  });

  it("keeps caller width classes on the outer surface", () => {
    const { outer } = renderDialog({ scrollable: true, className: "max-w-4xl" });
    expect(outer.className).toContain("max-w-4xl");
  });

  it("still honours onOpenChange plumbing", () => {
    const onOpenChange = vi.fn();
    render(
      <Dialog open onOpenChange={onOpenChange}>
        <DialogContent scrollable onEscapeKeyDown={onOpenChange}>
          <DialogTitle>t</DialogTitle>
          <DialogDescription>d</DialogDescription>
        </DialogContent>
      </Dialog>
    );
    expect(screen.getByRole("dialog")).toBeTruthy();
  });
});