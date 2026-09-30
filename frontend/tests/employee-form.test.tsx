import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { EmployeeForm } from "@/components/hr/employee-form";
import type { Employee } from "@/lib/employees";
import { makeEmployee } from "@/lib/employees/__fixtures__";
import { openSelect, selectOption, selectedValue } from "./helpers/select";

const HOD_EMPLOYEE: Employee = makeEmployee({
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
  team_name: "Bunda College Faculty",
});

/** `roleLabel` is the visible option text, e.g. "Approver". */
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

  it("offers the three system roles, and no approver positions", async () => {
    render(<EmployeeForm endpoint="/api/hr/employees" method="POST" />);

    await openSelect(screen.getByLabelText("Role"));

    const options = screen
      .getAllByRole("option")
      .map((option) => option.textContent);
    // Approver positions are held on a team or granted institution-wide, so
    // they are not chosen here.
    expect(options).toEqual(["Employee", "Approver", "Human Resources"]);
  });

  it("offers the teams it was given and defaults to no team", async () => {
    render(
      <EmployeeForm
        endpoint="/api/hr/employees"
        method="POST"
        teams={[
          { id: 4, name: "Bunda College Faculty", status: "active", is_effective: true },
          { id: 5, name: "Registry", status: "active", is_effective: true },
        ]}
      />
    );

    const teamSelect = screen.getByLabelText("Team");
    await openSelect(teamSelect);

    const options = screen
      .getAllByRole("option")
      .map((option) => option.textContent);
    expect(options).toEqual(["No team", "Bunda College Faculty", "Registry"]);
  });

  it("says which teams would not route, rather than letting HR assign into a trap", async () => {
    // An employee in a team that is not routing only finds out when they
    // submit, which is a bad time to find out. The reason is on the option.
    render(
      <EmployeeForm
        endpoint="/api/hr/employees"
        method="POST"
        teams={[
          { id: 4, name: "Registry", status: "active", is_effective: true },
          {
            id: 5,
            name: "New Team",
            status: "draft",
            is_effective: false,
          },
          {
            id: 6,
            name: "Old Team",
            status: "inactive",
            is_effective: false,
          },
          {
            id: 7,
            name: "Handover",
            status: "active",
            is_effective: false,
          },
        ]}
      />
    );

    const teamSelect = screen.getByLabelText("Team");
    await openSelect(teamSelect);

    const options = screen
      .getAllByRole("option")
      .map((option) => option.textContent);
    expect(options).toEqual([
      "No team",
      "Registry",
      "New Team (still being set up)",
      "Old Team (retired)",
      "Handover (not in force today)",
    ]);
  });

  it("prefills the employee's own team on edit", () => {
    render(
      <EmployeeForm
        employee={HOD_EMPLOYEE}
        endpoint="/api/hr/employees/1"
        method="PATCH"
        teams={[
          { id: 4, name: "Bunda College Faculty", status: "active", is_effective: true },
          { id: 5, name: "Registry", status: "active", is_effective: true },
        ]}
      />
    );

    expect(selectedValue(screen.getByLabelText("Team"))).toBe(
      "Bunda College Faculty"
    );
  });

  it("submits the chosen team, and null when the employee has none", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));
    const { unmount } = render(
      <EmployeeForm
        endpoint="/api/hr/employees"
        method="POST"
        teams={[{ id: 4, name: "Bunda College Faculty", status: "active", is_effective: true }]}
      />
    );
    await selectOption(screen.getByLabelText("Team"), "Bunda College Faculty", { user });
    await submitPayload("Employee");

    await waitFor(() => expect(fetch).toHaveBeenCalled());
    expect(
      JSON.parse(String(vi.mocked(fetch).mock.calls[0][1]?.body)).team
    ).toBe(4);
    unmount();

    vi.mocked(fetch).mockClear();
    render(<EmployeeForm endpoint="/api/hr/employees" method="POST" />);
    await submitPayload("Employee");

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
    expect(selectedValue(screen.getByLabelText("Role"))).toBe("Employee");

    unmount();

    render(
      <EmployeeForm
        employee={HOD_EMPLOYEE}
        endpoint="/api/hr/employees/1"
        method="PATCH"
      />
    );
    expect(selectedValue(screen.getByLabelText("Role"))).toBe("Approver");
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
    await submitPayload("Approver");

    await waitFor(() => expect(fetch).toHaveBeenCalled());
    const init = vi.mocked(fetch).mock.calls[0][1];
    expect(JSON.parse(String(init?.body)).role).toBe("approver");
  });
});