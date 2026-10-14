import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AdminUserForm } from "@/components/admin/admin-user-form";
import type { AdminUser } from "@/lib/admin-users";
import { createAdminUser, updateAdminUser } from "@/lib/admin-users-client";

const push = vi.fn();
const refresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh }),
}));

vi.mock("@/lib/admin-users-client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/admin-users-client")>();
  return { ...actual, createAdminUser: vi.fn(), updateAdminUser: vi.fn() };
});

const hr: AdminUser = {
  id: 2,
  email: "hr@test.luanar",
  first_name: "Test",
  last_name: "HR",
  full_name: "Test HR",
  role: "hr",
  is_active: true,
  is_superuser: false,
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("AdminUserForm", () => {
  it("creates an HR account with an initial password and no role field", async () => {
    vi.mocked(createAdminUser).mockResolvedValue(hr);
    render(<AdminUserForm />);

    expect(screen.queryByLabelText("Role")).toBeNull();
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "ada@test.luanar" },
    });
    fireEvent.change(screen.getByLabelText("First name"), {
      target: { value: "Ada" },
    });
    fireEvent.change(screen.getByLabelText("Initial password"), {
      target: { value: "longenough" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create HR user" }));

    await waitFor(() =>
      expect(createAdminUser).toHaveBeenCalledWith({
        email: "ada@test.luanar",
        first_name: "Ada",
        last_name: "",
        password: "longenough",
      })
    );
    expect(push).toHaveBeenCalledWith("/dashboard/admin/users");
    expect(refresh).toHaveBeenCalled();
  });

  it("requires a password when creating, matching the backend's rule", () => {
    render(<AdminUserForm />);

    const password = screen.getByLabelText("Initial password");
    expect(password).toBeRequired();
    expect(password).toHaveAttribute("minlength", "8");
  });

  it("prefills an existing account and makes the email read-only", () => {
    render(<AdminUserForm user={hr} />);

    expect(screen.getByLabelText("Email")).toHaveValue("hr@test.luanar");
    expect(screen.getByLabelText("Email")).toHaveAttribute("readonly");
    expect(screen.getByLabelText("New password")).not.toBeRequired();
    expect(screen.getByRole("checkbox")).toBeChecked();
  });

  it("resets a password only when one is typed", async () => {
    vi.mocked(updateAdminUser).mockResolvedValue(hr);
    const { unmount } = render(<AdminUserForm user={hr} />);

    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(updateAdminUser).toHaveBeenCalled());
    expect(vi.mocked(updateAdminUser).mock.calls[0][1]).not.toHaveProperty(
      "password"
    );
    unmount();

    vi.mocked(updateAdminUser).mockClear();
    render(<AdminUserForm user={hr} />);
    fireEvent.change(screen.getByLabelText("New password"), {
      target: { value: "brandnewpass" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() =>
      expect(vi.mocked(updateAdminUser).mock.calls[0][1]).toMatchObject({
        password: "brandnewpass",
      })
    );
  });

  it("shows why the backend refused the account", async () => {
    vi.mocked(createAdminUser).mockRejectedValue(
      new Error("An account with this email already exists.")
    );
    render(<AdminUserForm />);

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "hr@test.luanar" },
    });
    fireEvent.change(screen.getByLabelText("Initial password"), {
      target: { value: "longenough" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create HR user" }));

    expect(
      await screen.findByText("An account with this email already exists.")
    ).toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();
  });
});
