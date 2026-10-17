import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BalanceRing } from "@/components/ui/BalanceRing";

describe("BalanceRing", () => {
  it("shows remaining days and the used/total caption", () => {
    render(<BalanceRing label="Annual Leave" used={9} total={21} />);

    expect(
      screen.getByRole("img", { name: "Annual Leave: 9 of 21 days used" })
    ).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("9 of 21 days used")).toBeInTheDocument();
    expect(screen.getByText("Annual Leave")).toBeInTheDocument();
  });

  it("handles a zero entitlement without dividing by zero", () => {
    render(<BalanceRing label="Study Leave" used={0} total={0} />);

    expect(
      screen.getByRole("img", { name: "Study Leave: 0 of 0 days used" })
    ).toBeInTheDocument();
    expect(screen.getByText("0 of 0 days used")).toBeInTheDocument();
  });

  it("never reports a negative remaining balance when over-used", () => {
    render(<BalanceRing label="Sick Leave" used={12} total={10} />);

    expect(screen.getByText("0")).toBeInTheDocument();
  });
});
