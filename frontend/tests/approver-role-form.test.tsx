import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApproverRoleForm } from "@/components/hr/approver-role-form";
import type { ApproverRole } from "@/lib/approver-roles";
import {
  createApproverRole,
  updateApproverRole,
} from "@/lib/approver-roles-client";

const push = vi.fn();
const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh }),
}));

vi.mock("@/lib/approver-roles-client", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/lib/approver-roles-client")>();
  return { ...actual, createApproverRole: vi.fn(), updateApproverRole: vi.fn() };
});

const role: ApproverRole = {
  id: 1,
  code: "hod",
  label: "Head of Department",
  description: "Approves academic leave for the department",
  is_active: true,
  history_scope: "same_department",
  handles_cancellation: false,
  is_institution_wide: false,
  is_in_use: true,
  usage: [],
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ApproverRoleForm", () => {
  it("offers every history scope the backend defines, with a plain meaning", () => {
    render(<ApproverRoleForm />);

    const select = screen.getByLabelText("Leave history visible to this approver");
    expect(
      Array.from(select.querySelectorAll("option")).map(
        (option) => option.textContent
      )
    ).toEqual([
      "Full history",
      "Same department only",
      "Same faculty only",
      "Current financial year only",
      "No history",
    ]);
  });

  it("creates a role with the code HR chose", async () => {
    render(<ApproverRoleForm />);

    fireEvent.change(screen.getByLabelText("Label"), {
      target: { value: "Head of Department" },
    });
    fireEvent.change(screen.getByLabelText("Code"), {
      target: { value: "hod" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create role" }));

    await waitFor(() => expect(createApproverRole).toHaveBeenCalled());
    expect(vi.mocked(createApproverRole).mock.calls[0][0]).toMatchObject({
      code: "hod",
      label: "Head of Department",
      history_scope: "none",
      is_institution_wide: false,
    });
  });

  it("marks a role institution-wide from the form", async () => {
    render(<ApproverRoleForm />);

    fireEvent.change(screen.getByLabelText("Label"), {
      target: { value: "Registrar" },
    });
    fireEvent.change(screen.getByLabelText("Code"), {
      target: { value: "registrar" },
    });
    fireEvent.click(
      screen.getByLabelText("Institution-wide role", { exact: false })
    );
    fireEvent.click(screen.getByRole("button", { name: "Create role" }));

    await waitFor(() => expect(createApproverRole).toHaveBeenCalled());
    expect(vi.mocked(createApproverRole).mock.calls[0][0].is_institution_wide).toBe(
      true
    );
  });

  it("sends no code when updating, so a saved role keeps its identity", async () => {
    render(<ApproverRoleForm role={role} />);

    fireEvent.change(screen.getByLabelText("Label"), {
      target: { value: "Head of Department (Academic)" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(updateApproverRole).toHaveBeenCalled());
    const [, input] = vi.mocked(updateApproverRole).mock.calls[0];
    expect(input?.code).toBeUndefined();
    expect(input?.label).toBe("Head of Department (Academic)");
  });

  it("locks the code on edit and says why", () => {
    render(<ApproverRoleForm role={role} />);

    expect(screen.getByLabelText("Code")).toHaveAttribute("readonly");
    expect(
      screen.getByText(
        "The code cannot change once saved: workflow stages and team memberships store it."
      )
    ).toBeInTheDocument();
  });

  it("prefills an existing role", () => {
    render(<ApproverRoleForm role={role} />);

    expect(screen.getByLabelText("Label")).toHaveValue("Head of Department");
    expect(screen.getByLabelText("Code")).toHaveValue("hod");
    expect(
      screen.getByLabelText("Leave history visible to this approver")
    ).toHaveValue("same_department");
  });

  it("shows the backend's rejection without losing what was typed", async () => {
    vi.mocked(createApproverRole).mockRejectedValue(
      new Error('code: The role code "hod" is already in use.')
    );
    render(<ApproverRoleForm />);

    fireEvent.change(screen.getByLabelText("Label"), {
      target: { value: "Head of Department" },
    });
    fireEvent.change(screen.getByLabelText("Code"), {
      target: { value: "hod" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create role" }));

    expect(
      await screen.findByText('code: The role code "hod" is already in use.')
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Code")).toHaveValue("hod");
    expect(push).not.toHaveBeenCalled();
  });

  it("provides a cancel link back to the roles list", () => {
    render(<ApproverRoleForm />);

    expect(screen.getByRole("link", { name: "Cancel" })).toHaveAttribute(
      "href",
      "/dashboard/hr-admin/roles"
    );
  });
});
