import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { EmployeeForm } from "@/components/hr/employee-form";
import type { Employee } from "@/lib/employees";

import { openSelect, selectOption, selectedValue } from "./helpers/select";

const HOD_EMPLOYEE: Employee = {
  id: 1,
  user_id: 2,
  email: "hod@test.luanar",
  first_name: "Test",
  last_name: "HOD",
  full_name: "Test HOD",
  role: "hod",
  designation: "Head of Department",
  department: "Bunda College",
  category: "academic",
  grade: "G",
  appointment_date: "2020-01-01",
  is_active: true,
  supervisor: null,
};

/** `roleLabel` is the visible option text, e.g. "Head of Department". */
async function submitPayload(roleLabel: string) {
  fireEvent.change(screen.getByLabelText("First name"), {
    target: { value: "Test" },
  });
  fireEvent.change(screen.getByLabelText("Last name"), {
    target: { value: "Employee" },
  });
  fireEvent.change(screen.getByLabelText("Email"), {
    target: { value: "new.employee@test.luanar" },
  });
  await selectOption(screen.getByLabelText("Role"), roleLabel, { user });
  fireEvent.click(screen.getByRole("button", { name: "Create employee" }));
}

/** Shared so the module-level `submitPayload` can drive the Radix selects. */
let user: ReturnType<typeof userEvent.setup>;

describe("EmployeeForm", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
    user = userEvent.setup();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders a grade input that is both a dropdown and manually editable", () => {
    render(
      <EmployeeForm
        endpoint="/api/hr/employees"
        method="POST"
        gradeOptions={["A", "B", "C", "G"]}
      />
    );

    const gradeInput = screen.getByLabelText("Grade");
    expect(gradeInput).toBeInTheDocument();
    expect(gradeInput).toHaveAttribute("list", "grade-options");

    const datalist = document.getElementById("grade-options");
    expect(datalist).not.toBeNull();
    const options = datalist ? datalist.querySelectorAll("option") : [];
    expect(options.length).toBe(4);

    fireEvent.change(gradeInput, { target: { value: "X" } });
    expect(gradeInput).toHaveValue("X");
  });

  it("keeps manual entry when no configured grades exist", () => {
    render(<EmployeeForm endpoint="/api/hr/employees" method="POST" />);

    const gradeInput = screen.getByLabelText("Grade");
    expect(gradeInput).toBeInTheDocument();
    expect(gradeInput).not.toHaveAttribute("list");
    expect(document.getElementById("grade-options")).toBeNull();

    fireEvent.change(gradeInput, { target: { value: "M" } });
    expect(gradeInput).toHaveValue("M");
  });

  it("renders all seven role options", async () => {
    render(<EmployeeForm endpoint="/api/hr/employees" method="POST" />);

    await openSelect(screen.getByLabelText("Role"));

    const options = screen.getAllByRole("option").map((option) => option.textContent);
    expect(options).toEqual([
      "Employee",
      "Supervisor",
      "Head of Department",
      "Dean",
      "Registrar",
      "Deputy Vice-Chancellor",
      "Human Resources",
    ]);
  });

  it("defaults to Employee on create and to the current role on edit", () => {
    const { unmount } = render(
      <EmployeeForm endpoint="/api/hr/employees" method="POST" />
    );
    expect(selectedValue(screen.getByLabelText("Role"))).toBe("Employee");

    unmount();

    render(
      <EmployeeForm
        employee={HOD_EMPLOYEE}
        endpoint="/api/hr/employees/1"
        method="PATCH"
      />
    );
    expect(selectedValue(screen.getByLabelText("Role"))).toBe("Head of Department");
  });

  it("submits the default Employee role in the payload", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));

    render(<EmployeeForm endpoint="/api/hr/employees" method="POST" />);
    await submitPayload("Employee");

    await waitFor(() => expect(fetch).toHaveBeenCalled());
    const init = vi.mocked(fetch).mock.calls[0][1];
    expect(JSON.parse(String(init?.body)).role).toBe("employee");
  });

  it("submits the selected role instead of the default", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));

    render(<EmployeeForm endpoint="/api/hr/employees" method="POST" />);
    await submitPayload("Head of Department");

    await waitFor(() => expect(fetch).toHaveBeenCalled());
    const init = vi.mocked(fetch).mock.calls[0][1];
    expect(JSON.parse(String(init?.body)).role).toBe("hod");
  });

  it("renders the supervisor options and defaults to none", async () => {
    render(
      <EmployeeForm
        endpoint="/api/hr/employees"
        method="POST"
        supervisorOptions={[
          { id: 2, full_name: "Jane Phiri" },
          { id: 9, full_name: "Peter Banda" },
        ]}
      />
    );

    const supervisor = screen.getByLabelText("Supervisor");
    expect(supervisor).toBeInTheDocument();
    expect(selectedValue(supervisor)).toBe("No assigned supervisor");

    await openSelect(supervisor);

    expect(screen.getByRole("option", { name: "Jane Phiri" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Peter Banda" })).toBeInTheDocument();
  });

  it("preselects the assigned supervisor on edit", () => {
    render(
      <EmployeeForm
        employee={{ ...HOD_EMPLOYEE, supervisor: 9 }}
        endpoint="/api/hr/employees/1"
        method="PATCH"
        supervisorOptions={[
          { id: 2, full_name: "Jane Phiri" },
          { id: 9, full_name: "Peter Banda" },
        ]}
      />
    );

    expect(selectedValue(screen.getByLabelText("Supervisor"))).toBe("Peter Banda");
  });

  it("submits the selected supervisor user id in the payload", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));

    render(
      <EmployeeForm
        endpoint="/api/hr/employees"
        method="POST"
        supervisorOptions={[{ id: 9, full_name: "Peter Banda" }]}
      />
    );
    fireEvent.change(screen.getByLabelText("First name"), {
      target: { value: "Test" },
    });
    fireEvent.change(screen.getByLabelText("Last name"), {
      target: { value: "Employee" },
    });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "new.employee@test.luanar" },
    });
    await selectOption(screen.getByLabelText("Role"), "Employee", { user });
    await selectOption(screen.getByLabelText("Supervisor"), "Peter Banda", { user });
    fireEvent.click(screen.getByRole("button", { name: "Create employee" }));

    await waitFor(() => expect(fetch).toHaveBeenCalled());
    const init = vi.mocked(fetch).mock.calls[0][1];
    expect(JSON.parse(String(init?.body)).supervisor).toBe(9);
  });
});