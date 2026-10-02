import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { EmployeeForm } from "@/components/hr/employee-form";
import type { Department } from "@/lib/departments";
import { makeEmployee } from "@/lib/employees/__fixtures__";

const DEPARTMENTS: Department[] = [
  {
    id: 1,
    name: "Bunda College",
    is_active: true,
    team_count: 0,
    employee_count: 2,
    teams: [],
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
  {
    id: 2,
    name: "Administration",
    is_active: true,
    team_count: 0,
    employee_count: 1,
    teams: [],
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

const HOD_EMPLOYEE = makeEmployee({
  id: 1,
  user_id: 2,
  email: "hod@test.luanar",
  first_name: "Test",
  last_name: "HOD",
  full_name: "Test HOD",
  role: "approver",
  approver_roles: ["hod"],
  designation: "Head of Department",
  department: 1,
  department_name: "Bunda College",
  team: 4,
});

function submitPayload(password = "initial-pass-123") {
  fireEvent.change(screen.getByLabelText("First name"), {
    target: { value: "Test" },
  });
  fireEvent.change(screen.getByLabelText("Last name"), {
    target: { value: "Employee" },
  });
  fireEvent.change(screen.getByLabelText("Email"), {
    target: { value: "new.employee@test.luanar" },
  });
  fireEvent.change(screen.getByLabelText("Password"), {
    target: { value: password },
  });
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

  it("shows the role as read-only, not something HR can choose", () => {
    render(<EmployeeForm endpoint="/api/hr/employees" method="POST" />);

    const role = screen.getByLabelText("Role");
    expect(role).toHaveAttribute("readonly");
    expect(role).toHaveValue("Employee");
    // Approver positions are held on a team or granted institution-wide, so
    // they are not chosen here.
    expect(screen.queryByRole("combobox", { name: "Role" })).toBeNull();
  });

  it("does not offer a team picker, since teams are filled from the team side", () => {
    render(
      <EmployeeForm
        endpoint="/api/hr/employees"
        method="POST"
        departments={DEPARTMENTS}
      />
    );

    expect(screen.queryByLabelText("Team")).toBeNull();
  });

  it("offers the departments it was given and defaults to none", () => {
    render(
      <EmployeeForm
        endpoint="/api/hr/employees"
        method="POST"
        departments={DEPARTMENTS}
      />
    );

    const departmentSelect = screen.getByLabelText(
      "Department"
    ) as HTMLSelectElement;
    expect(departmentSelect).toHaveValue("");
    expect(
      Array.from(departmentSelect.options).map((option) => option.textContent)
    ).toEqual(["No department", "Bunda College", "Administration"]);
  });

  it("submits the chosen department as an id, and null when the employee has none", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));
    const { unmount } = render(
      <EmployeeForm
        endpoint="/api/hr/employees"
        method="POST"
        departments={DEPARTMENTS}
      />
    );
    fireEvent.change(screen.getByLabelText("Department"), {
      target: { value: "2" },
    });
    submitPayload();

    await waitFor(() => expect(fetch).toHaveBeenCalled());
    expect(
      JSON.parse(String(vi.mocked(fetch).mock.calls[0][1]?.body)).department
    ).toBe(2);
    unmount();

    vi.mocked(fetch).mockClear();
    render(
      <EmployeeForm
        endpoint="/api/hr/employees"
        method="POST"
        departments={DEPARTMENTS}
      />
    );
    submitPayload();

    await waitFor(() => expect(fetch).toHaveBeenCalled());
    expect(
      JSON.parse(String(vi.mocked(fetch).mock.calls[0][1]?.body)).department
    ).toBeNull();
  });

  it("prefills the employee's own department on edit", () => {
    render(
      <EmployeeForm
        employee={HOD_EMPLOYEE}
        endpoint="/api/hr/employees/1"
        method="PATCH"
        departments={DEPARTMENTS}
      />
    );

    expect(screen.getByLabelText("Department")).toHaveValue("1");
  });

  it("disables the department picker and explains why when departments could not load", () => {
    render(
      <EmployeeForm
        endpoint="/api/hr/employees"
        method="POST"
        departmentsError="Departments could not be loaded, so this employee cannot be placed in one."
      />
    );

    expect(screen.getByLabelText("Department")).toBeDisabled();
    expect(
      screen.getByText(
        "Departments could not be loaded, so this employee cannot be placed in one."
      )
    ).toBeInTheDocument();
  });

  it("never submits a team, so an edit cannot silently unseat the employee", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));

    render(
      <EmployeeForm
        employee={HOD_EMPLOYEE}
        endpoint="/api/hr/employees/1"
        method="PATCH"
        departments={DEPARTMENTS}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(fetch).toHaveBeenCalled());
    expect(
      JSON.parse(String(vi.mocked(fetch).mock.calls[0][1]?.body)).team
    ).toBeUndefined();
  });

  it("creates a department inline and selects it", async () => {
    const created: Department = {
      id: 3,
      name: "ICT",
      is_active: true,
      team_count: 0,
      employee_count: 0,
      teams: [],
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    };
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify(created), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      })
    );

    render(
      <EmployeeForm
        endpoint="/api/hr/employees"
        method="POST"
        departments={DEPARTMENTS}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Create department" }));
    fireEvent.change(screen.getByLabelText("New department name"), {
      target: { value: "ICT" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save department" }));

    await waitFor(() =>
      expect(vi.mocked(fetch)).toHaveBeenCalledWith(
        "/api/hr/departments",
        expect.objectContaining({ method: "POST" })
      )
    );
    await waitFor(() =>
      expect(screen.getByLabelText("Department")).toHaveValue("3")
    );
    expect(
      Array.from(
        (screen.getByLabelText("Department") as HTMLSelectElement).options
      ).map((option) => option.textContent)
    ).toEqual(["No department", "Administration", "Bunda College", "ICT"]);
  });

  it("labels the current role on create and on edit", () => {
    const { unmount } = render(
      <EmployeeForm endpoint="/api/hr/employees" method="POST" />
    );
    expect(screen.getByLabelText("Role")).toHaveValue("Employee");

    unmount();

    render(
      <EmployeeForm
        employee={HOD_EMPLOYEE}
        endpoint="/api/hr/employees/1"
        method="PATCH"
      />
    );
    expect(screen.getByLabelText("Role")).toHaveValue("Approver");
  });

  it("requires a password when creating an account", () => {
    render(<EmployeeForm endpoint="/api/hr/employees" method="POST" />);

    const password = screen.getByLabelText("Password");
    expect(password).toBeRequired();
    expect(password).toHaveAttribute("minlength", "8");
    expect(password).toHaveAttribute("autocomplete", "new-password");
  });

  it("does not require a password when editing, and says blank keeps the current one", () => {
    render(
      <EmployeeForm
        employee={HOD_EMPLOYEE}
        endpoint="/api/hr/employees/1"
        method="PATCH"
      />
    );

    const password = screen.getByLabelText("Password");
    expect(password).not.toBeRequired();
    expect(password).toHaveAttribute(
      "placeholder",
      "Leave blank to keep the current password"
    );
  });

  it("submits the password but never the role", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));

    render(<EmployeeForm endpoint="/api/hr/employees" method="POST" />);
    submitPayload("chosen-pass-1");

    await waitFor(() => expect(fetch).toHaveBeenCalled());
    const body = JSON.parse(String(vi.mocked(fetch).mock.calls[0][1]?.body));
    expect(body.password).toBe("chosen-pass-1");
    // The role is fixed server-side: sending it would either be ignored or
    // wrongly read as an attempt to choose access.
    expect(body.role).toBeUndefined();
  });
});