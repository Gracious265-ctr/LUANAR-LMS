import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { EmployeeForm } from "@/components/hr/employee-form";
import { makeEmployee } from "@/lib/employees/__fixtures__";

const LEAD_EMPLOYEE = makeEmployee({
  id: 1,
  user_id: 2,
  email: "lead@test.luanar",
  first_name: "Test",
  last_name: "Lead",
  full_name: "Test Lead",
  role: "approver",
  approver_roles: ["lead"],
  designation: "Team Leader",
  team: 4,
  team_name: "Bunda College Faculty",
});

function submitPayload() {
  fireEvent.change(screen.getByLabelText("First name"), {
    target: { value: "Test" },
  });
  fireEvent.change(screen.getByLabelText("Last name"), {
    target: { value: "Employee" },
  });
  fireEvent.change(screen.getByLabelText("Email"), {
    target: { value: "new.employee@test.luanar" },
  });

  fireEvent.click(
    screen.getByRole("button", { name: /create employee|save changes/i })
  );
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
    render(<EmployeeForm endpoint="/api/hr/employees" method="POST" />);

    expect(screen.queryByLabelText("Team")).toBeNull();
  });


  it("never submits a team, so an edit cannot silently unseat the employee", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));

    render(
      <EmployeeForm
        employee={LEAD_EMPLOYEE}
        endpoint="/api/hr/employees/1"
        method="PATCH"
      />
    );
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(fetch).toHaveBeenCalled());
    expect(
      JSON.parse(String(vi.mocked(fetch).mock.calls[0][1]?.body)).team
    ).toBeUndefined();
  });

  it("submits nothing that locates a person in the institution, because the team does that", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));

    render(<EmployeeForm endpoint="/api/hr/employees" method="POST" />);
    submitPayload();

    await waitFor(() => expect(fetch).toHaveBeenCalled());
    // The team is where leave routes, and it is set from the team screen, so the
    // form asks only about the person themselves. The key list is exact rather
    // than a spot check, because the backend refuses a field it does not have:
    // a stray key would be a save that fails, not a wrong value on screen.
    expect(
      Object.keys(
        JSON.parse(String(vi.mocked(fetch).mock.calls[0][1]?.body))
      ).sort()
    ).toEqual([
      "appointment_date",
      "category",
      "designation",
      "email",
      "first_name",
      "grade",
      "is_active",
      "last_name",
    ]);
  });

  it("labels the current role on create and on edit", () => {
    const { unmount } = render(
      <EmployeeForm endpoint="/api/hr/employees" method="POST" />
    );
    expect(screen.getByLabelText("Role")).toHaveValue("Employee");

    unmount();

    render(
      <EmployeeForm
        employee={LEAD_EMPLOYEE}
        endpoint="/api/hr/employees/1"
        method="PATCH"
      />
    );
    expect(screen.getByLabelText("Role")).toHaveValue("Approver");
  });

  it("offers no password field, because HR cannot set one", () => {
    render(<EmployeeForm endpoint="/api/hr/employees" method="POST" />);

    // The account is unusable until the person follows the emailed
    // set-password link, so there is nothing here for HR to fill in.
    expect(screen.queryByLabelText("Password")).toBeNull();
  });

  it("sends no password when editing either", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));

    render(
      <EmployeeForm
        employee={LEAD_EMPLOYEE}
        endpoint="/api/hr/employees/1"
        method="PATCH"
      />
    );

    submitPayload();

    await waitFor(() => expect(fetch).toHaveBeenCalled());
    const body = JSON.parse(String(vi.mocked(fetch).mock.calls[0][1]?.body));
    expect(body.password).toBeUndefined();
  });

  it("submits the password but never the role", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));

    render(<EmployeeForm endpoint="/api/hr/employees" method="POST" />);
    submitPayload();

    await waitFor(() => expect(fetch).toHaveBeenCalled());
    const body = JSON.parse(String(vi.mocked(fetch).mock.calls[0][1]?.body));
    // HR sets no password: the account is unusable until the person follows
    // the emailed set-password link.
    expect(body.password).toBeUndefined();
    // The role is fixed server-side: sending it would either be ignored or
    // wrongly read as an attempt to choose access.
    expect(body.role).toBeUndefined();
  });
});