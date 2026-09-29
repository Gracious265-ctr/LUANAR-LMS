import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { EmployeeForm } from "@/components/hr/employee-form";
import type { Employee } from "@/lib/employees";

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

function submitPayload(role: string) {
  fireEvent.change(screen.getByLabelText("First name"), {
    target: { value: "Test" },
  });
  fireEvent.change(screen.getByLabelText("Last name"), {
    target: { value: "Employee" },
  });
  fireEvent.change(screen.getByLabelText("Email"), {
    target: { value: "new.employee@test.luanar" },
  });
  fireEvent.change(screen.getByLabelText("Role"), { target: { value: role } });
  fireEvent.click(screen.getByRole("button", { name: "Create employee" }));
}

describe("EmployeeForm", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
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

  it("renders all seven role options", () => {
    render(<EmployeeForm endpoint="/api/hr/employees" method="POST" />);

    const roleSelect = screen.getByLabelText("Role") as HTMLSelectElement;
    const options = Array.from(roleSelect.options).map((option) => ({
      value: option.value,
      label: option.textContent,
    }));
    expect(options).toEqual([
      { value: "employee", label: "Employee" },
      { value: "supervisor", label: "Supervisor" },
      { value: "hod", label: "Head of Department" },
      { value: "dean", label: "Dean" },
      { value: "registrar", label: "Registrar" },
      { value: "dvc", label: "Deputy Vice-Chancellor" },
      { value: "hr", label: "Human Resources" },
    ]);
  });

  it("defaults to Employee on create and to the current role on edit", () => {
    const { unmount } = render(
      <EmployeeForm endpoint="/api/hr/employees" method="POST" />
    );
    expect(screen.getByLabelText("Role")).toHaveValue("employee");

    unmount();

    render(
      <EmployeeForm
        employee={HOD_EMPLOYEE}
        endpoint="/api/hr/employees/1"
        method="PATCH"
      />
    );
    expect(screen.getByLabelText("Role")).toHaveValue("hod");
  });

  it("submits the default Employee role in the payload", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));

    render(<EmployeeForm endpoint="/api/hr/employees" method="POST" />);
    submitPayload("employee");

    await waitFor(() => expect(fetch).toHaveBeenCalled());
    const init = vi.mocked(fetch).mock.calls[0][1];
    expect(JSON.parse(String(init?.body)).role).toBe("employee");
  });

  it("submits the selected role instead of the default", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));

    render(<EmployeeForm endpoint="/api/hr/employees" method="POST" />);
    submitPayload("hod");

    await waitFor(() => expect(fetch).toHaveBeenCalled());
    const init = vi.mocked(fetch).mock.calls[0][1];
    expect(JSON.parse(String(init?.body)).role).toBe("hod");
  });

  it("renders the supervisor options and defaults to none", () => {
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
    expect(supervisor).toHaveValue("");
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

    expect(screen.getByLabelText("Supervisor")).toHaveValue("9");
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
    fireEvent.change(screen.getByLabelText("Role"), {
      target: { value: "employee" },
    });
    fireEvent.change(screen.getByLabelText("Supervisor"), {
      target: { value: "9" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create employee" }));

    await waitFor(() => expect(fetch).toHaveBeenCalled());
    const init = vi.mocked(fetch).mock.calls[0][1];
    expect(JSON.parse(String(init?.body)).supervisor).toBe(9);
  });
});