import { render, screen } from "@testing-library/react";
import { useState } from "react";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";

import { openSelect, selectOption, selectedValue } from "./helpers/select";

/**
 * Contract tests for the Radix `Select` primitive.
 *
 * These also prove the jsdom shims in `tests/setup.ts` are sufficient: a Radix
 * listbox cannot open at all without pointer capture, resize observation and
 * `scrollIntoView`, so every assertion here is also a shim assertion.
 */

function RoleSelect({ onChange }: { onChange?: (value: string) => void }) {
  const [role, setRole] = useState("");

  return (
    <div>
      <Label htmlFor="role">Role</Label>
      <Select
        value={role}
        onValueChange={(next) => {
          setRole(next);
          onChange?.(next);
        }}
      >
        <SelectTrigger id="role" aria-label="Role">
          <SelectValue placeholder="Select a role" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="employee">Employee</SelectItem>
          <SelectItem value="supervisor">Supervisor</SelectItem>
          <SelectItem value="hod">Head of Department</SelectItem>
        </SelectContent>
      </Select>
    </div>
  );
}

describe("Select", () => {
  it("is closed until the trigger is activated", () => {
    render(<RoleSelect />);

    expect(screen.getByRole("combobox", { name: "Role" })).toBeInTheDocument();
    expect(screen.queryByRole("option")).not.toBeInTheDocument();
  });

  it("shows the placeholder until something is selected", () => {
    render(<RoleSelect />);

    expect(screen.getByRole("combobox", { name: "Role" })).toHaveTextContent(
      "Select a role"
    );
  });

  it("opens and lists every option", async () => {
    render(<RoleSelect />);

    await openSelect(screen.getByRole("combobox", { name: "Role" }));

    expect(await screen.findByRole("option", { name: "Employee" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Supervisor" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Head of Department" })).toBeInTheDocument();
  });

  it("puts the chosen value on the trigger and reports it", async () => {
    const onChange = vi.fn();
    render(<RoleSelect onChange={onChange} />);

    const trigger = screen.getByRole("combobox", { name: "Role" });
    await selectOption(trigger, "Head of Department");

    expect(onChange).toHaveBeenCalledWith("hod");
    expect(selectedValue(trigger)).toBe("Head of Department");
  });

  it("exposes the value to a label and keeps a stable accessible name", () => {
    render(<RoleSelect />);

    const trigger = screen.getByLabelText("Role");
    expect(trigger).toBe(screen.getByRole("combobox", { name: "Role" }));
  });

  it("marks the selected option for assistive technology", async () => {
    render(<RoleSelect />);

    const trigger = screen.getByRole("combobox", { name: "Role" });
    await selectOption(trigger, "Employee");

    await openSelect(trigger);
    const selected = await screen.findByRole("option", { selected: true });

    expect(selected).toHaveTextContent("Employee");
  });

  it("can be marked invalid for form validation", () => {
    render(
      <Select defaultValue="">
        <SelectTrigger aria-label="Role" aria-invalid="true">
          <SelectValue placeholder="Select a role" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="employee">Employee</SelectItem>
        </SelectContent>
      </Select>
    );

    expect(screen.getByRole("combobox", { name: "Role" })).toHaveAttribute(
      "aria-invalid",
      "true"
    );
  });
});
