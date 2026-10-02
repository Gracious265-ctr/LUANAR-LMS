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
  it("creates a role from its name alone, leaving the code to the backend", async () => {
    render(<ApproverRoleForm />);

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Head of Department" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create role" }));

    await waitFor(() => expect(createApproverRole).toHaveBeenCalled());
    expect(vi.mocked(createApproverRole).mock.calls[0][0]).toEqual({
      label: "Head of Department",
    });
  });

  it("does not ask for a code or behaviour when the role does not exist yet", () => {
    render(<ApproverRoleForm />);

    expect(screen.queryByLabelText("Code")).not.toBeInTheDocument();
    expect(
      screen.queryByLabelText("Leave history visible to this approver")
    ).not.toBeInTheDocument();
    expect(
      screen.queryByLabelText("Institution-wide role", { exact: false })
    ).not.toBeInTheDocument();
  });

  it("shows the code on edit without letting it be typed", () => {
    render(<ApproverRoleForm role={role} />);

    expect(screen.getByText("hod")).toBeInTheDocument();
    expect(screen.queryByLabelText("Code")).not.toBeInTheDocument();
  });

  it("shows the name on edit but does not send it, because it cannot change", async () => {
    render(<ApproverRoleForm role={role} />);

    expect(screen.getByLabelText("Name")).toHaveValue("Head of Department");
    expect(screen.getByLabelText("Name")).toHaveAttribute("readonly");

    fireEvent.change(screen.getByLabelText("Description"), {
      target: { value: "Approves department leave" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(updateApproverRole).toHaveBeenCalled());
    const [, input] = vi.mocked(updateApproverRole).mock.calls[0];
    expect(input).toMatchObject({
      description: "Approves department leave",
      history_scope: "same_department",
      handles_cancellation: false,
      is_institution_wide: false,
    });
    expect(input).not.toHaveProperty("label");
    expect(input).not.toHaveProperty("code");
  });

  it("offers every history scope the backend defines on an existing role", () => {
    render(<ApproverRoleForm role={role} />);

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
    expect(select).toHaveValue("same_department");
  });

  it("marks a role institution-wide when editing it", async () => {
    render(<ApproverRoleForm role={role} />);

    fireEvent.click(
      screen.getByLabelText("Institution-wide role", { exact: false })
    );
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(updateApproverRole).toHaveBeenCalled());
    expect(
      vi.mocked(updateApproverRole).mock.calls[0][1].is_institution_wide
    ).toBe(true);
  });

  it("shows the backend's rejection without losing what was typed", async () => {
    vi.mocked(createApproverRole).mockRejectedValue(
      new Error("label: Enter a role name.")
    );
    render(<ApproverRoleForm />);

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Head of Department" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create role" }));

    expect(
      await screen.findByText("label: Enter a role name.")
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Name")).toHaveValue("Head of Department");
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