import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DepartmentForm } from "@/components/hr/department-form";
import type { Department } from "@/lib/departments";
import {
  createDepartment,
  retireDepartment,
  updateDepartment,
} from "@/lib/departments-client";

const push = vi.fn();
const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh }),
}));

vi.mock("@/lib/departments-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/departments-client")>();
  return {
    ...actual,
    createDepartment: vi.fn(),
    updateDepartment: vi.fn(),
    retireDepartment: vi.fn(),
  };
});

const ict: Department = {
  id: 3,
  name: "ICT",
  is_active: true,
  team_count: 2,
  employee_count: 5,
  teams: [],
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("DepartmentForm", () => {
  it("creates a department from its name and returns to the list", async () => {
    vi.mocked(createDepartment).mockResolvedValue(ict);
    render(<DepartmentForm />);

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "ICT" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create department" }));

    await waitFor(() =>
      expect(createDepartment).toHaveBeenCalledWith({ name: "ICT" })
    );
    expect(push).toHaveBeenCalledWith("/dashboard/hr-admin/departments");
    expect(refresh).toHaveBeenCalled();
  });

  it("prefills an existing department and shows the relationships it owns", () => {
    render(<DepartmentForm department={ict} />);

    expect(screen.getByLabelText("Name")).toHaveValue("ICT");
    expect(screen.getByText(/2 teams · 5 employees/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Retire department" })
    ).toBeInTheDocument();
  });

  it("retires rather than deletes, so history can still name the department", async () => {
    vi.mocked(retireDepartment).mockResolvedValue({ ...ict, is_active: false });
    render(<DepartmentForm department={ict} />);

    fireEvent.click(screen.getByRole("button", { name: "Retire department" }));

    await waitFor(() => expect(retireDepartment).toHaveBeenCalledWith(3));
    expect(push).toHaveBeenCalledWith("/dashboard/hr-admin/departments");
  });

  it("reports a save to its host instead of navigating, when hosted", async () => {
    // The overlay closes and refetches in place; pushing the list route as well
    // would fight the dialog it just dismissed.
    vi.mocked(updateDepartment).mockResolvedValue(ict);
    const onSuccess = vi.fn();
    render(<DepartmentForm department={ict} onSuccess={onSuccess} />);

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "ICT" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(onSuccess).toHaveBeenCalledWith(ict));
    expect(push).not.toHaveBeenCalled();
    expect(refresh).not.toHaveBeenCalled();
  });

  it("reports a retirement to the same host callback", async () => {
    vi.mocked(retireDepartment).mockResolvedValue({
      ...ict,
      is_active: false,
    });
    const onSuccess = vi.fn();
    render(<DepartmentForm department={ict} onSuccess={onSuccess} />);

    fireEvent.click(screen.getByRole("button", { name: "Retire department" }));

    await waitFor(() =>
      expect(onSuccess).toHaveBeenCalledWith({ ...ict, is_active: false })
    );
    expect(push).not.toHaveBeenCalled();
  });

  it("offers a dismiss action when hosted, and it is a button not a link", () => {
    const onCancel = vi.fn();
    render(<DepartmentForm department={ict} onCancel={onCancel} />);

    const cancel = screen.getByRole("button", { name: "Cancel" });
    // A link would leave the overlay behind; the dialog owns dismissal.
    expect(screen.queryByRole("link", { name: "Cancel" })).toBeNull();

    fireEvent.click(cancel);

    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("leaves Cancel as a link when there is nothing to dismiss to", () => {
    render(<DepartmentForm department={ict} />);

    expect(screen.getByRole("link", { name: "Cancel" })).toHaveAttribute(
      "href",
      "/dashboard/hr-admin/departments"
    );
    expect(screen.queryByRole("button", { name: "Cancel" })).toBeNull();
  });

  it("shows a sentence when the backend refuses the change", async () => {
    vi.mocked(updateDepartment).mockRejectedValue(
      new Error("A department with this name already exists.")
    );
    render(<DepartmentForm department={ict} />);

    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "IT" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    expect(
      await screen.findByText("A department with this name already exists.")
    ).toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();
  });
});
