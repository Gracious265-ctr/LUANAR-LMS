import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { EmployeeForm } from "@/components/hr/employee-form";
import { makeEmployee } from "@/lib/employees/__fixtures__";

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
  team: 4,
});

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

  it("offers the three system roles, and no approver positions", () => {
    render(<EmployeeForm endpoint="/api/hr/employees" method="POST" />);

    const roleSelect = screen.getByLabelText("Role") as HTMLSelectElement;
    const options = Array.from(roleSelect.options).map((option) => ({
      value: option.value,
      label: option.textContent,
    }));
    // Approver positions are held on a team or granted institution-wide, so
    // they are not chosen here.
    expect(options).toEqual([
      { value: "employee", label: "Employee" },
      { value: "approver", label: "Approver" },
      { value: "hr", label: "Human Resources" },
    ]);
  });

  it("offers the teams it was given and defaults to no team", () => {
    render(
      <EmployeeForm
        endpoint="/api/hr/employees"
        method="POST"
        teams={[
          { id: 4, name: "Bunda College Faculty" },
          { id: 5, name: "Registry" },
        ]}
      />
    );

    const teamSelect = screen.getByLabelText("Team") as HTMLSelectElement;
    expect(teamSelect).toHaveValue("");
    expect(
      Array.from(teamSelect.options).map((option) => option.textContent)
    ).toEqual(["No team", "Bunda College Faculty", "Registry"]);
  });

  it("prefills the employee's own team on edit", () => {
    render(
      <EmployeeForm
        employee={HOD_EMPLOYEE}
        endpoint="/api/hr/employees/1"
        method="PATCH"
        teams={[
          { id: 4, name: "Bunda College Faculty" },
          { id: 5, name: "Registry" },
        ]}
      />
    );

    expect(screen.getByLabelText("Team")).toHaveValue("4");
  });

  it("submits the chosen team, and null when the employee has none", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));
    const { unmount } = render(
      <EmployeeForm
        endpoint="/api/hr/employees"
        method="POST"
        teams={[{ id: 4, name: "Bunda College Faculty" }]}
      />
    );
    fireEvent.change(screen.getByLabelText("Team"), { target: { value: "4" } });
    submitPayload("employee");

    await waitFor(() => expect(fetch).toHaveBeenCalled());
    expect(
      JSON.parse(String(vi.mocked(fetch).mock.calls[0][1]?.body)).team
    ).toBe(4);
    unmount();

    vi.mocked(fetch).mockClear();
    render(<EmployeeForm endpoint="/api/hr/employees" method="POST" />);
    submitPayload("employee");

    await waitFor(() => expect(fetch).toHaveBeenCalled());
    expect(
      JSON.parse(String(vi.mocked(fetch).mock.calls[0][1]?.body)).team
    ).toBeNull();
  });

  it("disables the team picker and explains why when teams could not load", () => {
    render(
      <EmployeeForm
        endpoint="/api/hr/employees"
        method="POST"
        teamsError="Teams could not be loaded, so this employee cannot be placed in a team."
      />
    );

    expect(screen.getByLabelText("Team")).toBeDisabled();
    expect(
      screen.getByText(
        "Teams could not be loaded, so this employee cannot be placed in a team."
      )
    ).toBeInTheDocument();
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
    expect(screen.getByLabelText("Role")).toHaveValue("approver");
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
    submitPayload("approver");

    await waitFor(() => expect(fetch).toHaveBeenCalled());
    const init = vi.mocked(fetch).mock.calls[0][1];
    expect(JSON.parse(String(init?.body)).role).toBe("approver");
  });
});