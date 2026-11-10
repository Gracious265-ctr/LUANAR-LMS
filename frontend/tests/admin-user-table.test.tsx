import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AdminUserTable } from "@/components/admin/admin-user-table";
import type { AdminUser } from "@/lib/admin-users";

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: React.ComponentProps<"a">) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

const user: AdminUser = {
  id: 7,
  email: "hr@test.luanar",
  first_name: "Hana",
  last_name: "Reyes",
  full_name: "Hana Reyes",
  role: "hr",
  is_active: true,
  is_superuser: false,
};

describe("AdminUserTable headings", () => {
  /**
   * The Edit column is the only one without a visible label in the design, and
   * it used to be a bare `<th></th>`. A screen reader then announces a
   * nameless column, so a row of Edit links reads as a column with no purpose.
   */
  it("names every column, including the actions column", () => {
    render(<AdminUserTable users={[user]} />);

    const headers = screen
      .getAllByRole("columnheader")
      .map((header) => header.textContent?.trim());

    expect(headers).toEqual(["Name", "Email", "Status", "Role", "Actions"]);
    // No heading may be blank: a blank one is what made the column nameless.
    expect(headers.every((text) => text && text.length > 0)).toBe(true);
  });

  it("marks every heading as a column heading", () => {
    render(<AdminUserTable users={[user]} />);

    for (const header of screen.getAllByRole("columnheader")) {
      expect(header).toHaveAttribute("scope", "col");
    }
  });

  it("still names the account on the edit control itself", () => {
    // The column heading names the column; the control names the row. Both are
    // needed, because "Edit" alone is ambiguous in a list of accounts.
    render(<AdminUserTable users={[user]} onEdit={vi.fn()} />);

    expect(
      screen.getByRole("button", { name: "Edit Hana Reyes" })
    ).toBeInTheDocument();
  });
});
