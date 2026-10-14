import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BalanceRing } from "@/components/ui/BalanceRing";

function circles(container: HTMLElement): SVGCircleElement[] {
  return Array.from(container.querySelectorAll("circle"));
}

describe("BalanceRing", () => {
  it("names the remaining days against the total for assistive tech", () => {
    render(<BalanceRing used={9} total={21} label="Annual leave" />);

    expect(
      screen.getByRole("img", { name: "Annual leave: 12 of 21 days remaining" })
    ).toBeInTheDocument();
  });

  it("shows the numeric figure beside the dial, not instead of it", () => {
    render(<BalanceRing used={9} total={21} />);

    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText(/of 21 days/)).toBeInTheDocument();
  });

  it("draws a partial arc for a partly-used balance", () => {
    const { container } = render(<BalanceRing used={9} total={21} />);

    const [, filled] = circles(container);
    const circumference = Number(filled.getAttribute("stroke-dasharray"));
    const offset = Number(filled.getAttribute("stroke-dashoffset"));

    expect(circumference).toBeGreaterThan(0);
    expect(offset).toBeGreaterThan(0);
    expect(offset).toBeLessThan(circumference);
  });

  it("clamps consumed days to the full entitlement", () => {
    const { container } = render(<BalanceRing used={30} total={21} />);

    const [, filled] = circles(container);
    const circumference = Number(filled.getAttribute("stroke-dasharray"));

    expect(
      screen.getByRole("img", { name: "0 of 21 days remaining" })
    ).toBeInTheDocument();
    // A full ring consumes the whole circumference: no arc is drawn.
    expect(Number(filled.getAttribute("stroke-dashoffset"))).toBeCloseTo(
      circumference
    );
  });

  it("treats a negative consumed value as none used", () => {
    render(<BalanceRing used={-5} total={21} />);

    expect(
      screen.getByRole("img", { name: "21 of 21 days remaining" })
    ).toBeInTheDocument();
  });

  it("never emits NaN geometry when no entitlement is configured", () => {
    const { container } = render(<BalanceRing used={0} total={0} />);

    const [, filled] = circles(container);
    expect(Number.isFinite(Number(filled.getAttribute("stroke-dashoffset")))).toBe(
      true
    );
    expect(
      screen.getByRole("img", { name: "0 of 0 days remaining" })
    ).toBeInTheDocument();
  });
});
