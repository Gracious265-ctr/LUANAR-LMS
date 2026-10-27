import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { AdminUser } from "@/lib/admin-users";
import { createAdminUser, updateAdminUser } from "@/lib/admin-users-client";

import { AdminUsersSection } from "@/components/admin/AdminUsersSection";
import { AdminUserTable } from "@/components/admin/admin-user-table";

const { routerMock, searchParamsRef, pathnameRef } = vi.hoisted(() => ({
  routerMock: { push: vi.fn(), replace: vi.fn(), back: vi.fn(), refresh: vi.fn() },
  searchParamsRef: { current: new URLSearchParams() },
  pathnameRef: { current: "/dashboard/admin/users" },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => routerMock,
  usePathname: () => pathnameRef.current,
  useSearchParams: () => searchParamsRef.current,
}));

vi.mock("@/lib/admin-users-client", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/lib/admin-users-client")>();
  return { ...actual, createAdminUser: vi.fn(), updateAdminUser: vi.fn() };
});

const users: AdminUser[] = [
  {
    id: 2,
    email: "hr@test.luanar",
    first_name: "Test",
    last_name: "HR",
    full_name: "Test HR",
    role: "hr",
    is_active: true,
    is_superuser: false,
  },
  {
    id: 5,
    email: "leave@luanar.ac.mw",
    first_name: "Leave",
    last_name: "Officer",
    full_name: "Leave Officer",
    role: "hr",
    is_active: false,
    is_superuser: false,
  },
];

describe("AdminUsersSection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    pathnameRef.current = "/dashboard/admin/users";
    searchParamsRef.current = new URLSearchParams();
    vi.mocked(createAdminUser).mockResolvedValue(users[0]);
    vi.mocked(updateAdminUser).mockResolvedValue(users[0]);
  });

  it("renders the table with no overlay open", () => {
    render(<AdminUsersSection users={users} />);

    expect(screen.getByText("hr@test.luanar")).toBeInTheDocument();
    expect(screen.getByText("Inactive")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("keeps the row Edit a real link when no overlay host is given", () => {
    render(<AdminUserTable users={users} />);

    const links = screen.getAllByRole("link", { name: "Edit" });
    expect(links).toHaveLength(2);
    expect(links[0].getAttribute("href")).toBe(
      "/dashboard/admin/users/2/edit"
    );
    expect(links[1].getAttribute("href")).toBe(
      "/dashboard/admin/users/5/edit"
    );
  });

  it("turns the row Edit into a button that targets the row id", () => {
    render(<AdminUsersSection users={users} />);

    fireEvent.click(screen.getByRole("button", { name: "Edit Test HR" }));

    expect(routerMock.push).toHaveBeenCalledWith(
      "/dashboard/admin/users?user=2"
    );
  });

  it("names each row's Edit action after the account, not a bare Edit", () => {
    render(<AdminUsersSection users={users} />);

    expect(
      screen.getByRole("button", { name: "Edit Leave Officer" })
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit" })).toBeNull();
  });

  it("opens a create form from the trigger", () => {
    render(<AdminUsersSection users={users} />);

    fireEvent.click(screen.getByRole("button", { name: /New HR user/ }));

    expect(routerMock.push).toHaveBeenCalledWith(
      "/dashboard/admin/users?user=new"
    );
  });

  it("seeds edit mode from the row already on screen, with no fetch", () => {
    searchParamsRef.current = new URLSearchParams("user=2");
    render(<AdminUsersSection users={users} />);

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toHaveValue("hr@test.luanar");
    expect(screen.getByLabelText("First name")).toHaveValue("Test");
    // The wrapping label carries the help text too, so the checkbox is found
    // by role — exactly as the form's own test does it.
    expect(screen.getByRole("checkbox")).toBeChecked();
    expect(screen.getByRole("button", { name: "Save changes" })).toBeInTheDocument();
  });

  it("still edits a deactivated row, because inactive accounts stay listed", () => {
    searchParamsRef.current = new URLSearchParams("user=5");
    render(<AdminUsersSection users={users} />);

    expect(screen.queryByText(/no longer in the list/)).toBeNull();
    expect(screen.getByLabelText("Email")).toHaveValue("leave@luanar.ac.mw");
    expect(screen.getByRole("checkbox")).not.toBeChecked();
  });

  it("shows a create form for the new target rather than an edit form", () => {
    searchParamsRef.current = new URLSearchParams("user=new");
    render(<AdminUsersSection users={users} />);

    expect(screen.getByLabelText("Email")).toHaveValue("");
    expect(
      screen.getByRole("button", { name: "Create HR user" })
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save changes" })).toBeNull();
  });

  it("reports an id that matches no row instead of rendering a blank edit form", () => {
    searchParamsRef.current = new URLSearchParams("user=99");
    render(<AdminUsersSection users={users} />);

    expect(screen.getByText(/no longer in the list/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Email")).toBeNull();
  });

  it("switches target without leaking the previous row's values", () => {
    searchParamsRef.current = new URLSearchParams("user=2");
    const { rerender } = render(<AdminUsersSection users={users} />);
    expect(screen.getByLabelText("First name")).toHaveValue("Test");

    searchParamsRef.current = new URLSearchParams("user=5");
    rerender(<AdminUsersSection users={users} />);

    expect(screen.getByLabelText("First name")).toHaveValue("Leave");
    expect(screen.getByLabelText("Email")).toHaveValue("leave@luanar.ac.mw");
  });

  it("refetches and closes after a create, without navigating away", async () => {
    searchParamsRef.current = new URLSearchParams("user=new");
    render(<AdminUsersSection users={users} />);

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "ada@test.luanar" },
    });
    fireEvent.change(screen.getByLabelText("Initial password"), {
      target: { value: "longenough" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create HR user" }));

    await waitFor(() => expect(routerMock.refresh).toHaveBeenCalled());
    expect(createAdminUser).toHaveBeenCalledWith(
      expect.objectContaining({ email: "ada@test.luanar" })
    );
    // The lone JSDOM history entry takes close's replace fallback; either way
    // the point is that it did not `push` the user off the list.
    expect(routerMock.replace).toHaveBeenCalledWith(
      "/dashboard/admin/users"
    );
    expect(routerMock.push).not.toHaveBeenCalled();
  });

  it("updates the existing account rather than creating a second one", () => {
    searchParamsRef.current = new URLSearchParams("user=2");
    render(<AdminUsersSection users={users} />);

    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    expect(updateAdminUser).toHaveBeenCalledWith(
      2,
      expect.objectContaining({ email: "hr@test.luanar" })
    );
    expect(createAdminUser).not.toHaveBeenCalled();
  });

  it("closes on cancel without writing anything", () => {
    searchParamsRef.current = new URLSearchParams("user=2");
    render(<AdminUsersSection users={users} />);

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    // Cancel is a button here, not a link: the overlay owns dismissal.
    expect(routerMock.replace).toHaveBeenCalledWith(
      "/dashboard/admin/users"
    );
    expect(updateAdminUser).not.toHaveBeenCalled();
    expect(createAdminUser).not.toHaveBeenCalled();
  });

  it("keeps the host's own query intact when the overlay opens", () => {
    searchParamsRef.current = new URLSearchParams("q=ada");
    render(<AdminUsersSection users={users} />);

    fireEvent.click(screen.getByRole("button", { name: "Edit Test HR" }));

    expect(routerMock.push).toHaveBeenCalledWith(
      "/dashboard/admin/users?q=ada&user=2"
    );
  });

  it("narrows the list by name or email", () => {
    render(<AdminUsersSection users={users} />);

    fireEvent.change(
      screen.getByRole("searchbox", { name: "Search HR users" }),
      { target: { value: "leave@" } }
    );

    expect(screen.getByText("leave@luanar.ac.mw")).toBeInTheDocument();
    expect(screen.queryByText("hr@test.luanar")).toBeNull();
  });

  it("narrows the list to inactive accounts without losing the row", () => {
    render(<AdminUsersSection users={users} />);

    fireEvent.click(screen.getByRole("button", { name: "Inactive only" }));

    expect(screen.getByText("leave@luanar.ac.mw")).toBeInTheDocument();
    expect(screen.queryByText("hr@test.luanar")).toBeNull();
    expect(
      screen.getByRole("button", { name: "Edit Leave Officer" })
    ).toBeInTheDocument();
  });
});
