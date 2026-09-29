import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";

import { DelegationReview } from "@/components/hr/delegation-review";
import type { Delegation } from "@/lib/delegations";
import type { Employee, UserRole } from "@/lib/employees";

import { selectOption } from "./helpers/select";

let user: ReturnType<typeof userEvent.setup>;

vi.mock("@/lib/delegations-client", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/lib/delegations-client")>();
  return {
    ...actual,
    approveDelegation: vi.fn(),
    rejectDelegation: vi.fn(),
    cancelDelegation: vi.fn(),
  };
});

import {
  approveDelegation,
  cancelDelegation,
  rejectDelegation,
} from "@/lib/delegations-client";

function makeEmployee(id: number, role: UserRole, name: string): Employee {
  return {
    id,
    user_id: id,
    email: `${name.replace(" ", ".").toLowerCase()}@test.luanar`,
    first_name: name.split(" ")[0],
    last_name: name.split(" ")[1] ?? "",
    full_name: name,
    role,
    designation: "Role holder",
    department: "Registry",
    category: "academic",
    grade: "G",
    appointment_date: "2020-01-01",
    is_active: true,
  supervisor: null,
  };
}

const employees: Employee[] = [
  makeEmployee(3, "dean", "Jane Dean"),
  makeEmployee(5, "hod", "Bob HOD"),
];

const base: Delegation = {
  id: 1,
  approver: 3,
  approver_name: "Jane Dean",
  approver_role: "dean",
  delegate: null,
  delegate_name: "",
  starts_on: "2026-10-01",
  ends_on: null,
  request_reason: "Attending a conference",
  requested_by: 1,
  requested_by_name: "Aisha HR",
  decision_reason: "",
  decided_by: null,
  decided_at: null,
  status: "requested",
  state: "requested",
  created_at: "2026-09-17T12:00:00Z",
  updated_at: "2026-09-17T12:00:00Z",
};

describe("DelegationReview", () => {
  beforeEach(() => {
    vi.mocked(approveDelegation).mockResolvedValue(base);
    vi.mocked(rejectDelegation).mockResolvedValue(base);
    vi.mocked(cancelDelegation).mockResolvedValue(base);
    user = userEvent.setup();
  });

  it("renders the delegation details and a state badge", () => {
    render(<DelegationReview delegation={base} employees={employees} />);

    expect(
      screen.getByRole("heading", { name: "Review delegation request" })
    ).toBeInTheDocument();
    expect(screen.getByText("Jane Dean")).toBeInTheDocument();
    expect(screen.getByText("dean")).toBeInTheDocument();
    expect(screen.getByText("Not yet assigned")).toBeInTheDocument();
    expect(screen.getByText("Requested")).toBeInTheDocument();
    expect(screen.getByText("Attending a conference")).toBeInTheDocument();
  });

  it("shows approve and reject controls for a requested delegation", () => {
    render(<DelegationReview delegation={base} employees={employees} />);

    expect(
      screen.getByRole("button", { name: "Approve" })
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reject" })).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Cancel delegation" })
    ).not.toBeInTheDocument();
  });

  it("requires a reason before approving", () => {
    render(<DelegationReview delegation={base} employees={employees} />);

    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    fireEvent.click(
      screen.getByRole("button", { name: "Confirm approval" })
    );

    expect(
      screen.getByText("A decision reason is required.")
    ).toBeInTheDocument();
    expect(approveDelegation).not.toHaveBeenCalled();
  });

  it("submits an approval with delegate and reason", async () => {
    render(<DelegationReview delegation={base} employees={employees} />);

    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    await selectOption(screen.getByLabelText("Delegate"), "Bob HOD", { user });
    fireEvent.change(screen.getByLabelText("Decision reason"), {
      target: { value: "Approved" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Confirm approval" })
    );

    expect(approveDelegation).toHaveBeenCalledWith(1, {
      delegate: 5,
      decision_reason: "Approved",
    });
  });

  it("submits a rejection with the mandatory reason", () => {
    render(<DelegationReview delegation={base} employees={employees} />);

    fireEvent.click(screen.getByRole("button", { name: "Reject" }));
    fireEvent.change(screen.getByLabelText("Decision reason"), {
      target: { value: "Not required" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Confirm rejection" })
    );

    expect(rejectDelegation).toHaveBeenCalledWith(1, "Not required");
  });

  it("shows the reason error for a rejection too", () => {
    render(<DelegationReview delegation={base} employees={employees} />);

    fireEvent.click(screen.getByRole("button", { name: "Reject" }));
    fireEvent.click(
      screen.getByRole("button", { name: "Confirm rejection" })
    );

    expect(
      screen.getByText("A decision reason is required.")
    ).toBeInTheDocument();
    expect(rejectDelegation).not.toHaveBeenCalled();
  });

  it("shows cancel only for scheduled or active approved delegations", () => {
    render(
      <DelegationReview
        delegation={{
          ...base,
          delegate: 5,
          delegate_name: "Bob HOD",
          status: "approved",
          state: "active",
        }}
        employees={employees}
      />
    );

    expect(
      screen.getByRole("button", { name: "Cancel delegation" })
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Approve" })
    ).not.toBeInTheDocument();
  });

  it("submits a cancellation with the mandatory reason", () => {
    render(
      <DelegationReview
        delegation={{
          ...base,
          delegate: 5,
          delegate_name: "Bob HOD",
          status: "approved",
          state: "active",
        }}
        employees={employees}
      />
    );

    fireEvent.click(
      screen.getByRole("button", { name: "Cancel delegation" })
    );
    fireEvent.change(screen.getByLabelText("Decision reason"), {
      target: { value: "Delegate returned early" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Confirm cancellation" })
    );

    expect(cancelDelegation).toHaveBeenCalledWith(
      1,
      "Delegate returned early"
    );
  });

  it("shows no decision controls for ended, rejected, or cancelled delegations", () => {
    for (const state of ["ended", "rejected", "cancelled"]) {
      const { unmount } = render(
        <DelegationReview
          delegation={{ ...base, state, status: state } as Delegation}
          employees={employees}
        />
      );
      expect(
        screen.queryByRole("button", { name: "Approve" })
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Reject" })
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Cancel delegation" })
      ).not.toBeInTheDocument();
      unmount();
    }
  });

  describe("read-only (approver-side) view", () => {
    it("shows the record but none of the HR decision controls", () => {
      // Even a requested delegation, which is exactly when HR gets buttons.
      render(
        <DelegationReview
          delegation={base}
          employees={employees}
          readOnly
          backHref="/dashboard/cover"
          title="Delegation"
        />
      );

      expect(screen.getByText("Attending a conference")).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: "Delegation" })).toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Approve" })
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Reject" })
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Cancel delegation" })
      ).not.toBeInTheDocument();
    });

    it("hides cancel on an active delegation too", () => {
      render(
        <DelegationReview
          delegation={{
            ...base,
            state: "active",
            status: "approved",
            delegate: 5,
            delegate_name: "Bob HOD",
          }}
          employees={employees}
          readOnly
        />
      );

      expect(
        screen.queryByRole("button", { name: "Cancel delegation" })
      ).not.toBeInTheDocument();
    });

    it("links back to the approver's own cover view", () => {
      render(
        <DelegationReview
          delegation={base}
          employees={employees}
          readOnly
          backHref="/dashboard/cover"
        />
      );

      expect(
        screen.getByRole("link", { name: /Back to delegations/ }).getAttribute("href")
      ).toBe("/dashboard/cover");
    });
  });
});
