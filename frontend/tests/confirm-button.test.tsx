import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ConfirmButton } from "@/components/ui/confirm-button";

/**
 * The confirm step is the whole point of the component, so what is asserted is
 * the ordering rather than an intermediate state: the first click reveals the
 * control, and only the second one runs the write.
 */
describe("ConfirmButton", () => {
  it("does not run the action on the first click", () => {
    const onConfirm = vi.fn();
    render(
      <ConfirmButton onConfirm={onConfirm} prompt="Retire this?">
        Retire
      </ConfirmButton>
    );

    fireEvent.click(screen.getByRole("button", { name: "Retire" }));

    expect(onConfirm).not.toHaveBeenCalled();
    expect(screen.getByText("Retire this?")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Yes, continue" })
    ).toBeInTheDocument();
  });

  it("runs the action on the confirming click", async () => {
    const onConfirm = vi.fn();
    render(
      <ConfirmButton onConfirm={onConfirm} confirmLabel="Yes, retire">
        Retire
      </ConfirmButton>
    );

    fireEvent.click(screen.getByRole("button", { name: "Retire" }));
    fireEvent.click(screen.getByRole("button", { name: "Yes, retire" }));

    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("backs out without running the action", () => {
    const onConfirm = vi.fn();
    render(<ConfirmButton onConfirm={onConfirm}>Retire</ConfirmButton>);

    fireEvent.click(screen.getByRole("button", { name: "Retire" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(onConfirm).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Retire" })).toBeInTheDocument();
  });

  it("does not open the confirm while disabled", () => {
    render(
      <ConfirmButton onConfirm={vi.fn()} disabled>
        Retire
      </ConfirmButton>
    );

    fireEvent.click(screen.getByRole("button", { name: "Retire" }));

    expect(screen.queryByRole("button", { name: "Yes, continue" })).toBeNull();
  });
});
