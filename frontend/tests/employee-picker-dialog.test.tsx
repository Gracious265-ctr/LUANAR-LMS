import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { EmployeePickerDialog } from "@/components/hr/employee-picker-dialog";

const employees = [
  {
    id: 31,
    full_name: "Ruth Member",
    email: "ruth@test.luanar",
    designation: "Lecturer",
  },
  {
    id: 32,
    full_name: "Sam Candidate",
    email: "sam@test.luanar",
    designation: "Assistant",
  },
  {
    id: 33,
    full_name: "Tina Officer",
    email: "tina@test.luanar",
    designation: "Registrar",
  },
];

function renderPicker(overrides: { onConfirm?: (ids: number[]) => void } = {}) {
  const onConfirm = overrides.onConfirm ?? vi.fn();
  const onOpenChange = vi.fn();
  render(
    <EmployeePickerDialog
      open
      onOpenChange={onOpenChange}
      title="Add employees"
      description="Pick people."
      employees={employees}
      onConfirm={onConfirm}
      confirmLabel={(count) =>
        count === 0
          ? "Add employees"
          : `Add ${count} employee${count === 1 ? "" : "s"}`
      }
    />
  );
  return { onConfirm, onOpenChange };
}

describe("EmployeePickerDialog", () => {
  it("holds several choices until the caller confirms them", () => {
    const { onConfirm } = renderPicker();
    const dialog = screen.getByRole("dialog");

    expect(
      within(dialog).getByRole("button", { name: "Add employees" })
    ).toBeDisabled();

    fireEvent.click(
      within(dialog).getByRole("checkbox", { name: "Ruth Member" })
    );
    fireEvent.click(
      within(dialog).getByRole("checkbox", { name: "Sam Candidate" })
    );
    expect(
      within(dialog).getByRole("button", { name: "Add 2 employees" })
    ).toBeEnabled();
    expect(onConfirm).not.toHaveBeenCalled();

    fireEvent.click(
      within(dialog).getByRole("button", { name: "Add 2 employees" })
    );
    expect(onConfirm).toHaveBeenCalledWith([31, 32]);
  });

  it("narrows the local pool and selects everything still shown", () => {
    const { onConfirm } = renderPicker();
    const dialog = screen.getByRole("dialog");

    fireEvent.change(
      within(dialog).getByRole("searchbox", {
        name: "Search employees to add",
      }),
      { target: { value: "reg" } }
    );
    expect(within(dialog).queryByText("Ruth Member")).not.toBeInTheDocument();
    expect(within(dialog).getByText("Tina Officer")).toBeInTheDocument();

    fireEvent.click(
      within(dialog).getByRole("checkbox", { name: "Select all shown" })
    );
    fireEvent.click(
      within(dialog).getByRole("button", { name: "Add 1 employee" })
    );
    expect(onConfirm).toHaveBeenCalledWith([33]);
  });

  it("keeps a selection made before the search when more are picked", () => {
    const { onConfirm } = renderPicker();
    const dialog = screen.getByRole("dialog");

    fireEvent.click(
      within(dialog).getByRole("checkbox", { name: "Ruth Member" })
    );
    fireEvent.change(
      within(dialog).getByRole("searchbox", {
        name: "Search employees to add",
      }),
      { target: { value: "sam" } }
    );
    fireEvent.click(
      within(dialog).getByRole("checkbox", { name: "Sam Candidate" })
    );
    fireEvent.click(
      within(dialog).getByRole("button", { name: "Add 2 employees" })
    );
    expect(onConfirm).toHaveBeenCalledWith([31, 32]);
  });
});
