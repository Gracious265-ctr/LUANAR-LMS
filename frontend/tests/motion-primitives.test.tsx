import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FadeIn } from "@/components/motion/FadeIn";
import { Stagger } from "@/components/motion/Stagger";
import { StaggerItem } from "@/components/motion/StaggerItem";

function Probe({ __staggerIndex }: { __staggerIndex?: number }) {
  return <span data-testid="probe">{__staggerIndex ?? "none"}</span>;
}

function children(count: number) {
  return Array.from({ length: count }, (_, i) => <Probe key={i} />);
}

function indices() {
  return screen.getAllByTestId("probe").map((node) => node.textContent);
}

describe("FadeIn", () => {
  it("renders its children", () => {
    render(
      <FadeIn>
        <p>content</p>
      </FadeIn>
    );
    expect(screen.getByText("content")).toBeDefined();
  });
});

describe("Stagger", () => {
  it("injects sequential indices at the cap of ten children", () => {
    render(<Stagger>{children(10)}</Stagger>);
    expect(indices()).toEqual(["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]);
  });

  it("skips staggering past ten children instead of clamping", () => {
    render(<Stagger>{children(11)}</Stagger>);
    expect(indices()).toEqual(Array(11).fill("none"));
  });

  it("staggers a short list", () => {
    render(<Stagger>{children(3)}</Stagger>);
    expect(indices()).toEqual(["0", "1", "2"]);
  });

  it("leaves a single child unstaggered rather than treating it as a list", () => {
    render(<Stagger>{children(1)}</Stagger>);
    expect(indices()).toEqual(["0"]);
  });
});

describe("StaggerItem", () => {
  it("renders its children with and without an injected index", () => {
    render(
      <>
        <StaggerItem>
          <p>first</p>
        </StaggerItem>
        <StaggerItem __staggerIndex={4}>
          <p>last</p>
        </StaggerItem>
      </>
    );
    expect(screen.getByText("first")).toBeDefined();
    expect(screen.getByText("last")).toBeDefined();
  });
});